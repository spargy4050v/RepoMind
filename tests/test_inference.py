"""Examples proving saved-model uploaded-scheme inference stays inference-only."""

from __future__ import annotations

from pathlib import Path

from backend.ml.anomaly_detection import fit_isolation_forest, fit_lof
from backend.ml.features import FEATURE_COLUMNS, build_feature_matrix, load_project_data
from backend.ml.inference import save_model_bundle, score_uploaded_scheme


ROOT = Path(__file__).resolve().parents[1]
DATASET = ROOT / "data" / "mplad_projects.csv"


def _saved_models(tmp_path: Path) -> tuple[Path, object]:
    """Create an explicit local training artifact for isolated inference examples."""
    features = build_feature_matrix(DATASET).loc[:, FEATURE_COLUMNS]
    model_path = tmp_path / "anomaly_detectors.pkl"
    source = load_project_data(DATASET)
    context = source.loc[:, [column for column in source.columns if not column.startswith("_ground_truth_")]]
    save_model_bundle(fit_isolation_forest(features), fit_lof(features), features, model_path, training_context=context)
    return model_path, features


def test_clearly_fraudulent_upload_has_explainable_high_confidence_verdict(tmp_path: Path) -> None:
    """An extreme feature-ready upload is scored from saved models without retraining."""
    model_path, features = _saved_models(tmp_path)
    uploaded = features.median().to_dict()
    uploaded.update({
        "cost_ratio": 8.0,
        "completion_speed_ratio": 0.04,
        "payment_gap_days": -900.0,
        "contractor_project_count": 400.0,
        "contractor_constituency_share": 0.98,
        "geo_cluster_density": 50.0,
        "sanction_lag_days": 500.0,
    })

    result = score_uploaded_scheme(uploaded, model_path=model_path)
    assert result["verdict"] == "Likely Fraudulent"
    assert result["confidence"] == "High"
    assert result["flagged_by_both"] is True
    assert result["reasons"]
    assert result["data_quality_issues"]


def test_normal_upload_returns_complete_inference_response(tmp_path: Path) -> None:
    """A typical feature-ready upload returns verdict, confidence, flags, scores, and readable reasons."""
    model_path, features = _saved_models(tmp_path)
    result = score_uploaded_scheme(features.iloc[0].to_dict(), model_path=model_path)

    assert {"isolation_forest_flag", "isolation_forest_score", "lof_flag", "lof_score", "flagged_by_both", "verdict", "confidence", "reasons"}.issubset(result)
    assert isinstance(result["reasons"], list)
    assert 1 <= len(result["reasons"]) <= 5


def test_partial_feature_upload_names_the_missing_columns(tmp_path: Path) -> None:
    """Feature-ready uploads cannot silently default omitted model inputs."""
    model_path, _ = _saved_models(tmp_path)
    try:
        score_uploaded_scheme({"cost_ratio": 1.0}, model_path=model_path)
    except ValueError as error:
        assert "completion_speed_ratio" in str(error)
        assert "payment_gap_days" in str(error)
    else:
        raise AssertionError("A partial engineered-feature upload must be rejected.")


def test_raw_upload_reuses_training_context_for_contextual_features(tmp_path: Path) -> None:
    """Raw uploads use the stored unlabeled project context instead of one-row density defaults."""
    model_path, _ = _saved_models(tmp_path)
    raw = load_project_data(DATASET).iloc[0].drop(labels=["_ground_truth_is_anomalous", "_ground_truth_anomaly_type"]).to_dict()
    raw["project_id"] = "UPLOADED-CONTEXT-CHECK"
    result = score_uploaded_scheme(raw, model_path=model_path)
    assert result["verdict"] in {"Likely Fraudulent", "Suspicious", "Likely Legitimate"}


def test_raw_upload_rejects_malformed_values_instead_of_imputing_them(tmp_path: Path) -> None:
    """Invalid raw amounts must not become zero-valued model inputs."""
    model_path, _ = _saved_models(tmp_path)
    raw = load_project_data(DATASET).iloc[0].drop(labels=["_ground_truth_is_anomalous", "_ground_truth_anomaly_type"]).to_dict()
    raw["project_id"] = "UPLOADED-MALFORMED-CHECK"
    raw["sanctioned_cost_inr"] = "not-a-number"
    try:
        score_uploaded_scheme(raw, model_path=model_path)
    except ValueError as error:
        assert "sanctioned_cost_inr" in str(error)
    else:
        raise AssertionError("Malformed raw amounts must be rejected before scoring.")
