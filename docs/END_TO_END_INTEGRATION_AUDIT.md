# End-to-End Integration Audit

**Audit date:** 2026-09-10  
**Scope:** Static integration trace and executable-environment readiness check.
This is not a substitute for the formal Module 8 runtime gate.

## Executive result

The primary portfolio-review path is coherently wired in source: React calls
FastAPI, FastAPI builds the documented seven-feature matrix, the hybrid scorer
returns reasons with the score, and the dashboard renders those reasons. This
workspace cannot prove that path at runtime because it has no runnable project
Python environment or frontend dependency installation.

Three issues prevent a fully verified dashboard/upload workflow today:

1. Vite omits `/upload` from its development proxy. The active upload screen's
   `/upload/extract` and `/upload/score` requests therefore do not reach
   FastAPI when `VITE_API_BASE_URL` is unset.
2. `models/anomaly_detectors.pkl` is absent. Upload scoring uses the saved-model
   inference path and will return a validation error until this local artifact
   is trained and present.
3. `App.tsx` returns the new `DashboardWithUpload` branch before legacy
   dashboard routing. The contractor detail flow is not reachable in the active
   UI, although its API endpoint and component remain in the repository.

Also resolve these before a demo: `/upload/extract` is documented as multipart
but implemented as raw bytes plus `X-Filename`, and visible UI/API text contains
encoding corruption such as `â‚¹` and `â†’`.

## Repository map

```text
RepoMind/
├── data/
│   ├── generate_dataset.py          # creates calibrated synthetic Tier 2 CSV
│   └── mplad_projects.csv           # 3,000 project rows; labels are evaluation-only
├── backend/
│   ├── api/main.py                  # FastAPI routes, local auth/audit, response composition
│   ├── ml/
│   │   ├── features.py              # exactly seven permitted features
│   │   ├── scorer.py                # portfolio hybrid scorer and explanations
│   │   ├── anomaly_detection.py     # Isolation Forest and LOF wrappers
│   │   ├── inference.py             # saved-model, one-record upload inference
│   │   ├── train_models.py          # explicit local artifact training
│   │   └── ingest/extract.py        # CSV, Excel, DOCX, PDF, image extraction
│   ├── schema.sql                   # authoritative Postgres/PostGIS design
│   ├── load_postgis.py              # synthetic CSV loader for PostGIS
│   ├── external_context.py          # disabled-by-default public-context seam
│   └── requirements.txt             # Python dependencies
├── frontend/
│   ├── src/api.ts                   # typed browser client and token handling
│   ├── src/App.tsx                  # login shell and active dashboard selection
│   ├── src/RiskEngine.tsx           # overview, projects, analysis, simulator, alerts
│   ├── src/UploadStory.tsx          # extraction, confirmation, score narrative
│   ├── src/risk.ts                  # shared green/amber/red thresholds
│   └── vite.config.ts               # local development proxy
├── tests/                           # data, scorer, inference, and API tests
├── docs/API_CONTRACT.md             # intended response/request source of truth
├── BUILD_PLAN.md                    # phased build gate
└── CONTEXT.md                       # handoff and verification state
```

## Technology stack

| Layer | Technology | Role |
|---|---|---|
| Data preparation | Python, pandas, NumPy | Generates and transforms calibrated synthetic data. |
| Spatial production design | PostgreSQL, PostGIS | Holds the two tiers and supports `ST_DWithin`/`ST_ClusterDBSCAN`. |
| Local demo storage | CSV plus SQLite | CSV powers offline portfolio scoring; SQLite holds sessions, uploads, alerts, and audit history. SQLite is not the production database. |
| Detection | scikit-learn Isolation Forest + LOF + deterministic rules | Produces anomaly likelihood and concrete review evidence. |
| API | FastAPI, Uvicorn, httpx | Serves protected local endpoints and error responses. |
| UI | React 18, TypeScript, Vite, Tailwind CSS | Renders dashboard flows and consumes typed API responses. |
| File extraction | openpyxl, python-docx, pypdf, Pillow, pytesseract, pdf2image | Extracts labelled fields for reviewer confirmation. OCR needs local Tesseract; scanned PDFs need Poppler. |
| Test tooling | pytest, FastAPI TestClient | Covers feature, scorer, API, and inference contracts. |

