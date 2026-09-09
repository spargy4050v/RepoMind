"""Inference-only scoring for one uploaded MPLAD scheme/project.

Models are loaded from a pre-trained local artifact. This module never fits on
uploaded data, and it rejects missing or non-finite feature values explicitly.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Final

import joblib
import numpy as np
import pandas as pd
import sklearn

from backend.ml.anomaly_detection import FittedAnomalyDetector, score_row
from backend.ml.features import FEATURE_COLUMNS, build_feature_matrix_from_frame


MODEL_PATH: Final[Path] = Path(__file__).resolve().parents[2] / "models" / "anomaly_detectors.pkl"
MAX_REASON_COUNT: Final[int] = 5
MODEL_BUNDLE_VERSION: Final[int] = 2


@dataclass(frozen=True)
class VerdictConfig:
    """Reviewer-facing verdict labels, kept configurable rather than embedded in scoring branches."""

    both_verdict: str = "Likely Fraudulent"
    one_verdict: str = "Suspicious"
    neither_verdict: str = "Likely Legitimate"
    both_confidence: str = "High"
    one_confidence: str = "Medium"
    neither_confidence: str = "High"
    max_reasons: int = MAX_REASON_COUNT


DEFAULT_VERDICT_CONFIG: Final[VerdictConfig] = VerdictConfig()


@dataclass(frozen=True)
class ModelBundle:
    """Saved detectors plus unlabeled training distribution statistics used for explanations."""

    isolation_forest: FittedAnomalyDetector
    lof: FittedAnomalyDetector
    feature_columns: tuple[str, ...]
    training_mean: dict[str, float]
    training_std: dict[str, float]
    training_min: dict[str, float]
    training_max: dict[str, float]
    training_values: dict[str, list[float]]
    training_context: pd.DataFrame | None
    bundle_version: int
    sklearn_version: str


def save_model_bundle(
    isolation_forest: FittedAnomalyDetector,
    lof: FittedAnomalyDetector,
    training_features: pd.DataFrame,
    model_path: Path = MODEL_PATH,
    training_context: pd.DataFrame | None = None,
) -> None:
    """Persist detectors, feature statistics, and optional unlabeled project context for inference."""
    _validate_feature_frame(training_features)
    values = training_features.loc[:, FEATURE_COLUMNS]
    bundle = ModelBundle(
        isolation_forest=isolation_forest,
        lof=lof,
        feature_columns=FEATURE_COLUMNS,
        training_mean={column: float(values[column].mean()) for column in FEATURE_COLUMNS},
        training_std={column: float(values[column].std(ddof=0)) for column in FEATURE_COLUMNS},
        training_min={column: float(values[column].min()) for column in FEATURE_COLUMNS},
        training_max={column: float(values[column].max()) for column in FEATURE_COLUMNS},
        training_values={column: values[column].astype(float).tolist() for column in FEATURE_COLUMNS},
        training_context=training_context.copy() if training_context is not None else None,
        bundle_version=MODEL_BUNDLE_VERSION,
        sklearn_version=sklearn.__version__,
    )
    model_path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(bundle, model_path)


def load_model_bundle(model_path: Path = MODEL_PATH) -> ModelBundle:
    """Load a previously trained artifact or clearly require the offline training step."""
    if not model_path.is_file():
        raise FileNotFoundError(f"No saved anomaly models at {model_path}. Train models first with python -m backend.ml.train_models.")
    try:
        bundle = joblib.load(model_path)
    except Exception as error:
        raise ValueError(f"Could not load saved anomaly models from {model_path}: {error}") from error
    if not isinstance(bundle, ModelBundle) or bundle.feature_columns != FEATURE_COLUMNS or bundle.bundle_version != MODEL_BUNDLE_VERSION:
        raise ValueError("Saved model artifact is invalid, stale, or was trained for a different feature schema. Retrain models first.")
    if bundle.sklearn_version != sklearn.__version__:
        raise ValueError(f"Saved model uses scikit-learn {bundle.sklearn_version}, but this environment uses {sklearn.__version__}. Retrain models first.")
    return bundle


def _as_one_row_frame(input_data: dict[str, object] | pd.DataFrame) -> pd.DataFrame:
    """Accept one JSON-like object or exactly one CSV/DataFrame row for inference."""
    if isinstance(input_data, dict):
        frame = pd.DataFrame([input_data])
    elif isinstance(input_data, pd.DataFrame):
        frame = input_data.copy()
    else:
        raise TypeError("input_data must be a dict or a pandas DataFrame containing exactly one row.")
    if len(frame) != 1:
        raise ValueError(f"Uploaded input must contain exactly one row; received {len(frame)} rows.")
    return frame


def _validate_feature_frame(features: pd.DataFrame) -> None:
    """Reject absent, NaN, and infinite feature values rather than silently imputing uploads."""
    missing = [column for column in FEATURE_COLUMNS if column not in features.columns]
    if missing:
        raise ValueError(f"Uploaded scheme is missing required feature columns: {', '.join(missing)}")
    values = features.loc[:, FEATURE_COLUMNS].apply(pd.to_numeric, errors="coerce")
    invalid = [column for column in FEATURE_COLUMNS if not np.isfinite(values[column].to_numpy(dtype=float)).all()]
    if invalid:
        raise ValueError(f"Uploaded scheme has missing, non-numeric, or non-finite values for: {', '.join(invalid)}")


def _validate_raw_project_frame(frame: pd.DataFrame) -> None:
    """Reject malformed raw uploads before feature engineering could silently impute them.

    A raw upload must be complete and parseable: invalid dates, amounts, or
    coordinates must be reported to the user rather than becoming zero-valued
    model features.
    """
    required = {
        "project_id", "sanctioned_cost_inr", "regional_baseline_cost_inr", "start_date",
        "completion_certified_date", "fund_release_date", "planned_duration_days", "contractor_id",
        "mp_constituency", "recommended_date", "sanction_date", "latitude", "longitude",
    }
    missing = sorted(required.difference(frame.columns))
    if missing:
        raise ValueError(f"Raw uploaded scheme is missing required fields: {', '.join(missing)}")
    null_columns = sorted(column for column in required if frame[column].isna().any() or frame[column].astype("string").str.strip().eq("").any())
    if null_columns:
        raise ValueError(f"Raw uploaded scheme has missing values for: {', '.join(null_columns)}")
    numeric_columns = (
        "sanctioned_cost_inr", "regional_baseline_cost_inr", "planned_duration_days", "latitude", "longitude",
    )
    numeric = frame.loc[:, numeric_columns].apply(pd.to_numeric, errors="coerce")
    invalid_numeric = [
        column for column in numeric_columns
        if not np.isfinite(numeric[column].to_numpy(dtype=float)).all()
    ]
    if invalid_numeric:
        raise ValueError(f"Raw uploaded scheme has non-numeric or non-finite values for: {', '.join(invalid_numeric)}")
    non_positive = [
        column for column in ("regional_baseline_cost_inr", "planned_duration_days")
        if (numeric[column] <= 0).any()
    ]
    if non_positive:
        raise ValueError(f"Raw uploaded scheme requires positive values for: {', '.join(non_positive)}")
    if (numeric["sanctioned_cost_inr"] < 0).any():
        raise ValueError("Raw uploaded scheme requires a non-negative sanctioned_cost_inr")
    if not numeric["latitude"].between(-90, 90).all() or not numeric["longitude"].between(-180, 180).all():
        raise ValueError("Raw uploaded scheme has latitude/longitude outside valid geographic bounds")
    date_columns = ("recommended_date", "sanction_date", "start_date", "completion_certified_date", "fund_release_date")
    parsed_dates = frame.loc[:, date_columns].apply(pd.to_datetime, errors="coerce")
    invalid_dates = [column for column in date_columns if parsed_dates[column].isna().any()]
    if invalid_dates:
        raise ValueError(f"Raw uploaded scheme has invalid dates for: {', '.join(invalid_dates)}")


def _prepare_features(frame: pd.DataFrame, bundle: ModelBundle) -> pd.DataFrame:
    """Build upload features against the saved unlabeled portfolio context.

    Raw records are appended to the label-free training portfolio before using
    the same batch feature builder as model training. This preserves contractor
    history, constituency concentration, and 2 km geographic density instead
    of manufacturing one-record defaults.
    """
    supplied_features = [column for column in FEATURE_COLUMNS if column in frame.columns]
    if supplied_features:
        _validate_feature_frame(frame)
        features = frame.loc[:, FEATURE_COLUMNS].copy()
    else:
        raw = frame.copy()
        _validate_raw_project_frame(raw)
        if bundle.training_context is None:
            raise ValueError("Saved models lack project context for raw-record feature engineering. Retrain models first or upload all engineered feature columns.")
        if raw["project_id"].isin(bundle.training_context["project_id"]).any():
            raise ValueError("Uploaded raw project_id already exists in the training context; upload engineered features to rescore it.")
        context = bundle.training_context.loc[:, [column for column in bundle.training_context.columns if not column.startswith("_ground_truth_")]]
        combined = pd.concat([context, raw], ignore_index=True, sort=False)
        features = build_feature_matrix_from_frame(combined).tail(1).loc[:, FEATURE_COLUMNS]
    _validate_feature_frame(features)
    return features.apply(pd.to_numeric, errors="raise").astype(float)


def _feature_reason(column: str, value: float, bundle: ModelBundle) -> str:
    """Translate a feature's distance from its unlabeled training distribution into reviewable plain language."""
    values = np.asarray(bundle.training_values[column], dtype=float)
    percentile = float((values <= value).mean() * 100.0)
    direction = "highest" if percentile >= 50 else "lowest"
    tail = 100.0 - percentile if percentile >= 50 else percentile
    labels = {
        "cost_ratio": f"Cost ratio of {value:.2f}x",
        "completion_speed_ratio": f"Completion-speed ratio of {value:.2f}x",
        "payment_gap_days": f"Payment gap of {value:.0f} days",
        "contractor_project_count": f"Contractor project count of {value:.0f}",
        "contractor_constituency_share": f"Contractor constituency share of {value:.0%}",
        "geo_cluster_density": f"Geographic cluster density of {value:.0f} nearby projects",
        "sanction_lag_days": f"Sanction lag of {value:.0f} days",
    }
    return f"{labels[column]} is in the {direction} {max(tail, 100.0 / len(values)):.1f}% of training projects."


