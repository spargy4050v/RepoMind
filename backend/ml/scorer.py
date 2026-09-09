"""Explainable, unlabeled anomaly scoring for calibrated synthetic MPLAD projects.

The scorer consumes only the seven Module 2 features.  It uses scikit-learn's
Isolation Forest as the primary detector, Local Outlier Factor as a secondary
cross-check, and transparent domain rules so every 0--100 risk score is
accompanied by actionable, human-readable evidence.
"""

from __future__ import annotations

from pathlib import Path
from typing import Final

import numpy as np
import pandas as pd

from backend.ml.anomaly_detection import fit_isolation_forest, fit_lof, score_combined_batch
from backend.ml.features import FEATURE_COLUMNS, build_feature_matrix


RISK_SCORE_COLUMN: Final[str] = "risk_score"
REASONS_COLUMN: Final[str] = "reasons"
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

    Scores weight the primary Isolation Forest more heavily than the LOF
    cross-check, then blend those continuous signals with capped rule severity.
    Detector agreement remains reviewer-visible in its specific explanation,
    rather than adding a post-scale bonus that could push severe rows above 100
    and collapse their relative severity through clipping. A low-scoring
    project still receives an explicit normal-pattern explanation, preventing
    a bare numerical score from reaching a reviewer.
    """
    expected = ["project_id", *FEATURE_COLUMNS]
    if list(features.columns) != expected:
        raise ValueError(f"features must contain exactly: {', '.join(expected)}")
    numeric = features.loc[:, FEATURE_COLUMNS].to_numpy(dtype=float)
    if not np.isfinite(numeric).all():
        raise ValueError("features must be finite before scoring")
    model_features = features.loc[:, FEATURE_COLUMNS]
    isolation_forest = fit_isolation_forest(model_features)
    lof = fit_lof(model_features)
    model_signals = score_combined_batch(isolation_forest, lof, model_features)
    rule_scores = features.apply(_rule_risk, axis=1).to_numpy(dtype=float)
    forest = model_signals["isolation_forest_score"].to_numpy(dtype=float)
    lof_scores = model_signals["lof_score"].to_numpy(dtype=float)
    forest_scaled = (forest - forest.min()) / max(float(forest.max() - forest.min()), np.finfo(float).eps)
    lof_scaled = (lof_scores - lof_scores.min()) / max(float(lof_scores.max() - lof_scores.min()), np.finfo(float).eps)
    # All components are in [0, 1] and the weights sum to one. Keeping the
    # agreement signal in ``reason_text`` avoids a post-blend bonus that would
    # exceed the 0--100 scale and make different severe projects all read 100.
    scores = 100.0 * (0.35 * forest_scaled + 0.05 * lof_scaled + 0.60 * rule_scores)
    all_reasons = features.apply(suspicious_reasons, axis=1)
    reason_text = [
        reasons + [str(model_signals.iloc[index]["reason"])]
        if reasons or bool(model_signals.iloc[index]["isolation_forest_flag"]) or bool(model_signals.iloc[index]["lof_flag"])
        else ["No material cost, timing, concentration, geographic, or sanction-lag warning was detected."]
        for index, reasons in enumerate(all_reasons)
    ]
    return pd.DataFrame({"project_id": features["project_id"].astype("string"), RISK_SCORE_COLUMN: scores, REASONS_COLUMN: reason_text})


def score_projects(csv_path: str | Path | None = None) -> pd.DataFrame:
    """Build and score the synthetic project feature matrix using no evaluation labels."""
    features = build_feature_matrix() if csv_path is None else build_feature_matrix(csv_path)
    return score_feature_matrix(features)
