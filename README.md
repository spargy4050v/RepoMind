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

## Current setup

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
python -m backend.load_postgis
```

The loader inserts the calibrated synthetic Tier 2 CSV into the PostGIS schema.
Pass a connection string with `--dsn` when the database is not the local default.

The Module 2 CSV test path uses an exact great-circle 2km fallback so it can
run offline before ingestion; production density uses PostGIS `ST_DWithin`.

Follow `BUILD_PLAN.md` and `PROGRESS.md` strictly. The explainable local scorer,
local API, project dashboard, project detail view, and contractor cluster view
are available. Module 8 end-to-end verification is the next planned phase.

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
project list, project-detail, and contractor-cluster views with summary cards,
API-backed filters, sort controls, pagination, coded explanations, and shared risk tiers. It continues to label all project-level data as
calibrated **synthetic Tier 2** data.

## Score one uploaded scheme

Train and save the local unlabeled detector artifact explicitly (never on an upload):

```powershell
python -m backend.ml.train_models
```

Then score an exactly-one-row CSV using the saved models:

```powershell
python -m backend.ml.inference path\to\uploaded_scheme.csv
```

The upload may contain all seven engineered feature columns, or the complete
raw project fields required by `backend.ml.features`. Missing, non-finite, and
malformed raw values are rejected; values outside the training range are reported as
data-quality review reasons. This CLI runs inference only and never retrains.

## CORS for a separately hosted dashboard

The Vite development server proxies API calls automatically. If the built
frontend is served from a different origin, start the API with its origins set:

```powershell
$env:MPLAD_TRACE_CORS_ORIGINS = "https://dashboard.example.org,http://localhost:5173"
uvicorn backend.api.main:app
```
