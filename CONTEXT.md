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
- Verified on 2026-09-07 with a local PostGIS 3.4.3 container: schema applied, all 3,000 projects loaded, and `build_feature_matrix(postgis_dsn=...)` returned 3,000 finite rows through its production `ST_DWithin` query. Two density counts differ from the Haversine fallback at the radius boundary because PostGIS geography uses its geodetic distance model.

## Active module and next action

Module 2 is complete. Module 3 is now the active module; FastAPI and frontend work have not started.

Next permitted work:

1. Implement the Module 3 scorer with Isolation Forest and explainable rules.
2. Add scorer tests, including precision-at-top-20% and recall checks using labels only in the test evaluation code.
3. Record actual Module 3 metrics in `PROGRESS.md` and this file.

## Recent structural decisions

- The authoritative layout is `data/`, `backend/`, `docs/`, and `tests/` as documented in `README.md` and `BUILD_PLAN.md`.
- Retired incompatible prototype sources: `ml/detector.py`, `backend/main.py`, and `data/projects.csv`.
- No scorer, API, or frontend replacement was created.

## Pending user instruction

The latest pasted specification requests Module 3 scoring, tests, and metrics. It is now authorized because Module 2's PostGIS validation is complete.
