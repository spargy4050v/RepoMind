"""Standalone, label-after-scoring evaluation for MPLAD Trace anomaly detectors.

Run from the repository root with ``python test_anomaly_detection.py``. This
diagnostic uses calibrated synthetic Tier 2 labels only to evaluate already-fit
unsupervised models; labels never enter model fitting or feature construction.
"""

from __future__ import annotations

import os
from itertools import combinations
from pathlib import Path
from typing import Final

# Keep Matplotlib's cache in the repository output area in restricted local environments.
os.environ.setdefault("MPLCONFIGDIR", str(Path(__file__).resolve().parent / "eval_output" / ".matplotlib"))

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from backend.ml.anomaly_detection import fit_isolation_forest, fit_lof, score_batch, score_detector_batch
from backend.ml.features import DATASET_PATH, FEATURE_COLUMNS, build_feature_matrix


LABEL_COLUMN: Final[str] = "_ground_truth_is_anomalous"
OUTPUT_DIRECTORY: Final[Path] = Path(__file__).resolve().parent / "eval_output"
CONTAMINATION: Final[float] = 0.19
N_ESTIMATORS: Final[int] = 100
LOF_NEIGHBORS: Final[int] = 20
STABILITY_SEEDS: Final[tuple[int, ...]] = (11, 23, 37, 53, 71)
TOP_STABILITY_ROWS: Final[int] = 20
LOW_STABILITY_PERCENT: Final[float] = 70.0


def load_evaluation_data(dataset_path: Path = DATASET_PATH) -> tuple[pd.DataFrame, pd.Series]:
    """Build unlabeled model features and retain synthetic ground truth only for evaluation."""
    if not dataset_path.is_file():
        raise FileNotFoundError(f"Synthetic dataset was not found: {dataset_path}")
    source = pd.read_csv(dataset_path)
    if source.empty:
        raise ValueError("Synthetic dataset is empty; evaluation needs at least two rows.")
    if LABEL_COLUMN not in source.columns:
        raise ValueError(f"Synthetic dataset is missing evaluation-only column {LABEL_COLUMN!r}.")
    labels = source[LABEL_COLUMN]
    if labels.isna().any() or not labels.map(lambda value: isinstance(value, (bool, np.bool_))).all():
        raise ValueError(f"{LABEL_COLUMN!r} must contain boolean evaluation labels, not missing or string values.")
    labels = labels.astype(bool).rename("ground_truth_is_anomalous")
    if labels.nunique() < 2:
        raise ValueError("Evaluation labels must contain both normal and anomalous synthetic rows.")

    features = build_feature_matrix(dataset_path)
    if len(features) != len(labels) or not features["project_id"].eq(source["project_id"].astype("string")).all():
        raise ValueError("Feature rows do not align one-to-one with the source dataset rows.")
    return features.loc[:, FEATURE_COLUMNS], labels.reset_index(drop=True)


def classification_metrics(flags: pd.Series, labels: pd.Series) -> dict[str, float | int]:
    """Calculate review-queue metrics after scoring, never as an input to a detector."""
    predicted = flags.astype(bool).to_numpy()
    actual = labels.astype(bool).to_numpy()
    true_positive = int(np.sum(predicted & actual))
    false_positive = int(np.sum(predicted & ~actual))
    false_negative = int(np.sum(~predicted & actual))
    true_negative = int(np.sum(~predicted & ~actual))
    precision = true_positive / (true_positive + false_positive) if true_positive + false_positive else 0.0
    recall = true_positive / (true_positive + false_negative) if true_positive + false_negative else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "true_positive": true_positive,
        "false_positive": false_positive,
        "false_negative": false_negative,
        "true_negative": true_negative,
    }


