"""Regression and evaluation tests for the Module 3 explainable scorer."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from backend.ml.features import FEATURE_COLUMNS, build_feature_matrix
from backend.ml.scorer import REASONS_COLUMN, RISK_SCORE_COLUMN, score_feature_matrix, score_projects


ROOT = Path(__file__).resolve().parents[1]
DATASET = ROOT / "data" / "mplad_projects.csv"


def test_scorer_returns_bounded_scores_and_specific_reasons() -> None:
    """Every project needs a reviewable 0--100 score and non-empty explanation."""
    scored = score_projects(str(DATASET))
    assert list(scored.columns) == ["project_id", RISK_SCORE_COLUMN, REASONS_COLUMN]
    assert scored[RISK_SCORE_COLUMN].between(0, 100).all()
    assert scored[REASONS_COLUMN].map(lambda reasons: isinstance(reasons, list) and len(reasons) > 0).all()


def test_ground_truth_columns_cannot_be_used_as_scorer_input() -> None:
    """The scorer's strict Module 2 matrix contract prevents label leakage."""
    source = pd.read_csv(DATASET)
    with np.testing.assert_raises(ValueError):
        score_feature_matrix(source)
    features = build_feature_matrix(DATASET)
    assert not any(column.startswith("_ground_truth_") for column in features.columns)


def test_hidden_labels_evaluate_high_precision_and_recall_at_top_twenty_percent() -> None:
    """Evaluate only after scoring: labels never enter feature construction or scoring."""
    source = pd.read_csv(DATASET, usecols=["project_id", "_ground_truth_is_anomalous"])
    scored = score_projects(str(DATASET))
    evaluated = scored.merge(source, on="project_id", validate="one_to_one").sort_values(RISK_SCORE_COLUMN, ascending=False)
    top = evaluated.head(int(np.ceil(len(evaluated) * 0.20)))
    positives = evaluated["_ground_truth_is_anomalous"].astype(bool)
    precision_at_20 = top["_ground_truth_is_anomalous"].astype(bool).mean()
    recall_at_20 = top["_ground_truth_is_anomalous"].astype(bool).sum() / positives.sum()
    # The deliberately ambiguous collusion cohort labels only half of an
    # otherwise identical contractor/constituency pattern as anomalous.  These
    # thresholds therefore validate useful prioritisation without pretending
    # the hidden labels are perfectly separable from the permitted features.
    assert precision_at_20 >= 0.75
    assert recall_at_20 >= 0.80