No paid API key is required. Optional external public context is disabled by
default and cannot be a model input.

## Data boundaries and scoring contract

### Tier 1: real public aggregate data

`mp_fund_summary` in `backend/schema.sql` is reserved for real public aggregate
MPLAD summaries: entitled, released, sanctioned, expended, unspent, and work
counts. It supports macro utilisation and completion analysis.

### Tier 2: calibrated synthetic project data

`data/mplad_projects.csv` and the PostGIS `projects` table hold synthetic
project-level records. The local portfolio API reads this CSV, not external
government transactions. The UI must preserve that disclosure.

### Evaluation labels and seven features

`_ground_truth_*` fields are held solely for synthetic evaluation and are never
features or scorer inputs. The feature builder returns `project_id` plus:

1. `cost_ratio`
2. `completion_speed_ratio`
3. `payment_gap_days`
4. `contractor_project_count`
5. `contractor_constituency_share`
6. `geo_cluster_density`
7. `sanction_lag_days`

The scorer rejects any other matrix schema. Display endpoints exclude
ground-truth fields; confirmed upload records drop such fields before scoring.

## Primary portfolio workflow

```text
Browser login
  → POST /auth/login
  → token in localStorage
  → authenticated React API client
  → FastAPI auth middleware
  → synthetic CSV + feature builder
  → Isolation Forest + LOF + transparent rules
  → risk score and coded reasons
  → FastAPI JSON response
  → RiskEngine overview, analysis, simulator, and alerts UI
```

### Happy path

1. A reviewer logs in with a local demo or registered account. FastAPI stores
   the server session in SQLite; the browser stores the token in localStorage.
2. `RiskEngine` requests the portfolio summary, tier distribution, alert queue,
   and highest-risk projects.
3. `GET /projects` resolves `_scored_table()`: it reads the synthetic CSV,
   builds the seven features, fits local portfolio detectors, applies rules,
   and joins score/reasons to safe display fields.
4. Selecting a project calls `GET /projects/{project_id}`. The response includes
   display fields, GeoJSON location, nearby IDs, score, and coded reasons.
5. Risk Analysis renders cost deviation, project facts, and every returned
   reason. The output is a review signal, not a fraud verdict.
6. Amber/red records seed persisted alerts. The reviewer changes state between
   `new`, `under_review`, `investigating`, and `resolved`.
7. The simulator calls `POST /simulate`; missing features are filled with
   portfolio medians. It returns live score/reasons/breakdown and never persists
   data or retrains a model.

### Static frontend/backend mapping

| Client operation | API route | Active UI state | Static result |
|---|---|---|---|
| Login / register | `POST /auth/login`, `POST /auth/register` | Login shell | Wired; `/auth` is proxied. |
| Summary | `GET /stats/summary` | Overview | Wired; `/stats` is proxied. |
| Portfolio distribution | `GET /analysis/portfolio` | Overview | Wired; `/analysis` is proxied. |
| Project queue | `GET /projects` | Overview and Projects | Wired; `/projects` is proxied. |
| Project detail | `GET /projects/{id}` | Risk Analysis | Wired; `/projects` is proxied. |
| Simulator | `POST /simulate` | Detection Logic | Wired; `/simulate` is proxied. |
| Alerts | `GET /alerts`, `PATCH /alerts/{id}` | Alerts | Wired; `/alerts` is proxied. |
| Extraction | `POST /upload/extract` | Upload file | Client is wired, but `/upload` is not proxied: blocked in normal Vite dev use. |
| Confirmed document score | `POST /upload/score` | Upload file | Blocked by proxy omission and absent model artifact. |
| Contractor portfolio | `GET /contractors/{id}` | Legacy component only | API/client exist but active UI cannot reach it. |
| Rescan, history, saved uploads | corresponding API routes | Legacy component only | Backend exists but active dashboard does not expose the workflow. |

## File-upload workflow

