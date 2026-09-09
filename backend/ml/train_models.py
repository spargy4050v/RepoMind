"""Explicit offline training command for the persisted MPLAD Trace anomaly models."""

from __future__ import annotations

import argparse
from pathlib import Path

from backend.ml.anomaly_detection import fit_isolation_forest, fit_lof
from backend.ml.features import DATASET_PATH, FEATURE_COLUMNS, build_feature_matrix, load_project_data
from backend.ml.inference import MODEL_PATH, save_model_bundle


def main() -> None:
    """Train only on the local unlabeled feature matrix and save a reusable model artifact."""
    parser = argparse.ArgumentParser(description="Explicitly train and save MPLAD Trace anomaly models.")
    parser.add_argument("--dataset", type=Path, default=DATASET_PATH)
    parser.add_argument("--output", type=Path, default=MODEL_PATH)
    args = parser.parse_args()
    source = load_project_data(args.dataset)
    features = build_feature_matrix(args.dataset).loc[:, FEATURE_COLUMNS]
    isolation_forest = fit_isolation_forest(features)
    lof = fit_lof(features)
    context = source.loc[:, [column for column in source.columns if not column.startswith("_ground_truth_")]]
    save_model_bundle(isolation_forest, lof, features, args.output, training_context=context)
    print(f"Saved unlabeled Isolation Forest and LOF models for {len(features)} synthetic Tier 2 projects to {args.output}")


if __name__ == "__main__":
    main()