def _distribution_reasons(features: pd.DataFrame, bundle: ModelBundle, limit: int) -> tuple[list[str], list[str]]:
    """Select the most unusual 3--5 values and identify valid values beyond observed training ranges."""
    row = features.iloc[0]
    distances: list[tuple[str, float]] = []
    quality_issues: list[str] = []
    for column in FEATURE_COLUMNS:
        value = float(row[column])
        std = bundle.training_std[column]
        distance = abs(value - bundle.training_mean[column]) / std if std > 0 else 0.0
        distances.append((column, distance))
        if value < bundle.training_min[column] or value > bundle.training_max[column]:
            quality_issues.append(f"{column} ({value:.4g}) lies outside the training range [{bundle.training_min[column]:.4g}, {bundle.training_max[column]:.4g}].")
    if float(row["cost_ratio"]) < 0:
        quality_issues.append("cost_ratio is negative; sanctioned cost and baseline inputs require data-quality review.")
    if float(row["completion_speed_ratio"]) < 0:
        quality_issues.append("completion_speed_ratio is negative; source dates or duration require data-quality review.")
    if float(row["contractor_constituency_share"]) < 0 or float(row["contractor_constituency_share"]) > 1:
        quality_issues.append("contractor_constituency_share is outside 0--1 and requires data-quality review.")
    selected = sorted(distances, key=lambda item: item[1], reverse=True)[: min(3, limit)]
    return ([_feature_reason(column, float(row[column]), bundle) for column, _ in selected], quality_issues)


