"""Focused regression tests for the completed synthetic-data and feature-engineering modules."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from backend.ml.features import FEATURE_COLUMNS, build_feature_matrix


ROOT = Path(__file__).resolve().parents[1]
DATASET = ROOT / "data" / "mplad_projects.csv"


def test_synthetic_dataset_size_and_anomaly_rate_are_preserved() -> None:
    """Guard the fixed Module 1 dataset contract required for later evaluation."""
    source = pd.read_csv(DATASET)
    assert len(source) == 3_000
    assert source["_ground_truth_is_anomalous"].astype(bool).mean() == 0.19


def test_feature_matrix_is_finite_and_contains_exactly_the_seven_features() -> None:
    """Invalid source values must not turn Module 2 output into NaN or infinity."""
    features = build_feature_matrix(DATASET)
    assert list(features.columns) == ["project_id", *FEATURE_COLUMNS]
    assert len(features) == 3_000
    assert np.isfinite(features.loc[:, FEATURE_COLUMNS].to_numpy(dtype=float)).all()


def test_known_cost_and_payment_anomalies_have_extreme_signals() -> None:
    """Validate the injected cost-inflation and payment-before-completion signals directly."""
    source = pd.read_csv(DATASET)
    features = build_feature_matrix(DATASET).set_index("project_id")
    cost_ids = source.loc[source["_ground_truth_anomaly_type"] == "cost_inflation", "project_id"]
    payment_ids = source.loc[source["_ground_truth_anomaly_type"] == "payment_timing", "project_id"]
    assert (features.loc[cost_ids, "cost_ratio"] > 1.8).all()
    assert (features.loc[payment_ids, "payment_gap_days"] < 0).all()


def test_ground_truth_columns_never_enter_feature_matrix() -> None:
    """Prevent evaluation labels leaking into any model/scoring input later."""
    features = build_feature_matrix(DATASET)
    assert not any(column.startswith("_ground_truth_") for column in features.columns)


def test_invalid_inputs_are_coerced_to_finite_feature_values(tmp_path: Path) -> None:
    """Division, date parsing, and numeric coercion failures must not poison the full matrix."""
    dirty = pd.read_csv(DATASET).head(3).copy()
    dirty.loc[0, "regional_baseline_cost_inr"] = 0
    dirty.loc[1, "recommended_date"] = "not-a-date"
    dirty.loc[1, "completion_certified_date"] = "not-a-date"
    dirty.loc[2, "sanctioned_cost_inr"] = np.inf
    dirty.loc[2, "latitude"] = np.nan
    dirty_path = tmp_path / "dirty_projects.csv"
    dirty.to_csv(dirty_path, index=False)

    features = build_feature_matrix(dirty_path)
    assert np.isfinite(features.loc[:, FEATURE_COLUMNS].to_numpy(dtype=float)).all()
