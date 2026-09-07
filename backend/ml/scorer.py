"""Explainable, unlabeled anomaly scoring for calibrated synthetic MPLAD projects.

The scorer consumes only the seven Module 2 features.  It combines a small,
deterministic Isolation Forest with transparent domain rules so every 0--100
risk score is accompanied by actionable, human-readable evidence.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import ceil, log2
from pathlib import Path
from typing import Final

import numpy as np
import pandas as pd

from backend.ml.features import FEATURE_COLUMNS, build_feature_matrix


RISK_SCORE_COLUMN: Final[str] = "risk_score"
REASONS_COLUMN: Final[str] = "reasons"
_SAMPLE_SIZE: Final[int] = 256
_TREE_COUNT: Final[int] = 160
_RANDOM_SEED: Final[int] = 26102


@dataclass(frozen=True)
class _IsolationNode:
    """A node in an isolation tree; leaf size corrects short terminal paths."""

    feature: int | None
    split: float | None
    size: int
    left: _IsolationNode | None = None
    right: _IsolationNode | None = None


def _average_path_length(size: int) -> float:
    """Return the expected unsuccessful-search path length for an isolation leaf."""
    if size <= 1:
        return 0.0
    if size == 2:
        return 1.0
    return 2.0 * (np.log(size - 1) + np.euler_gamma) - (2.0 * (size - 1) / size)


def _build_tree(values: np.ndarray, depth: int, max_depth: int, rng: np.random.Generator) -> _IsolationNode:
    """Randomly partition unlabeled observations; rare values isolate in fewer splits."""
    size = len(values)
    if depth >= max_depth or size <= 1 or np.all(values == values[0]):
        return _IsolationNode(feature=None, split=None, size=size)
    variable_features = np.flatnonzero(np.ptp(values, axis=0) > 0)
    if not len(variable_features):
        return _IsolationNode(feature=None, split=None, size=size)
    feature = int(rng.choice(variable_features))
    low, high = values[:, feature].min(), values[:, feature].max()
    split = float(rng.uniform(low, high))
    left_values, right_values = values[values[:, feature] < split], values[values[:, feature] >= split]
    if not len(left_values) or not len(right_values):
        return _IsolationNode(feature=None, split=None, size=size)
    return _IsolationNode(
        feature=feature,
        split=split,
        size=size,
        left=_build_tree(left_values, depth + 1, max_depth, rng),
        right=_build_tree(right_values, depth + 1, max_depth, rng),
    )


def _path_length(row: np.ndarray, node: _IsolationNode, depth: int = 0) -> float:
    """Measure how quickly one observation reaches a leaf in an isolation tree."""
    if node.feature is None or node.left is None or node.right is None:
        return depth + _average_path_length(node.size)
    child = node.left if row[node.feature] < node.split else node.right
    return _path_length(row, child, depth + 1)


def _rank_normalise(values: np.ndarray) -> np.ndarray:
    """Map each feature to stable percentile ranks so units cannot dominate random splits."""
    frame = pd.DataFrame(values)
    return frame.rank(method="average", pct=True).to_numpy(dtype=float)


def isolation_forest_scores(feature_values: np.ndarray) -> np.ndarray:
    """Return deterministic 0--1 unlabeled Isolation Forest anomaly scores.

    The forest has no labels or ground-truth inputs: observations with shorter
    average random-partition paths receive higher scores.
    """
    if feature_values.ndim != 2 or not len(feature_values):
        raise ValueError("feature_values must be a non-empty two-dimensional matrix")
    values = _rank_normalise(np.nan_to_num(feature_values, nan=0.0, posinf=0.0, neginf=0.0))
    sample_size = min(_SAMPLE_SIZE, len(values))
    max_depth = int(ceil(log2(sample_size)))
    rng = np.random.default_rng(_RANDOM_SEED)
    trees = [_build_tree(values[rng.choice(len(values), size=sample_size, replace=False)], 0, max_depth, rng) for _ in range(_TREE_COUNT)]
    average_paths = np.array([np.mean([_path_length(row, tree) for tree in trees]) for row in values])
    return np.power(2.0, -average_paths / _average_path_length(sample_size))


def suspicious_reasons(row: pd.Series) -> list[str]:
    """State the concrete suspicious patterns detected in one unlabeled feature row.

    Each condition maps to an auditable fraud signal such as cost inflation,
    pre-completion payment, award concentration, or co-located projects.
    """
    reasons: list[str] = []
    if row["cost_ratio"] > 1.8:
        reasons.append(f"Sanctioned cost is {row['cost_ratio']:.1f}x the regional baseline (above 1.8x).")
    if row["completion_speed_ratio"] < 0.5:
        reasons.append(f"Certified completion took only {row['completion_speed_ratio']:.0%} of the planned duration.")
    if row["payment_gap_days"] < 0:
        reasons.append(f"Funds were released {abs(row['payment_gap_days']):.0f} days before certified completion.")
    if row["contractor_project_count"] >= 60 and row["contractor_constituency_share"] >= 0.20:
        reasons.append(
            f"Contractor holds {row['contractor_project_count']:.0f} projects and {row['contractor_constituency_share']:.0%} of this constituency's awards."
        )
    if row["geo_cluster_density"] >= 8:
        reasons.append(f"{row['geo_cluster_density']:.0f} other projects lie within the 2 km spatial-density radius.")
    if row["sanction_lag_days"] >= 85:
        reasons.append(f"Sanction followed recommendation after {row['sanction_lag_days']:.0f} days, an unusually long lag.")
    return reasons


def _rule_risk(row: pd.Series) -> float:
    """Quantify transparent suspicious signals without using hidden evaluation fields."""
    severity = max(
        (row["cost_ratio"] - 1.2) / 1.2,
        (0.75 - row["completion_speed_ratio"]) / 0.65,
        -row["payment_gap_days"] / 45.0,
        min(row["contractor_project_count"] / 75.0, row["contractor_constituency_share"] / 0.30),
        row["geo_cluster_density"] / 12.0,
        (row["sanction_lag_days"] - 75.0) / 30.0,
        0.0,
    )
    return float(np.clip(severity, 0.0, 1.0))


def score_feature_matrix(features: pd.DataFrame) -> pd.DataFrame:
    """Score a Module 2 matrix and attach one or more specific reasons to every project.

    Scores blend the unsupervised forest (40%) and rule severity (60%).  A
    low-scoring project still receives an explicit normal-pattern explanation,
    preventing a bare numerical score from reaching a reviewer.
    """
    expected = ["project_id", *FEATURE_COLUMNS]
    if list(features.columns) != expected:
        raise ValueError(f"features must contain exactly: {', '.join(expected)}")
    numeric = features.loc[:, FEATURE_COLUMNS].to_numpy(dtype=float)
    if not np.isfinite(numeric).all():
        raise ValueError("features must be finite before scoring")
    forest = isolation_forest_scores(numeric)
    rule_scores = features.apply(_rule_risk, axis=1).to_numpy(dtype=float)
    forest_scaled = (forest - forest.min()) / max(float(forest.max() - forest.min()), np.finfo(float).eps)
    scores = np.clip(100.0 * (0.40 * forest_scaled + 0.60 * rule_scores), 0.0, 100.0)
    all_reasons = features.apply(suspicious_reasons, axis=1)
    reason_text = all_reasons.map(lambda items: items if items else ["No material cost, timing, concentration, geographic, or sanction-lag warning was detected."])
    return pd.DataFrame({"project_id": features["project_id"].astype("string"), RISK_SCORE_COLUMN: scores, REASONS_COLUMN: reason_text})


def score_projects(csv_path: str | Path | None = None) -> pd.DataFrame:
    """Build and score the synthetic project feature matrix using no evaluation labels."""
    features = build_feature_matrix() if csv_path is None else build_feature_matrix(csv_path)
    return score_feature_matrix(features)