def print_metrics(name: str, metrics: dict[str, float | int]) -> None:
    """Print a compact metric and confusion-matrix block for one detection signal."""
    print(f"\n{name}")
    print(f"  Precision: {float(metrics['precision']):.2%}")
    print(f"  Recall:    {float(metrics['recall']):.2%}")
    print(f"  F1:        {float(metrics['f1']):.3f}")
    print("  Confusion matrix (actual rows; predicted columns):")
    print(f"                 normal  anomalous")
    print(f"    normal       {int(metrics['true_negative']):4d}       {int(metrics['false_positive']):4d}")
    print(f"    anomalous    {int(metrics['false_negative']):4d}       {int(metrics['true_positive']):4d}")


def save_score_histogram(scores: pd.Series, labels: pd.Series, model_name: str, output_path: Path) -> None:
    """Save overlapping normal/anomalous score distributions to make rank separation reviewable."""
    figure, axis = plt.subplots(figsize=(9, 5))
    axis.hist(scores.loc[~labels], bins=30, alpha=0.65, label="Synthetic normal", color="#38bdf8")
    axis.hist(scores.loc[labels], bins=30, alpha=0.65, label="Synthetic anomalous", color="#f97316")
    axis.set_title(f"{model_name} anomaly-score distribution")
    axis.set_xlabel("Anomaly score (higher is more anomalous)")
    axis.set_ylabel("Project count")
    axis.legend()
    figure.tight_layout()
    figure.savefig(output_path, dpi=150)
    plt.close(figure)


def injected_fraud_rows(features: pd.DataFrame) -> pd.DataFrame:
    """Create five extreme rows using real cost, timing, concentration, and geo feature names."""
    if features.empty:
        raise ValueError("Cannot construct injection rows from an empty feature matrix.")
    injected = pd.DataFrame(
        [features.median(numeric_only=True).to_dict() for _ in range(5)],
        columns=FEATURE_COLUMNS,
    )
    for index in injected.index:
        multiplier = float(index + 1)
        injected.loc[index, "cost_ratio"] = 3.0 + multiplier
        injected.loc[index, "completion_speed_ratio"] = 0.04 * multiplier
        injected.loc[index, "payment_gap_days"] = -180.0 * multiplier
        injected.loc[index, "contractor_project_count"] = 150.0 + 25.0 * multiplier
        injected.loc[index, "contractor_constituency_share"] = min(0.55 + 0.08 * multiplier, 0.98)
        injected.loc[index, "geo_cluster_density"] = 20.0 + 5.0 * multiplier
        injected.loc[index, "sanction_lag_days"] = 180.0 + 30.0 * multiplier
    return injected.astype(float)


def injection_check(features: pd.DataFrame, contamination: float) -> tuple[pd.DataFrame, bool]:
    """Score deliberately extreme unseen rows and report whether both detectors flag each one."""
    forest = fit_isolation_forest(features, n_estimators=N_ESTIMATORS, contamination=contamination, random_state=26102)
    lof = fit_lof(features, n_neighbors=LOF_NEIGHBORS, contamination=contamination)
    injected_scores = score_batch(forest, lof, injected_fraud_rows(features))
    injected_scores.index = pd.Index(range(1, len(injected_scores) + 1), name="injected_row")
    passed = bool(injected_scores["isolation_forest_flag"].all() and injected_scores["lof_flag"].all())
    return injected_scores, passed


def normal_false_positive_rate(features: pd.DataFrame, labels: pd.Series, contamination: float) -> float:
    """Measure the actual review flag rate on a deterministic sample of labelled-normal rows."""
    normal_features = features.loc[~labels]
    if normal_features.empty:
        raise ValueError("False-positive check requires at least one labelled-normal synthetic row.")
    sample = normal_features.sample(n=min(500, len(normal_features)), random_state=26102)
    forest = fit_isolation_forest(features, n_estimators=N_ESTIMATORS, contamination=contamination, random_state=26102)
    flags = score_detector_batch(forest, sample)["flag"]
    return float(flags.mean())


