# API Contract — MPLAD Trace

Source of truth for request/response shapes. Update THIS file first if a shape
needs to change, then update backend + frontend code to match.

Base URL (dev): `http://localhost:8000`

The local development service reads the calibrated **synthetic Tier 2** CSV.
It never returns `_ground_truth_*` evaluation fields. Production storage remains
Postgres + PostGIS; the local CSV path exists for the offline demo only.

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
