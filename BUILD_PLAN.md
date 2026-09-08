# MPLAD Trace Build Plan

## Locked architecture

- Python with pandas and NumPy for dataset and feature engineering.
- Postgres + PostGIS for the authoritative relational and spatial design.
- Tier 1 is real public aggregate data in `mp_fund_summary`; Tier 2 is clearly labelled calibrated synthetic project data in `projects`.
- The production geographic-density query uses `ST_DWithin` on PostGIS geography. Coordinate rounding and manual location buckets are prohibited.
- No paid APIs, API keys, or online services are required.

## Authoritative repository structure

```
data/
  generate_dataset.py
  mplad_projects.csv
backend/
  requirements.txt
  schema.sql
  ml/features.py
docs/
  API_CONTRACT.md
  DATA_STRATEGY.md
  PROBLEM_STATEMENT.md
tests/
  test_module1_and_module2.py
```

## Module 1: Synthetic Dataset - done

Output: `data/generate_dataset.py` and `data/mplad_projects.csv`.

- [x] The checked-in synthetic Tier 2 dataset contains 3,000 projects.
- [x] Its hidden evaluation-label anomaly rate is 19.0%.
- [x] `_ground_truth_*` columns are retained only for evaluation.

## Module 2: Feature Engineering - done

Output: `backend/ml/features.py`.

It returns `project_id` plus exactly these seven numerical features:

1. `cost_ratio`
2. `completion_speed_ratio`
3. `payment_gap_days`
4. `contractor_project_count`
5. `contractor_constituency_share`
6. `geo_cluster_density`
7. `sanction_lag_days`

Checklist:

- [x] Full dataset run produces finite values for all 3,000 rows, including safe handling of invalid dates, missing values, zero baselines, and infinity.
- [x] Known `cost_inflation` records have `cost_ratio > 1.8`; known `payment_timing` records have negative `payment_gap_days`.
- [x] The matrix contains no `_ground_truth_*` columns.
- [x] The production `ST_DWithin` query was verified against a local Postgres + PostGIS instance. The exact-distance CSV fallback is offline test support only.

## Module 3: Anomaly Scoring Engine - done

Output: `backend/ml/scorer.py`. It uses the seven-feature matrix and produces a 0-100 score plus specific human-readable reasons. It must never use ground-truth fields as inputs.

Checklist:

- [x] The deterministic local Isolation Forest consumes exactly the seven Module 2 features.
- [x] Every project has a bounded 0-100 score and a non-empty human-readable reason list.
- [x] Hidden labels are used only after scoring to verify precision-at-top-20% >= 75% and recall-at-top-20% >= 80% (79.17% precision; 83.33% recall).

## Module 4: FastAPI Service - done

Output: `backend/api/main.py`, following `docs/API_CONTRACT.md`.

Checklist:

- [x] The local API reads only calibrated synthetic Tier 2 project data and never exposes `_ground_truth_*` fields.
- [x] Paginated project list, project detail, contractor, summary, and rescan endpoints conform to the documented shapes.
- [x] Scores always include coded human-readable reasons; request-validation and not-found errors use the shared error shape.
- [x] API contract tests pass locally.

## Module 5: Dashboard Shell + Project List - done

Output: `frontend/` React/Vite/Tailwind application.

- [x] Dashboard summary cards read `GET /stats/summary` without changing the API contract.
- [x] Paginated project list reads `GET /projects` with documented filters and sort controls.
- [x] The dashboard keeps synthetic Tier 2 labelling visible and uses shared risk tiers: green <40, amber 40-70, red >70.
- [x] `npm run build` passes.

## Modules 6-7: Detail view, contractor view - not started

These React/Tailwind modules begin only after the API contract is implemented and tested.

## Modules 8-10: Integration, demo, pitch alignment - not started

Begin only after the preceding modules pass their checklists.

## Rule

Do not begin a later module until the previous module's checklist is fully verified.
