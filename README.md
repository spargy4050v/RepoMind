# MPLAD Trace
AI-powered anomaly/fraud detection for MPLAD scheme implementation — SIH26102.

## What this is
Ingests MPLAD project records (cost, timeline, contractor, location) and produces
an explainable risk score per project — not a black-box label. See `BUILD_PLAN.md`
for the full module-by-module build spec.

## Repo layout
```
data/          Synthetic dataset generator + output CSV/JSON
backend/
  ml/          Feature engineering + Isolation Forest scoring engine
  api/         FastAPI service exposing scored data
frontend/      React + Vite + Tailwind dashboard
docs/          API contract, coding conventions, agent context
tests/         Cross-cutting test scripts (precision/recall checks, API tests)
```

## Setup
```bash
# 0. Database (Postgres + PostGIS)
createdb mplad_trace
psql mplad_trace -f backend/schema.sql

# 1. Generate synthetic Tier 2 data, load Tier 1 real data
cd data && python3 generate_dataset.py
# (Tier 1: pull real MPLADS aggregate datasets per docs/DATA_STRATEGY.md and load into mp_fund_summary)

# 2. Backend
cd backend && python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
uvicorn api.main:app --reload   # http://localhost:8000/docs

# 3. Frontend
cd frontend && npm install && npm run dev   # http://localhost:5173
```

See `docs/DATA_STRATEGY.md` for the real-vs-synthetic data design, and
`docs/PROBLEM_STATEMENT.md` for the full problem + solution write-up.

## Build order
Follow `BUILD_PLAN.md` strictly in module order. Do not start a module until
the previous one's test checklist in that doc is fully checked off — this
matters most for Module 3 (scoring engine), which everything else depends on.

## Status
See `PROGRESS.md` for current module status.
