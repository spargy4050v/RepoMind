"""Load calibrated synthetic Tier 2 projects into the authoritative PostGIS schema."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Final

import pandas as pd
import psycopg

from backend.ml.features import DATASET_PATH


PROJECT_COLUMNS: Final[tuple[str, ...]] = (
    "project_id", "mp_constituency", "state", "work_category", "units", "unit_type", "contractor_id",
    "sanctioned_cost_inr", "regional_baseline_cost_inr", "recommended_date", "sanction_date", "start_date",
    "completion_certified_date", "fund_release_date", "planned_duration_days", "longitude", "latitude",
    "_ground_truth_is_anomalous", "_ground_truth_anomaly_type",
)


def load_synthetic_projects(dsn: str, csv_path: Path = DATASET_PATH) -> int:
    """Replace Tier 2 tables with CSV records and PostGIS geography points for local production validation."""
    source = pd.read_csv(csv_path, encoding="utf-8")
    missing = sorted(set(PROJECT_COLUMNS).difference(source.columns))
    if missing:
        raise ValueError(f"Synthetic project CSV is missing columns: {', '.join(missing)}")
    contractors = source.loc[:, ["contractor_id", "state"]].drop_duplicates().itertuples(index=False, name=None)
    projects = source.loc[:, PROJECT_COLUMNS].itertuples(index=False, name=None)
    contractor_sql = """
        INSERT INTO contractors (contractor_id, registered_state)
        VALUES (%s, %s)
        ON CONFLICT (contractor_id) DO UPDATE SET registered_state = EXCLUDED.registered_state
    """
    project_sql = """
        INSERT INTO projects (
            project_id, mp_constituency, state, work_category, units, unit_type, contractor_id,
            sanctioned_cost_inr, regional_baseline_cost_inr, recommended_date, sanction_date, start_date,
            completion_certified_date, fund_release_date, planned_duration_days, location,
            gt_is_anomalous, gt_anomaly_type
        ) VALUES (
            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
            ST_SetSRID(ST_MakePoint(%s, %s), 4326)::geography, %s, %s
        )
    """
    with psycopg.connect(dsn) as connection, connection.cursor() as cursor:
        cursor.execute("TRUNCATE project_score_reasons, project_scores, projects, contractors CASCADE")
        cursor.executemany(contractor_sql, contractors)
        cursor.executemany(project_sql, projects)
    return len(source)


def main() -> None:
    """Load the checked-in synthetic CSV using a local PostgreSQL DSN by default."""
    parser = argparse.ArgumentParser(description="Load MPLAD Trace synthetic Tier 2 data into PostGIS.")
    parser.add_argument("--dsn", default="dbname=mplad_trace", help="PostgreSQL/PostGIS connection string")
    parser.add_argument("--dataset", type=Path, default=DATASET_PATH, help="Synthetic project CSV path")
    args = parser.parse_args()
    print(f"Loaded {load_synthetic_projects(args.dsn, args.dataset):,} calibrated synthetic Tier 2 projects.")


if __name__ == "__main__":
    main()