```text
Choose supported file
  → browser sends raw bytes + X-Filename
  → POST /upload/extract
  → local parser/OCR returns fields, confidence, and source
  → reviewer corrects fields
  → POST /upload/score
  → saved-model inference
  → score, coded reasons, deterministic story, evidence persisted in SQLite
```

The extractor supports CSV, XLSX/XLS, DOCX, text PDF, PNG, JPG, and JPEG. It
rejects unsupported, empty, corrupt, oversize (more than 10 MB), and fieldless
files; PDFs are limited to 10 pages. OCR fields have low confidence by design
and must be reviewed before scoring.

Raw records require valid dates, finite numeric values, positive baseline and
duration, valid coordinates, and all documented fields. Feature-ready records
need all seven finite features. Partial/malformed records are rejected instead
of being silently imputed. Uploads never retrain the detector.

## Error and edge cases

| Case | Intended server outcome |
|---|---|
| Missing/invalid token | `401` shared error response. |
| Invalid query or alert status | `422` shared error response. |
| Missing project, contractor, alert, or another user’s upload | `404` shared error response. |
| Unsupported/corrupt/oversize/fieldless document | `422` extraction error. |
| No `X-Filename` with raw-byte extraction | `422`. |
| No saved model artifact | `422` with instruction to train models. |
| Missing/invalid upload field | `422`, never a silent zero-valued feature. |
| Ground-truth upload field | Dropped before confirmed scoring output. |
| Optional external source unavailable | Non-fatal unavailable status; never a model input. |

## Spatial design

The production schema uses `GEOGRAPHY(POINT, 4326)` plus a GiST index.
Production density/clustering uses `ST_DWithin` and `ST_ClusterDBSCAN`. The
offline CSV/API path uses exact Haversine distance solely for local demo/tests;
it does not use coordinate rounding or manual location buckets.

## Automated coverage

There are 24 named pytest cases covering dataset size/rate, finite seven-feature
matrices, label exclusion, scorer bounds/reasons/evaluation, detector wrappers,
saved-model inference validation, FastAPI authentication, project list/detail,
contractor, summary/rescan, CORS, upload verification, history, portfolio,
simulation, and alerts.

Not covered today: extraction for every format and limit; `/upload/score` and
story persistence; the `/upload` Vite proxy; active React routing; browser-level
flows/visual quality; and a current PostGIS runtime pass.

## Verification performed in this audit

| Check | Result |
|---|---|
| Git tree before audit | Clean. |
| Route/API-client trace | Completed statically. |
| Feature/scorer/API/upload trace | Completed statically. |
| Saved model artifact | Absent: `models/anomaly_detectors.pkl`. |
| Project virtual environment | Absent: `.venv/Scripts/python.exe`. |
| Frontend dependencies | Absent: `frontend/node_modules`. |
| Full pytest run | Not reproducible here; `python`/`py` resolve to Windows Store aliases, not the project runtime. |
| Frontend build | Not reproducible here; dependency directory is absent. |
| Live browser/API/PostGIS run | Not performed because prerequisites are missing. |

`CONTEXT.md` records a previous-environment `20 passed` test run and successful
frontend build. Those are historical results, not present-checkout verification.

## Required remediation order

1. Add `/upload` to Vite’s local proxy, or consistently configure
   `VITE_API_BASE_URL`. Reconcile API contract wording with actual raw-byte
   plus `X-Filename` implementation, or implement multipart across both sides.
2. Restore the active contractor workflow or remove it from product claims.
   Remove unreachable legacy code instead of masking it with `@ts-nocheck`.
3. Repair visible encoding corruption before screenshots, recordings, or stage
   demos.
4. Create `.venv`, install backend/frontend dependencies, and run the documented
   local training command to create the upload model artifact.
5. Add tests for extraction, confirmed scoring/persistence, proxy integration,
   and active UI navigation.
6. Run Module 8 from cold start: full pytest, production build, authenticated
   browser path, upload CSV happy/error cases, and PostGIS loader/query check
   where local PostGIS is available.

Only after these checks pass should MPLAD Trace be described as fully
end-to-end verified for an SIH live demonstration.