def stability_overlap(features: pd.DataFrame, top_rows: int = TOP_STABILITY_ROWS) -> float:
    """Return mean pairwise Jaccard overlap of top Isolation Forest rows across five seeds."""
    if len(features) < top_rows:
        raise ValueError(f"Stability check needs at least {top_rows} feature rows.")
    top_sets: list[set[int]] = []
    for seed in STABILITY_SEEDS:
        forest = fit_isolation_forest(features, n_estimators=N_ESTIMATORS, contamination=CONTAMINATION, random_state=seed)
        scores = score_detector_batch(forest, features)["score"]
        top_sets.append(set(scores.nlargest(top_rows).index.tolist()))
    overlaps = [len(first & second) / len(first | second) for first, second in combinations(top_sets, 2)]
    return float(np.mean(overlaps) * 100.0)


def main() -> None:
    """Run all diagnostic checks and print a readable, evaluation-only report."""
    features, labels = load_evaluation_data()
    OUTPUT_DIRECTORY.mkdir(exist_ok=True)

    # Labels are intentionally absent from every fit call below.
    forest = fit_isolation_forest(features, n_estimators=N_ESTIMATORS, contamination=CONTAMINATION, random_state=26102)
    lof = fit_lof(features, n_neighbors=LOF_NEIGHBORS, contamination=CONTAMINATION)
    signals = score_batch(forest, lof, features)

    save_score_histogram(signals["isolation_forest_score"], labels, "Isolation Forest", OUTPUT_DIRECTORY / "isolation_forest_scores.png")
    save_score_histogram(signals["lof_score"], labels, "Local Outlier Factor", OUTPUT_DIRECTORY / "lof_scores.png")

    injected, injections_passed = injection_check(features, CONTAMINATION)
    false_positive_rate = normal_false_positive_rate(features, labels, CONTAMINATION)
    stability = stability_overlap(features)
    union_flagged = signals["isolation_forest_flag"] | signals["lof_flag"]
    union_count = int(union_flagged.sum())
    both_percent = float(signals.loc[union_flagged, "flagged_by_both"].mean() * 100.0) if union_count else 0.0
    forest_only_percent = float((signals["isolation_forest_flag"] & ~signals["lof_flag"]).sum() / union_count * 100.0) if union_count else 0.0
    lof_only_percent = float((~signals["isolation_forest_flag"] & signals["lof_flag"]).sum() / union_count * 100.0) if union_count else 0.0

    print("MPLAD Trace — Unsupervised Anomaly Detection Evaluation")
    print(f"Dataset: {len(features):,} calibrated synthetic Tier 2 rows; labels used only after scoring.")
    print(f"Configured contamination: {CONTAMINATION:.2%}")
    print_metrics("Isolation Forest", classification_metrics(signals["isolation_forest_flag"], labels))
    print_metrics("Local Outlier Factor", classification_metrics(signals["lof_flag"], labels))
    print_metrics("Flagged by both", classification_metrics(signals["flagged_by_both"], labels))
    print("\nInjection test (each detector must flag all five extreme unseen rows):")
    for row_number, row in injected.iterrows():
        result = "PASS" if bool(row["isolation_forest_flag"]) and bool(row["lof_flag"]) else "FAIL"
        print(f"  Row {row_number}: IF={bool(row['isolation_forest_flag'])}, LOF={bool(row['lof_flag'])} — {result}")
    print(f"  Overall: {'PASS' if injections_passed else 'FAIL'}")
    print(f"\nFalse-positive rate on up to 500 labelled-normal rows: {false_positive_rate:.2%} (configured contamination: {CONTAMINATION:.2%})")
    print(f"Stability: {stability:.1f}% mean pairwise top-{TOP_STABILITY_ROWS} Jaccard overlap — {'PASS' if stability >= LOW_STABILITY_PERCENT else 'LOW: investigate'}")
    print(f"Agreement among {union_count} rows flagged by either detector: both={both_percent:.1f}%, IF only={forest_only_percent:.1f}%, LOF only={lof_only_percent:.1f}%")
    print(f"Score-distribution plots: {OUTPUT_DIRECTORY / 'isolation_forest_scores.png'} and {OUTPUT_DIRECTORY / 'lof_scores.png'}")


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        raise RuntimeError(f"Anomaly-detection evaluation failed: {error}") from error
