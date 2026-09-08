# MPLAD Trace

AI-powered anomaly/fraud detection for MPLAD scheme implementation (SIH26102).
The detailed project dataset is calibrated **synthetic** Tier 2 data, not government transaction data.

## Authoritative structure

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

Postgres + PostGIS is the production database design. `backend/schema.sql` defines
Tier 1 real public aggregate data and Tier 2 synthetic project data separately.

## Current setup (Modules 1--5)

```powershell
python data/generate_dataset.py
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r backend/requirements.txt
python -m pytest -q
```

For production spatial-density validation, initialize Postgres with PostGIS:

```powershell
createdb mplad_trace
psql mplad_trace -f backend/schema.sql
```

The Module 2 CSV test path uses an exact great-circle 2km fallback so it can
run offline before ingestion; production density uses PostGIS `ST_DWithin`.

Follow `BUILD_PLAN.md` and `PROGRESS.md` strictly. The explainable local scorer
and local API are available; frontend modules have not been started.

## Run the local API

```powershell
uvicorn backend.api.main:app --reload
```

The service is available at `http://localhost:8000`; interactive contract
documentation is at `/docs`. It serves calibrated **synthetic Tier 2** project
data and never exposes evaluation-only ground-truth fields.

## Run the dashboard

In a second terminal, after starting the API:

```powershell
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173`. The Module 5 dashboard is a React/Vite/Tailwind
project list with summary cards, API-backed filters, sort controls, pagination,
and shared risk tiers. It continues to label all project-level data as
calibrated **synthetic Tier 2** data.
