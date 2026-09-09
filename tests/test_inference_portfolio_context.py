"""Regression coverage for raw upload features that require portfolio context."""

from __future__ import annotations

from pathlib import Path

from backend.ml.anomaly_detection import fit_isolation_forest, fit_lof
from backend.ml.features import FEATURE_COLUMNS, build_feature_matrix, load_project_data
from backend.ml.inference import save_model_bundle, score_uploaded_scheme


ROOT = Path(__file__).resolve().parents[1]
DATASET = ROOT / "data" / "mplad_projects.csv"


def test_raw_upload_uses_existing_contractor_and_geographic_portfolio_context(tmp_path: Path) -> None:
    """A raw record inherits its contractor's portfolio counts instead of isolated one-row defaults."""
    source = load_project_data(DATASET)
    features = build_feature_matrix(DATASET)
    candidate = features.loc[features["contractor_project_count"] > 1].sort_values(
        "contractor_project_count", ascending=False
    ).iloc[0]
    raw = source.loc[source["project_id"] == candidate["project_id"]].iloc[0].drop(
        labels=["_ground_truth_is_anomalous", "_ground_truth_anomaly_type"]
    ).to_dict()
    raw["project_id"] = "UPLOADED-PORTFOLIO-CONTEXT"
    model_path = tmp_path / "anomaly_detectors.pkl"
    context = source.loc[:, [column for column in source.columns if not column.startswith("_ground_truth_")]]
    feature_values = features.loc[:, FEATURE_COLUMNS]
    save_model_bundle(fit_isolation_forest(feature_values), fit_lof(feature_values), feature_values, model_path, training_context=context)

    result = score_uploaded_scheme(raw, model_path=model_path)

    expected = build_feature_matrix_from_uploaded_context(context, raw)
    assert result["feature_values"]["contractor_project_count"] == expected["contractor_project_count"]
    assert result["feature_values"]["contractor_project_count"] > 1
    assert result["feature_values"]["contractor_constituency_share"] == expected["contractor_constituency_share"]
    assert result["feature_values"]["geo_cluster_density"] == expected["geo_cluster_density"]


def build_feature_matrix_from_uploaded_context(context, raw):
    """Calculate the expected row through the production shared batch feature builder."""
    from backend.ml.features import build_feature_matrix_from_frame
    import pandas as pd

    return build_feature_matrix_from_frame(pd.concat([context, pd.DataFrame([raw])], ignore_index=True)).iloc[-1]
