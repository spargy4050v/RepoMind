# API Contract — MPLAD Trace

Source of truth for request/response shapes. Update THIS file first if a shape
needs to change, then update backend + frontend code to match.

Base URL (dev): `http://localhost:8000`

The local development service reads the calibrated **synthetic Tier 2** CSV.
It never returns `_ground_truth_*` evaluation fields. Production storage remains
Postgres + PostGIS; the local CSV path exists for the offline demo only.

All endpoints except `POST /auth/login` and `POST /auth/register` require `Authorization: Bearer <session-token>`. This is self-contained local account access for the hackathon build, not government SSO.

## POST /auth/login
Body: `{"username":"demo","password":"demo123"}`. Returns `{"token":"...","username":"demo"}`. `POST /auth/logout` invalidates the token.

## POST /auth/register
Body: `{"username":"reviewer","password":"at-least-8-characters"}`. Creates a local user with a salted password hash and returns `{"token":"...","username":"reviewer"}`. Usernames are unique, 3--64 characters, and contain letters, numbers, `_`, `.`, or `-`. This is local hackathon access—not government identity verification.

## POST /verify/upload
Authenticated multipart-free JSON body: one raw project object, `{"record": {...}}`, or `{"records": [...]}`. The dashboard parses CSV locally and posts its records in this shape. Each record is scored only through the existing single-record inference pipeline (with the existing trained Isolation Forest/LOF artifact), returns `risk_score` (0--100) plus non-empty coded `reasons`, and is persisted as an owned upload batch. The response includes `upload_id`, `record_count`, and either `result` (one record) or `results` (batch). Results are risk/anomaly likelihood review signals, never fraud verdicts.

## GET /uploads/{upload_id}
Returns the authenticated user's persisted upload batch: `{"upload_id":1,"created_at":"...","record_count":2,"results":[{"risk_score":20,"risk_tier":"green","reasons":[{"code":"...","text":"..."}]}]}`. Another user's upload returns 404.

## POST /upload/extract
Authenticated `multipart/form-data` endpoint accepting one `file` part with a
`.csv`, `.xlsx`, `.xls`, `.docx`, `.pdf`, `.png`, `.jpg`, or `.jpeg` file
(maximum 10 MB and 10 PDF pages). It does not score. It returns normalized
editable `record` fields, per-field `confidence`, and a `source` panel
containing extracted text/tables. Unsupported, corrupt, oversize, or fieldless
documents return the shared 422 error object. `_ground_truth_*` fields are
discarded. The request uses the browser-provided filename in the multipart
part; no custom filename header is required.

## POST /upload/score
Authenticated JSON body: `{"record":{...},"extraction":{"format":"pdf","confidence":{},"source":{}}}`. The confirmed record follows the existing raw-record validation and trained inference path. The response includes the persisted upload result plus deterministic `story`, actual coded `reasons`, and the retained source/confidence evidence. Optional LLM rewriting is disabled by default and is never required for this local flow.

## GET /history
Returns authenticated user audit entries: `[{"timestamp":"...","user":"demo","action":"upload","input_summary":"1 record","risk_score":72,"risk_tier":"red","reasons":[{"code":"...","text":"..."}],"upload_id":1}]`.

## GET /analysis/portfolio
Returns read-only Tier 2 synthetic portfolio distributions by risk tier, state, work category, contractor, and high-risk reason code (`high_risk_reason_codes`).

## POST /simulate
Authenticated what-if endpoint. Body supplies one or more of the seven documented feature values; omitted values use the current synthetic portfolio median. Returns the real scorer's `risk_score`, coded non-empty `reasons`, and `breakdown` category scores. It never persists data, retrains a model, or accepts ground-truth fields.

## GET /alerts
Returns persisted alerts seeded from current amber/red synthetic projects. Query params: `status` (`new`, `under_review`, `investigating`, `resolved`) and `search`. Each result includes `alert_id`, `project_id`, `anomaly_type`, `risk_score`, `severity`, and persisted `status`.

