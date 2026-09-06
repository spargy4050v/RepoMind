# Agent Context — MPLAD Trace

Read this before making changes. This file exists so any AI coding agent working
in this repo (Antigravity, Codex, etc.) has consistent grounding instead of
re-inferring project intent from scratch each session.

## What we're building
A fraud/anomaly detection dashboard for MPLAD (govt scheme fund disbursement)
projects, for SIH 2026 (PS SIH26102). Judges will ask "why is this flagged?" —
every risk score MUST be explainable with specific triggered reasons, never a
bare number. This is the single non-negotiable design constraint of the project.

## Current phase
Check `PROGRESS.md` for the exact module in progress. Do not jump ahead to a
later module's files until the current module's test checklist (in
`BUILD_PLAN.md`) is fully checked off.

## Hard constraints — do not violate these
- **No paid APIs, no API keys required to run the project.** Everything must
  run fully offline/locally (this is a judging requirement — "free tier" build).
- **Data is synthetic, and must stay clearly labeled as such.** Never write
  copy, comments, or UI text that implies the data is real government data.
- **`_ground_truth_*` fields exist only for evaluating the model.** Never let
  the scoring engine (`backend/ml/scorer.py`) read these as input features —
  that would be cheating/leakage and invalidates the whole detector.
- **Every anomaly score must ship with human-readable reasons.** If you add a
  new detection rule or feature, always add a corresponding reason string.
- **Stick to the tech stack in `README.md`.** Don't introduce a new framework,
  database, or major dependency without flagging it to the team first — we're
  optimizing for a small team finishing in ~3 weeks, not for the "best" stack.
- **Database is Postgres + PostGIS**, not SQLite (superseded the earlier SQLite
  plan — see `docs/DATA_STRATEGY.md` for why). Use PostGIS geography/geometry
  types and spatial functions (`ST_DWithin`, `ST_ClusterDBSCAN`) for geo
  features — do not reimplement geo-clustering with manual lat/lon rounding.
- **Two data tiers exist — do not blur them.** Tier 1 (`mp_fund_summary` table)
  is REAL public government data. Tier 2 (`projects` table) is calibrated
  SYNTHETIC data. Never write code, UI copy, or docs that imply Tier 2 numbers
  are real government figures.

## Code conventions
- Python: type hints on function signatures, docstrings on any function that
  computes a feature or rule (explain *what pattern it detects and why*, not
  just what the code does — the team needs to defend this at Q&A).
- React: functional components + hooks only. Tailwind for styling, no CSS files.
- Keep risk-tier color logic (green <40, amber 40-70, red >70) in ONE shared
  place (`frontend/src/lib/riskTiers.js` or similar) and import it everywhere —
  never hardcode the thresholds/colors in multiple components.

## API contract
Backend and frontend must agree on response shapes before frontend work starts.
See `docs/API_CONTRACT.md` — update it FIRST if an endpoint's shape changes,
then update the code to match, not the other way around.

## When you're unsure
If a request is ambiguous or you're about to make an architectural decision
not covered here or in `BUILD_PLAN.md`, stop and ask the team rather than
guessing — this is a competition submission the team needs to be able to
explain in full, not a throwaway prototype.
