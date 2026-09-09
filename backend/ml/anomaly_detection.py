"""Unsupervised anomaly-model signals for the MPLAD Trace feature matrix.

Both detectors use only the seven engineered numerical features.  They do not
accept project labels or any ``_ground_truth_*`` values, which keeps them safe
to use in the live synthetic Tier 2 scoring pipeline.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, TypeAlias

import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest
from sklearn.neighbors import LocalOutlierFactor
from sklearn.preprocessing import StandardScaler


Contamination: TypeAlias = Literal["auto"] | float
DetectorEstimator: TypeAlias = IsolationForest | LocalOutlierFactor


@dataclass(frozen=True)
class FittedAnomalyDetector:
    """A fitted detector and its feature scaling learned only from training rows."""

    estimator: DetectorEstimator
    scaler: StandardScaler


def _feature_values(features: pd.DataFrame | np.ndarray) -> np.ndarray:
    """Validate a finite, unlabeled feature matrix before it reaches either detector."""
    values = features.to_numpy(dtype=float) if isinstance(features, pd.DataFrame) else np.asarray(features, dtype=float)
    if values.ndim != 2 or not len(values):
        raise ValueError("features must be a non-empty two-dimensional matrix")
    if not np.isfinite(values).all():
        raise ValueError("features must be finite before anomaly detection")
    return values


def _validate_contamination(contamination: Contamination) -> None:
    """Reject unsupported contamination settings before scikit-learn raises an opaque fit error."""
    if contamination == "auto":
        return
    if not isinstance(contamination, (float, int)) or not 0.0 < float(contamination) <= 0.5:
        raise ValueError("contamination must be 'auto' or a float in the interval (0, 0.5]")


def _fit_scaler(features: pd.DataFrame | np.ndarray) -> tuple[np.ndarray, StandardScaler]:
    """Standardise features so LOF distances are not dominated by currency or day units."""
    values = _feature_values(features)
    scaler = StandardScaler()
    return scaler.fit_transform(values), scaler


def fit_isolation_forest(
    features: pd.DataFrame | np.ndarray,
    *,
    n_estimators: int = 100,
    contamination: Contamination = "auto",
    random_state: int | None = 26102,
) -> FittedAnomalyDetector:
    """Fit the primary Isolation Forest on unlabeled project features.

    Isolation Forest flags records isolated by unusually short random-partition
    paths, which can reveal unusual combinations beyond explicit fraud rules.
    """
    if n_estimators < 1:
        raise ValueError("n_estimators must be at least 1")
    _validate_contamination(contamination)
    scaled, scaler = _fit_scaler(features)
    estimator = IsolationForest(
        n_estimators=n_estimators,
        contamination=contamination,
        random_state=random_state,
    ).fit(scaled)
    return FittedAnomalyDetector(estimator=estimator, scaler=scaler)


def fit_lof(
    features: pd.DataFrame | np.ndarray,
    *,
    n_neighbors: int = 20,
    contamination: Contamination = "auto",
) -> FittedAnomalyDetector:
    """Fit novelty-enabled LOF as a neighborhood-based anomaly cross-check.

    LOF flags a project whose local density is unusually low relative to its
    neighbours, catching isolated records that may not have short tree paths.
    """
    values = _feature_values(features)
    if len(values) < 2:
        raise ValueError("LOF requires at least two feature rows")
    if n_neighbors < 1:
        raise ValueError("n_neighbors must be at least 1")
    _validate_contamination(contamination)
    scaler = StandardScaler()
    scaled = scaler.fit_transform(values)
    effective_neighbors = min(n_neighbors, len(values) - 1)
    estimator = LocalOutlierFactor(
        n_neighbors=effective_neighbors,
        contamination=contamination,
        novelty=True,
    ).fit(scaled)
    return FittedAnomalyDetector(estimator=estimator, scaler=scaler)


def score_detector_batch(detector: FittedAnomalyDetector, features: pd.DataFrame | np.ndarray) -> pd.DataFrame:
    """Return a detector's boolean review flag and continuous higher-is-riskier score.

    ``decision_function`` is negated because scikit-learn gives inliers larger
    values; this preserves a consistent score direction for ranking.
    """
    values = _feature_values(features)
    expected_width = int(detector.scaler.n_features_in_)
    if values.shape[1] != expected_width:
        raise ValueError(f"features have {values.shape[1]} columns, but the fitted detector expects {expected_width}")
    scaled = detector.scaler.transform(values)
    flags = detector.estimator.predict(scaled) == -1
    scores = -detector.estimator.decision_function(scaled)
    return pd.DataFrame({"flag": flags.astype(bool), "score": scores.astype(float)})


def score_detector_row(detector: FittedAnomalyDetector, row: pd.Series | np.ndarray) -> dict[str, bool | float]:
    """Score one unseen project row with the same flag-and-continuous-score interface."""
    values = row.to_numpy(dtype=float) if isinstance(row, pd.Series) else np.asarray(row, dtype=float)
    if values.ndim != 1:
        raise ValueError("row must be one-dimensional")
    result = score_detector_batch(detector, values.reshape(1, -1)).iloc[0]
    return {"flag": bool(result["flag"]), "score": float(result["score"])}


def score_combined_batch(
    isolation_forest: FittedAnomalyDetector,
    lof: FittedAnomalyDetector,
    features: pd.DataFrame | np.ndarray,
) -> pd.DataFrame:
    """Cross-check both unlabeled detectors and attach a reviewer-readable reason.

    Agreement is a higher-confidence signal because both random isolation and
    local-neighbourhood density independently identify the same unusual record.
    """
    forest = score_detector_batch(isolation_forest, features)
    neighbourhood = score_detector_batch(lof, features)
    both = forest["flag"] & neighbourhood["flag"]
    reasons = np.select(
        [both, forest["flag"], neighbourhood["flag"]],
        [
            "Flagged by both isolation-based and neighborhood-based detection.",
            "Flagged by isolation-based detection; neighborhood cross-check did not flag it.",
            "Flagged by neighborhood-based detection; isolation-based cross-check did not flag it.",
        ],
        default="Neither unsupervised detector flagged this project.",
    )
    return pd.DataFrame(
        {
            "isolation_forest_flag": forest["flag"].astype(bool),
            "isolation_forest_score": forest["score"].astype(float),
            "lof_flag": neighbourhood["flag"].astype(bool),
            "lof_score": neighbourhood["score"].astype(float),
            "flagged_by_both": both.astype(bool),
            "reason": reasons,
        }
    )


def score_batch(
    isolation_forest: FittedAnomalyDetector,
    lof: FittedAnomalyDetector,
    features: pd.DataFrame | np.ndarray,
) -> pd.DataFrame:
    """Score a dataset with both models using the documented combined-signal interface."""
    return score_combined_batch(isolation_forest, lof, features)


def score_row(
    isolation_forest: FittedAnomalyDetector,
    lof: FittedAnomalyDetector,
    row: pd.Series | np.ndarray,
) -> dict[str, bool | float | str]:
    """Score one project with both detectors and return its complete reason-layer result."""
    values = row.to_numpy(dtype=float) if isinstance(row, pd.Series) else np.asarray(row, dtype=float)
    if values.ndim != 1:
        raise ValueError("row must be one-dimensional")
    result = score_batch(isolation_forest, lof, values.reshape(1, -1)).iloc[0]
    return {
        "isolation_forest_flag": bool(result["isolation_forest_flag"]),
        "isolation_forest_score": float(result["isolation_forest_score"]),
        "lof_flag": bool(result["lof_flag"]),
        "lof_score": float(result["lof_score"]),
        "flagged_by_both": bool(result["flagged_by_both"]),
        "reason": str(result["reason"]),
    }
