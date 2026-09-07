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

## Current setup (Modules 1 and 2 only)

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

Follow `BUILD_PLAN.md` and `PROGRESS.md` strictly. Scoring, API, and frontend
modules have not been started.