def score_uploaded_scheme(
    input_data: dict[str, object] | pd.DataFrame,
    *,
    model_path: Path = MODEL_PATH,
    verdict_config: VerdictConfig = DEFAULT_VERDICT_CONFIG,
) -> dict[str, object]:
    """Load pre-trained models and return an explainable fraud-review verdict for one uploaded scheme.

    Feature-ready uploads must supply all seven ``FEATURE_COLUMNS``. Raw
    records are appended to the saved unlabeled portfolio and passed through
    the shared batch feature builder, so contextual features use real portfolio
    history without ever reading evaluation-only ground-truth fields.
    """
    bundle = load_model_bundle(model_path)
    features = _prepare_features(_as_one_row_frame(input_data), bundle)
    signal = score_row(bundle.isolation_forest, bundle.lof, features.iloc[0])
    if bool(signal["flagged_by_both"]):
        verdict, confidence = verdict_config.both_verdict, verdict_config.both_confidence
    elif bool(signal["isolation_forest_flag"]) or bool(signal["lof_flag"]):
        verdict, confidence = verdict_config.one_verdict, verdict_config.one_confidence
    else:
        verdict, confidence = verdict_config.neither_verdict, verdict_config.neither_confidence
    reasons, quality_issues = _distribution_reasons(features, bundle, verdict_config.max_reasons)
    if bool(signal["isolation_forest_flag"]) or bool(signal["lof_flag"]):
        reasons.insert(0, str(signal["reason"]))
    for issue in quality_issues:
        if len(reasons) >= verdict_config.max_reasons:
            break
        reasons.append(f"Data-quality review: {issue}")
    return {
        **signal,
        "verdict": verdict,
        "confidence": confidence,
        "reasons": reasons[: verdict_config.max_reasons],
        "data_quality_issues": quality_issues,
        "feature_values": {column: float(features.iloc[0][column]) for column in FEATURE_COLUMNS},
    }


def main() -> None:
    """Provide the requested one-row CSV inference command-line entry point."""
    parser = argparse.ArgumentParser(description="Score one uploaded MPLAD scheme against saved anomaly models.")
    parser.add_argument("csv_path", type=Path, help="CSV file containing exactly one uploaded project row")
    parser.add_argument("--model-path", type=Path, default=MODEL_PATH, help="Path to the pre-trained .pkl artifact")
    args = parser.parse_args()
    if not args.csv_path.is_file():
        raise FileNotFoundError(f"Upload CSV was not found: {args.csv_path}")
    print(json.dumps(score_uploaded_scheme(pd.read_csv(args.csv_path, encoding="utf-8"), model_path=args.model_path), indent=2))


if __name__ == "__main__":
    main()
