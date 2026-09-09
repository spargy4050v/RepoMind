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
- Focused test command: `python -m pytest -q`; latest result before Module 3: `5 passed in 2.24s`.

### Module 3 completed and validated

- `backend/ml/scorer.py` contains a deterministic local NumPy Isolation Forest. It consumes exactly the seven Module 2 features, with no labels, API calls, or additional dependencies.
- The scorer blends the unsupervised score with explicit cost, completion, payment, contractor-concentration, geographic-density, and sanction-lag rules. Every result contains a bounded 0--100 score and a non-empty, specific reason list (or a clear no-warning explanation).
- `tests/test_module3_scorer.py` verifies the output contract, strict prevention of ground-truth inputs, and held-out-after-scoring evaluation. At the top 20% review queue, precision is 79.17% and recall is 83.33% (thresholds: 75% and 80%). The intentionally ambiguous contractor cohort labels only half of otherwise identical concentration-pattern records, so a substantially higher label-only target would misrepresent what the permitted features can distinguish.
- Module 3 test command: `python -m pytest -q tests/test_module3_scorer.py` -> `3 passed`. Existing Module 1--2 non-temp-fixture tests: `4 passed, 1 deselected`. The environment denied pytest access to sandbox-created cache/temp directories during the full collection; this is not a project test failure.

### Module 4 completed and validated

- `docs/API_CONTRACT.md` was updated before implementation. It explicitly identifies the local data as synthetic Tier 2, excludes evaluation-only ground-truth fields, documents reason objects, and distinguishes the offline exact-distance fallback from production PostGIS `ST_DWithin` geography.
- `backend/api/main.py` implements the documented `/projects`, `/projects/{project_id}`, `/contractors/{contractor_id}`, `/stats/summary`, and `/projects/rescan` endpoints. It caches local unlabeled scorer results, supplies coded explanation objects for all project details, and uses the documented error object for 404/422 responses.
- `backend/requirements.txt` now declares FastAPI and Uvicorn. Dependencies were installed locally and the service is runnable with `uvicorn backend.api.main:app --reload`.
- `tests/test_module4_api.py` passes: `3 passed`. The Module 3 scorer regression test also passes: `3 passed`.

### Module 5 completed and validated

- `frontend/` is a React/Vite/Tailwind application that consumes only the documented local API. It provides synthetic-data labelling, portfolio summary cards, filters, sorting, pagination, and a project review list.
- `frontend/src/risk.ts` is the single risk-tier source: green <40, amber 40--70, red >70.
- `npm run build` completes successfully.

### Module 6 completed and validated

- `frontend/src/ProjectDetail.tsx` consumes the documented `GET /projects/{project_id}` response without changing the API contract.
- The project list opens the detail view, which presents coded reasons, risk tier, review facts, project timeline, coordinates, nearby-project count, and synthetic Tier 2 labelling.
- `npm run build` completes successfully.

### Module 7 completed and validated

- `frontend/src/ContractorView.tsx` consumes the documented `GET /contractors/{contractor_id}` response without changing the API contract.
- The contractor field in project detail opens a synthetic contractor portfolio with average-risk tier, flagged count, constituency footprint, and links to its project cluster.
- `npm run build` completes successfully.

### Production database state

- `backend/schema.sql` contains the Postgres + PostGIS two-tier schema and production `ST_DWithin` density design.
- The CSV-only feature test path uses an exact great-circle 2km fallback with equivalent inclusion/exclusion semantics. It is explicitly not the production implementation.
- Verified on 2026-09-07 with a local PostGIS 3.4.3 container: schema applied, all 3,000 projects loaded, and `build_feature_matrix(postgis_dsn=...)` returned 3,000 finite rows through its production `ST_DWithin` query. Two density counts differ from the Haversine fallback at the radius boundary because PostGIS geography uses its geodetic distance model.

## Active module and next action

Module 7 is complete. Module 8 is now the active module.

Next permitted work:

1. Perform the end-to-end test pass across the dashboard and API.

## Recent structural decisions

- The current layout is `data/`, `backend/`, `docs/`, `frontend/`, and `tests/`. `frontend/` contains the Module 5 React/Vite/Tailwind application.
- Removed obsolete root-level `database/` and `ml/` placeholder directories and generated test/bytecode artifacts.
- `.gitignore` now correctly ignores Python bytecode, pytest temporary/cache directories, virtual environments, Node build artifacts, and local environment files.

## Pending user instruction

Perform the Module 8 end-to-end test pass only after the user requests the next phase.

## Current maintenance work

- The user requested a bug-fix pass before Module 8. The duplicate root-level
  pytest diagnostic was moved to `scripts/evaluate_anomaly_detection.py` so it
  no longer collides with `tests/test_anomaly_detection.py` during collection.
- Raw inference uploads now reject malformed numeric values, invalid dates, and
  out-of-bounds coordinates instead of allowing the feature builder to impute
  zeroes. The FastAPI service now has configurable CORS origins, and
  `backend/load_postgis.py` loads the synthetic CSV into the documented schema.
- Verification found an omitted `httpx` dependency required by FastAPI's test
  client; it has been added to `backend/requirements.txt`.
- Validation after the maintenance pass: `.venv\\Scripts\\python.exe -m pytest -q`
  completed with `20 passed`; `npm run build` completed successfully. The
  PostGIS loader itself requires a running local PostGIS instance and was not
  executed against a database in this pass.

## Context maintenance

- On 2026-09-09, the user requested that this handoff record be updated for
  every prompt and that completed working-tree changes be pushed to Git.