Reason objects use stable codes. In particular, `detector_agreement` means both
the isolation-based and neighborhood-based detectors flagged the project; it
is a corroborating review signal, not a no-warning result.

## PATCH /alerts/{alert_id}
Authenticated body: `{"status":"under_review"}`. Updates a persisted alert status and returns the updated alert. Valid statuses are `new`, `under_review`, `investigating`, and `resolved`.

## GET /context/external-status
Returns the availability of optional, operator-configured public aggregate-data context. It is disabled by default (`MPLAD_TRACE_EXTERNAL_CONTEXT_ENABLED=false`), needs no API key, fails gracefully offline, and is never a model input or merged with synthetic Tier 2 data.

---

## GET /projects
Query params: `page` (int, default 1), `page_size` (int, default 50),
`sort_by` (str: `risk_score` | `sanctioned_cost_inr` | `completion_certified_date`, default `risk_score`),
`order` (`asc` | `desc`, default `desc`),
`state` (optional str filter), `work_category` (optional str filter),
`min_risk` (optional int 0-100), `contractor_id` (optional str filter)

Response:
```json
{
  "total": 3000,
  "page": 1,
  "page_size": 50,
  "results": [
    {
      "project_id": "MPLAD-00003",
      "mp_constituency": "Nalgonda",
      "state": "Telangana",
      "work_category": "Health Sub-Centre",
      "contractor_id": "CTR-0187",
      "sanctioned_cost_inr": 11188624.05,
      "risk_score": 87,
      "top_anomaly_type": "cost_inflation"
    }
  ]
}
```

## GET /projects/{project_id}
Response: all displayable raw project fields (excluding `_ground_truth_*`) + full scoring detail.
`reasons` always contains at least one item. `nearby_projects` uses the local
exact-distance 2 km fallback in development; production uses PostGIS geography
and `ST_DWithin`.
```json
{
  "project_id": "MPLAD-00003",
  "mp_constituency": "Nalgonda",
  "state": "Telangana",
  "work_category": "Health Sub-Centre",
  "units": 1.65,
  "contractor_id": "CTR-0187",
  "sanctioned_cost_inr": 11188624.05,
  "regional_baseline_cost_inr": 5280000.0,
  "recommended_date": "2022-06-11",
  "sanction_date": "2022-09-04",
  "start_date": "2022-09-27",
  "completion_certified_date": "2023-11-30",
  "fund_release_date": "2023-12-18",
  "location": {"type": "Point", "coordinates": [78.7046, 17.4774]},
  "risk_score": 87,
  "reasons": [
    {"code": "cost_inflation", "text": "Cost exceeds regional baseline by 112% (₹1.12Cr vs ₹52.8L expected)"}
  ],
  "nearby_projects": ["MPLAD-00042", "MPLAD-00099"]
}
```

## GET /contractors/{contractor_id}
```json
{
  "contractor_id": "CTR-0187",
  "total_projects": 14,
  "avg_risk_score": 61,
  "flagged_project_count": 6,
  "constituencies": ["Nalgonda", "Warangal"],
  "projects": ["MPLAD-00003", "MPLAD-00042"]
}
```

## GET /stats/summary
```json
{
  "total_projects": 3000,
  "total_flagged": 480,
  "total_sanctioned_inr": 4210000000,
  "avg_risk_score": 34.2
}
```

## POST /projects/rescan
No body required. Re-runs scoring pipeline on current dataset.
Response: `{"status": "ok", "rescored_count": 3000}`

`rescan` rebuilds the seven-feature matrix and scorer cache from the local
synthetic CSV. It does not read or use evaluation labels.

---

## Error shape (all endpoints)
```json
{ "error": "message", "detail": "optional extra context" }
```
Use standard HTTP status codes (404 for missing project/contractor, 422 for bad query params).
