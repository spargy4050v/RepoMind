"""Unit tests for the scikit-learn anomaly detector wrappers."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from backend.ml.anomaly_detection import fit_isolation_forest, fit_lof, score_batch, score_detector_batch, score_row


def _synthetic_features() -> pd.DataFrame:
    """Create an unlabeled feature set with one deliberately distant observation."""
    rng = np.random.default_rng(26102)
    inliers = rng.normal(0.0, 0.25, size=(30, 3))
    return pd.DataFrame(np.vstack((inliers, [[7.0, 7.0, 7.0]])), columns=["first", "second", "third"])


def test_models_fit_and_expose_flag_and_continuous_scores() -> None:
    """Both unsupervised models score rows without labels or runtime errors."""
    features = _synthetic_features()
    forest = fit_isolation_forest(features, n_estimators=25, contamination=0.1, random_state=7)
    lof = fit_lof(features, n_neighbors=5, contamination=0.1)

    forest_scores = score_detector_batch(forest, features)
    lof_scores = score_detector_batch(lof, features)
    assert list(forest_scores.columns) == ["flag", "score"]
    assert list(lof_scores.columns) == ["flag", "score"]
    assert forest_scores["flag"].dtype == bool
    assert lof_scores["score"].map(np.isfinite).all()
    assert isinstance(score_row(forest, lof, features.iloc[0])["isolation_forest_score"], float)


def test_combined_signal_reports_detector_agreement_and_reason() -> None:
    """The agreement layer emits the documented structured, human-readable result."""
    features = _synthetic_features()
    forest = fit_isolation_forest(features, n_estimators=25, contamination=0.1, random_state=7)
    lof = fit_lof(features, n_neighbors=5, contamination=0.1)
    combined = score_batch(forest, lof, features)

    assert list(combined.columns) == [
        "isolation_forest_flag", "isolation_forest_score", "lof_flag", "lof_score", "flagged_by_both", "reason",
    ]
    assert combined["reason"].str.len().gt(0).all()
    assert (combined["flagged_by_both"] == (combined["isolation_forest_flag"] & combined["lof_flag"])).all()


def test_detector_rejects_wrong_feature_width_with_a_clear_error() -> None:
    """Saved scalers cannot silently score a row with a stale feature schema."""
    features = _synthetic_features()
    forest = fit_isolation_forest(features, n_estimators=10, random_state=7)
    with pytest.raises(ValueError, match="expects 3"):
        score_detector_batch(forest, features.iloc[:, :2])
