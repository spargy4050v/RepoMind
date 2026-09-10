"""Verify the local PostGIS path for MPLAD Trace's synthetic Tier 2 data.

Working Docker command (verified 2026-09-10):
docker run -d --name mplad-postgis -e POSTGRES_PASSWORD=postgres -e POSTGRES_DB=mplad_trace -p 5432:5432 postgis/postgis:16-3.4

The container must be running and ``backend/schema.sql`` must already have
been applied. This script reloads only the calibrated synthetic Tier 2 CSV.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# Permit direct ``python scripts/verify_postgis_integration.py`` execution.
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import numpy as np
import pandas as pd
import psycopg

from backend.load_postgis import load_synthetic_projects
from backend.ml.features import DATASET_PATH, FEATURE_COLUMNS, build_feature_matrix
from backend.ml.scorer import RISK_SCORE_COLUMN, score_feature_matrix


DSN = os.environ.get(
    "MPLAD_TRACE_POSTGIS_DSN",
    "host=localhost port=5432 dbname=mplad_trace user=postgres password=postgres",
)
SAMPLE_IDS = [f"MPLAD-{number:05d}" for number in range(1, 11)]


def precision_recall_at_top_twenty_percent(scored: pd.DataFrame) -> tuple[float, float]:
    """Evaluate ranked review prioritisation only after unlabeled scoring is complete."""
    labels = pd.read_csv(DATASET_PATH, usecols=["project_id", "_ground_truth_is_anomalous"])
    evaluated = scored.merge(labels, on="project_id", validate="one_to_one").sort_values(
        RISK_SCORE_COLUMN, ascending=False
    )
    top = evaluated.head(int(np.ceil(len(evaluated) * 0.20)))
    positives = evaluated["_ground_truth_is_anomalous"].astype(bool)
    precision = float(top["_ground_truth_is_anomalous"].astype(bool).mean())
    recall = float(top["_ground_truth_is_anomalous"].astype(bool).sum() / positives.sum())
    return precision, recall


def main() -> int:
    """Load synthetic records and verify PostGIS density and scorer invariants."""
    passed = True
    print("MPLAD Trace PostGIS integration verification")
    print(f"DSN: {DSN}")
    try:
        loaded = load_synthetic_projects(DSN)
        print(f"Loaded calibrated synthetic Tier 2 rows: {loaded}")
        with psycopg.connect(DSN) as connection, connection.cursor() as cursor:
            cursor.execute("SELECT COUNT(*) FROM projects")
            project_count = int(cursor.fetchone()[0])
            print(f"projects row count: {project_count}")
            cursor.execute(
                """
                SELECT p1.project_id, COUNT(p2.project_id) AS nearby
                FROM projects AS p1
                JOIN projects AS p2
                  ON ST_DWithin(p1.location, p2.location, 2000)
                 AND p1.project_id <> p2.project_id
                GROUP BY p1.project_id
                ORDER BY nearby DESC, p1.project_id
                LIMIT 10
                """
            )
            print("Top ST_DWithin 2 km neighbor counts:")
            for project_id, nearby in cursor.fetchall():
                print(f"  {project_id}: {nearby}")
        passed &= project_count == 3_000

        postgis_features = build_feature_matrix(postgis_dsn=DSN)
        fallback_features = build_feature_matrix()
        numeric = postgis_features.loc[:, FEATURE_COLUMNS].to_numpy(dtype=float)
        finite = bool(np.isfinite(numeric).all())
        print(f"PostGIS feature matrix shape: {postgis_features.shape}")
        print(f"All feature values finite: {finite}")
        print("PostGIS geo_cluster_density describe:")
        print(postgis_features["geo_cluster_density"].describe().to_string())
        comparison = (
            postgis_features.loc[postgis_features["project_id"].isin(SAMPLE_IDS), ["project_id", "geo_cluster_density"]]
            .merge(
                fallback_features.loc[
                    fallback_features["project_id"].isin(SAMPLE_IDS), ["project_id", "geo_cluster_density"]
                ],
                on="project_id",
                suffixes=("_postgis", "_haversine"),
            )
            .sort_values("project_id")
        )
        comparison["difference"] = comparison["geo_cluster_density_postgis"] - comparison["geo_cluster_density_haversine"]
        print("First 10 density values (PostGIS | Haversine fallback | difference):")
        print(comparison.to_string(index=False))
        passed &= len(postgis_features) == 3_000 and finite

        scored = score_feature_matrix(postgis_features)
        precision, recall = precision_recall_at_top_twenty_percent(scored)
        exact_hundreds = int((scored[RISK_SCORE_COLUMN] == 100).sum())
        print(f"Top-20% precision: {precision:.2%}")
        print(f"Top-20% recall: {recall:.2%}")
        print(f"Exact-100 score count: {exact_hundreds}")
        passed &= precision >= 0.75 and recall >= 0.80 and exact_hundreds == 0
    except Exception as error:  # Keep the verifier's final summary useful for demo setup.
        print(f"Verification error: {type(error).__name__}: {error}")
        passed = False

    print(f"POSTGIS INTEGRATION: {'PASS' if passed else 'FAIL'}")
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
