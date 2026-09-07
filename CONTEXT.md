# MPLAD Trace Working Context

Update this file whenever repository state, validated results, decisions, blockers, or the active task changes. It is a handoff record, not a substitute for `AGENTS.md` or `BUILD_PLAN.md`.

## Project

MPLAD Trace is an SIH 2026 explainable fraud/anomaly-detection project for MPLAD scheme implementation. A risk score must always have specific human-readable reasons. The project runs locally without paid APIs or API keys.

## Non-negotiable constraints

- Tier 1 (`mp_fund_summary`) is real public aggregate data; Tier 2 (`projects`) is calibrated synthetic project data. Keep this distinction explicit.
- `_ground_truth_*` fields are evaluation-only and cannot be scoring/model inputs.
- Postgres + PostGIS is authoritative. Production geographical analysis uses geography plus `ST_DWithin`/`ST_ClusterDBSCAN`; coordinate bucketing is prohibited.
- Do not start a later module until the active module's checklist is fully verified.

## Current repository state

### Completed and validated

- Module 1 source: `data/generate_dataset.py` writes `data/mplad_projects.csv`.
- Regenerated dataset: 3,000 synthetic project rows and 570 hidden anomalies (19.0%).
- Module 2 source: `backend/ml/features.py` returns `project_id` plus exactly seven finite features: `cost_ratio`, `completion_speed_ratio`, `payment_gap_days`, `contractor_project_count`, `contractor_constituency_share`, `geo_cluster_density`, and `sanction_lag_days`.
- Ground-truth fields are absent from the returned feature matrix.
- Known cost-inflation and payment-timing records produce the expected extreme feature signals.
- Focused test command: `python -m pytest -q`; latest result: `5 passed in 2.24s`.

### Production database state

- `backend/schema.sql` contains the Postgres + PostGIS two-tier schema and production `ST_DWithin` density design.
- The CSV-only feature test path uses an exact great-circle 2km fallback with equivalent inclusion/exclusion semantics. It is explicitly not the production implementation.
- Blocker: `psql`/a Postgres + PostGIS instance is unavailable in the current environment, so production spatial integration has not been executed.

## Active module and next action

`PROGRESS.md` remains unchanged: Module 2 is not yet complete because its PostGIS checklist item is unverified. Module 3, FastAPI, and frontend work have not started.

Next permitted work:

1. Provision local Postgres with PostGIS and apply `backend/schema.sql`.
2. Ingest the synthetic CSV into `projects`, constructing the `location` geography from CSV coordinates.
3. Run `build_feature_matrix(..., postgis_dsn=...)` and verify its `ST_DWithin` density query.
4. Update Module 2 checklist and `PROGRESS.md` only after that verification succeeds.
5. Then review and execute the pending Module 3 scorer brief; it requires adding scikit-learn and must preserve the evaluation-label isolation rule.

## Recent structural decisions

- The authoritative layout is `data/`, `backend/`, `docs/`, and `tests/` as documented in `README.md` and `BUILD_PLAN.md`.
- Retired incompatible prototype sources: `ml/detector.py`, `backend/main.py`, and `data/projects.csv`.
- No scorer, API, or frontend replacement was created.

## Pending user instruction

The latest pasted specification requests Module 3 scoring, tests, and metrics. It is retained as intent but is blocked by the active Module 2 PostGIS validation requirement above.
