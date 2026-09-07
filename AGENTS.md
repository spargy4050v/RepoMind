# Agent Context - MPLAD Trace

Read this before making changes.

## What we're building

An explainable fraud/anomaly dashboard for MPLAD projects (SIH 2026, PS SIH26102). Every future risk score must carry specific human-readable reasons; a bare score is never acceptable.

## Current phase

Read `PROGRESS.md` and `BUILD_PLAN.md`. Do not work on a later module until the current module's checklist is fully verified.

## Hard constraints

- No paid APIs, API keys, or required online services. The project must run locally.
- Synthetic data must always be labelled synthetic. Tier 1 (`mp_fund_summary`) is real public aggregate data; Tier 2 (`projects`) is calibrated synthetic project data. Never blur them.
- `_ground_truth_*` fields are evaluation-only. They must never be features or inputs to a scoring engine.
- Production storage is Postgres + PostGIS. Use geography/geometry plus `ST_DWithin` and `ST_ClusterDBSCAN` for geographic features; coordinate rounding and manual location buckets are prohibited.
- Keep to the stack in `README.md`; flag a new framework, database, or major dependency before adding it.

## Code conventions

- Python functions that compute features or rules require type hints and docstrings explaining the suspicious pattern and why it matters.
- React uses functional components and hooks. Tailwind only; no CSS files.
- Keep risk tiers in one shared frontend location: green <40, amber 40-70, red >70.

## API contract

Before API or frontend work, update `docs/API_CONTRACT.md` before implementation if a response shape changes.

## When unsure

Stop and ask before making an architectural decision not covered by `BUILD_PLAN.md`.
