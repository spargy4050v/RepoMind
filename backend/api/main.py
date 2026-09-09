"""Offline FastAPI service for the calibrated synthetic MPLAD project dataset."""

from __future__ import annotations

from functools import lru_cache
import os
import hashlib
import json
import secrets
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated, Final, Literal

import numpy as np
import pandas as pd
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from backend.ml.features import DATASET_PATH, FEATURE_COLUMNS, build_feature_matrix
from backend.ml.scorer import REASONS_COLUMN, RISK_SCORE_COLUMN, score_feature_matrix, score_projects
from backend.ml.inference import score_uploaded_scheme
from backend.ml.ingest import extract_upload
from backend.external_context import external_context_status


APP_TITLE: Final[str] = "MPLAD Trace API"
NEARBY_RADIUS_METRES: Final[float] = 2_000.0
EARTH_RADIUS_METRES: Final[float] = 6_371_008.8
app = FastAPI(title=APP_TITLE, version="0.1.0")
DEMO_DB: Final[str] = str(Path(__file__).resolve().parents[2] / "data" / "demo_access.sqlite3")
DEMO_USERNAME: Final[str] = os.getenv("MPLAD_TRACE_DEMO_USERNAME", "demo")
DEMO_PASSWORD: Final[str] = os.getenv("MPLAD_TRACE_DEMO_PASSWORD", "demo123")
PASSWORD_ITERATIONS: Final[int] = 310_000

def _db() -> sqlite3.Connection:
    """Open the local-only demo access/audit store; it is never a model input."""
    connection = sqlite3.connect(DEMO_DB)
    connection.execute("CREATE TABLE IF NOT EXISTS sessions (token TEXT PRIMARY KEY, username TEXT NOT NULL)")
    connection.execute("CREATE TABLE IF NOT EXISTS users (username TEXT PRIMARY KEY, password_hash TEXT NOT NULL, salt TEXT NOT NULL, created_at TEXT NOT NULL)")
    connection.execute("CREATE TABLE IF NOT EXISTS uploads (id INTEGER PRIMARY KEY, username TEXT NOT NULL, created_at TEXT NOT NULL, record_count INTEGER NOT NULL, results TEXT NOT NULL)")
    connection.execute("CREATE TABLE IF NOT EXISTS alerts (id INTEGER PRIMARY KEY, project_id TEXT UNIQUE NOT NULL, anomaly_type TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'new')")
    connection.execute("CREATE TABLE IF NOT EXISTS history (id INTEGER PRIMARY KEY, timestamp TEXT, username TEXT, action TEXT, input_summary TEXT, risk_score REAL, risk_tier TEXT, reasons TEXT, upload_id INTEGER)")
    columns = {row[1] for row in connection.execute("PRAGMA table_info(history)")}
    if "upload_id" not in columns:
        connection.execute("ALTER TABLE history ADD COLUMN upload_id INTEGER")
    _ensure_demo_user(connection)
    return connection


def _password_hash(password: str, salt: bytes) -> str:
    """Derive a salted local password hash for the hackathon account store."""
    return hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, PASSWORD_ITERATIONS).hex()


def _ensure_demo_user(connection: sqlite3.Connection) -> None:
    """Keep a documented demo account available without storing its plaintext password."""
    if connection.execute("SELECT 1 FROM users WHERE username = ?", (DEMO_USERNAME,)).fetchone() is None:
        salt = secrets.token_bytes(16)
        connection.execute("INSERT INTO users (username, password_hash, salt, created_at) VALUES (?, ?, ?, ?)", (DEMO_USERNAME, _password_hash(DEMO_PASSWORD, salt), salt.hex(), datetime.now(timezone.utc).isoformat()))


def _new_session(connection: sqlite3.Connection, username: str) -> dict[str, str]:
    """Create an opaque local session token after account credentials are verified."""
    token = secrets.token_urlsafe(32)
    connection.execute("INSERT INTO sessions (token, username) VALUES (?, ?)", (token, username))
    return {"token": token, "username": username}

@app.middleware("http")
async def demo_auth(request: Request, call_next: object) -> object:
    """Gate dashboard APIs with short-lived local demo tokens, excluding login and docs."""
    public = {"/auth/login", "/auth/register", "/openapi.json", "/docs", "/docs/oauth2-redirect"}
    if request.method == "OPTIONS" or request.url.path in public:
        return await call_next(request)  # type: ignore[misc]
    token = request.headers.get("Authorization", "").removeprefix("Bearer ")
    with _db() as connection:
        session = connection.execute("SELECT username FROM sessions WHERE token = ?", (token,)).fetchone()
    if not session:
        return JSONResponse(status_code=401, content={"error": "Authentication required", "detail": "Sign in with the local demo account."})
    request.state.username = str(session[0])
    return await call_next(request)  # type: ignore[misc]

@app.post("/auth/login")
async def login(payload: dict[str, str]) -> dict[str, str]:
    """Create a self-contained demo session; this is not government authentication."""
    username, password = payload.get("username", "").strip(), payload.get("password", "")
    with _db() as connection:
        user = connection.execute("SELECT password_hash, salt FROM users WHERE username = ?", (username,)).fetchone()
        if user is None or not secrets.compare_digest(_password_hash(password, bytes.fromhex(str(user[1]))), str(user[0])):
            raise HTTPException(status_code=401, detail="Invalid username or password")
        return _new_session(connection, username)


@app.post("/auth/register")
async def register(payload: dict[str, str]) -> dict[str, str]:
    """Create a local reviewer account with a salted password hash, never government SSO."""
    username, password = payload.get("username", "").strip(), payload.get("password", "")
    valid_username = 3 <= len(username) <= 64 and all(character.isalnum() or character in "_.-" for character in username)
    if not valid_username:
        raise HTTPException(status_code=422, detail="Username must be 3-64 characters using letters, numbers, _, ., or -")
    if len(password) < 8:
        raise HTTPException(status_code=422, detail="Password must contain at least 8 characters")
    salt = secrets.token_bytes(16)
    with _db() as connection:
        try:
            connection.execute("INSERT INTO users (username, password_hash, salt, created_at) VALUES (?, ?, ?, ?)", (username, _password_hash(password, salt), salt.hex(), datetime.now(timezone.utc).isoformat()))
        except sqlite3.IntegrityError as error:
            raise HTTPException(status_code=409, detail="That username is already registered") from error
        return _new_session(connection, username)

@app.post("/auth/logout")
def logout(request: Request) -> dict[str, str]:
    """Invalidate the caller's local demo session."""
    token = request.headers.get("Authorization", "").removeprefix("Bearer ")
    with _db() as connection:
        connection.execute("DELETE FROM sessions WHERE token = ?", (token,))
    return {"status": "ok"}

# The Vite proxy handles this in local development. A separately hosted
# dashboard supplies its origin through MPLAD_TRACE_CORS_ORIGINS.
CORS_ORIGINS: Final[tuple[str, ...]] = tuple(
    origin.strip()
    for origin in os.getenv("MPLAD_TRACE_CORS_ORIGINS", "http://localhost:5173").split(",")
    if origin.strip()
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=list(CORS_ORIGINS),
    allow_credentials=False,
    allow_methods=["GET", "POST", "PATCH"],
    allow_headers=["*"],
)


@app.exception_handler(HTTPException)
async def http_error_handler(_: Request, exc: HTTPException) -> JSONResponse:
    """Return the API contract's consistent error object for known HTTP errors."""
    detail = exc.detail if isinstance(exc.detail, str) else None
    return JSONResponse(status_code=exc.status_code, content={"error": detail or "Request failed", "detail": detail})


@app.exception_handler(RequestValidationError)
async def validation_error_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
    """Return bad query parameters in the contract's 422 error shape."""
    return JSONResponse(status_code=422, content={"error": "Invalid request parameters", "detail": exc.errors()})


@lru_cache(maxsize=1)
def _project_table() -> pd.DataFrame:
    """Load displayable synthetic records while excluding evaluation-only ground-truth fields."""
    source = pd.read_csv(DATASET_PATH)
    return source.loc[:, [column for column in source.columns if not column.startswith("_ground_truth_")]].copy()


@lru_cache(maxsize=1)
def _scored_table() -> pd.DataFrame:
    """Combine synthetic project fields with unlabeled risk scores and explanations."""
    scored = score_projects(DATASET_PATH)
    return _project_table().merge(scored, on="project_id", validate="one_to_one")


def _reason_code(text: str) -> str:
    """Map each transparent scorer explanation to a stable API reason code."""
    if text.startswith("Sanctioned cost"):
        return "cost_inflation"
    if text.startswith("Certified completion"):
        return "implausibly_fast_completion"
    if text.startswith("Funds were released"):
        return "payment_before_completion"
    if text.startswith("Contractor holds"):
        return "contractor_concentration"
    if "projects lie within" in text:
        return "geographic_clustering"
    if text.startswith("Sanction followed"):
        return "sanction_lag"
    return "no_material_warning"


def _reason_objects(reasons: list[str]) -> list[dict[str, str]]:
    """Convert scorer text into the stable, coded reason objects exposed by the API."""
    return [{"code": _reason_code(text), "text": text} for text in reasons]


def _breakdown(reasons: list[str], score: float) -> dict[str, float]:
    """Expose transparent category signals derived from the scorer's actual reasons."""
    categories = {"cost": 0.0, "completion": 0.0, "payment": 0.0, "contractor": 0.0, "geographic": 0.0, "sanction_lag": 0.0, "model": 0.0}
    mapping = {"cost_inflation": "cost", "implausibly_fast_completion": "completion", "payment_before_completion": "payment", "contractor_concentration": "contractor", "geographic_clustering": "geographic", "sanction_lag": "sanction_lag"}
    for reason in reasons:
        category = mapping.get(_reason_code(reason))
        if category:
            categories[category] = max(categories[category], score)
    categories["model"] = score if not any(categories.values()) else round(score * 0.35, 2)
    return categories


def _json_scalar(value: object) -> object:
    """Convert pandas/NumPy scalar values to JSON-native types at the API boundary."""
    if isinstance(value, np.generic):
        return value.item()
    return value


def _nearby_project_ids(project: pd.Series, projects: pd.DataFrame) -> list[str]:
    """Find local-demo nearby projects with exact great-circle distance, never coordinate buckets.

    This is offline support only. Production geographic lookups use the PostGIS
    geography `ST_DWithin` query specified in the schema and API contract.
    """
    latitudes = np.radians(pd.to_numeric(projects["latitude"], errors="coerce").to_numpy(dtype=float))
    longitudes = np.radians(pd.to_numeric(projects["longitude"], errors="coerce").to_numpy(dtype=float))
    latitude, longitude = np.radians(float(project["latitude"])), np.radians(float(project["longitude"]))
    haversine = np.sin((latitudes - latitude) / 2) ** 2
    haversine += np.cos(latitude) * np.cos(latitudes) * np.sin((longitudes - longitude) / 2) ** 2
    distances = 2 * EARTH_RADIUS_METRES * np.arcsin(np.sqrt(np.clip(haversine, 0, 1)))
    nearby = projects.loc[(distances <= NEARBY_RADIUS_METRES) & (projects["project_id"] != project["project_id"]), "project_id"]
    return nearby.astype(str).sort_values().tolist()


def _list_project(project: pd.Series) -> dict[str, object]:
    """Build a compact list response without exposing raw coordinates or evaluation labels."""
    reasons = project[REASONS_COLUMN]
    codes = [_reason_code(text) for text in reasons]
    top_code = next((code for code in codes if code != "no_material_warning"), None)
    return {
        "project_id": str(project["project_id"]),
        "mp_constituency": str(project["mp_constituency"]),
        "state": str(project["state"]),
        "work_category": str(project["work_category"]),
        "contractor_id": str(project["contractor_id"]),
        "sanctioned_cost_inr": float(project["sanctioned_cost_inr"]),
        "risk_score": round(float(project[RISK_SCORE_COLUMN]), 2),
        "top_anomaly_type": top_code,
    }


@app.get("/projects")
def list_projects(
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 50,
    sort_by: Literal["risk_score", "sanctioned_cost_inr", "completion_certified_date"] = "risk_score",
    order: Literal["asc", "desc"] = "desc",
    state: str | None = None,
    work_category: str | None = None,
    min_risk: Annotated[int | None, Query(ge=0, le=100)] = None,
    contractor_id: str | None = None,
) -> dict[str, object]:
    """Return a paginated, filterable priority queue of synthetic projects."""
    projects = _scored_table()
    filtered = projects.copy()
    for column, value in (("state", state), ("work_category", work_category), ("contractor_id", contractor_id)):
        if value is not None:
            filtered = filtered.loc[filtered[column].eq(value)]
    if min_risk is not None:
        filtered = filtered.loc[filtered[RISK_SCORE_COLUMN] >= min_risk]
    filtered = filtered.sort_values(sort_by, ascending=order == "asc", kind="mergesort")
    start = (page - 1) * page_size
    return {"total": int(len(filtered)), "page": page, "page_size": page_size, "results": [_list_project(row) for _, row in filtered.iloc[start : start + page_size].iterrows()]}


@app.get("/projects/{project_id}")
def get_project(project_id: str) -> dict[str, object]:
    """Return one synthetic project's display fields, coded explanations, and local nearby IDs."""
    projects = _scored_table()
    matches = projects.loc[projects["project_id"].eq(project_id)]
    if matches.empty:
        raise HTTPException(status_code=404, detail=f"Project {project_id} was not found")
    project = matches.iloc[0]
    response = {
        column: _json_scalar(value)
        for column, value in project.items()
        if column not in {"latitude", "longitude", REASONS_COLUMN}
    }
    response["risk_score"] = round(float(project[RISK_SCORE_COLUMN]), 2)
    response["location"] = {"type": "Point", "coordinates": [float(project["longitude"]), float(project["latitude"])]}
    response["reasons"] = _reason_objects(project[REASONS_COLUMN])
    response["nearby_projects"] = _nearby_project_ids(project, projects)
    return response


@app.get("/contractors/{contractor_id}")
def get_contractor(contractor_id: str) -> dict[str, object]:
    """Summarise one contractor's synthetic project portfolio and flagged work."""
    projects = _scored_table().loc[lambda frame: frame["contractor_id"].eq(contractor_id)]
    if projects.empty:
        raise HTTPException(status_code=404, detail=f"Contractor {contractor_id} was not found")
    return {
        "contractor_id": contractor_id,
        "total_projects": int(len(projects)),
        "avg_risk_score": round(float(projects[RISK_SCORE_COLUMN].mean()), 2),
        "flagged_project_count": int((projects[RISK_SCORE_COLUMN] >= 40).sum()),
        "constituencies": sorted(projects["mp_constituency"].astype(str).unique().tolist()),
        "projects": projects.sort_values(RISK_SCORE_COLUMN, ascending=False)["project_id"].astype(str).tolist(),
    }


@app.get("/stats/summary")
def summary() -> dict[str, object]:
    """Return dataset-level synthetic-project totals for the dashboard header."""
    projects = _scored_table()
    return {
        "total_projects": int(len(projects)),
        "total_flagged": int((projects[RISK_SCORE_COLUMN] >= 40).sum()),
        "total_sanctioned_inr": float(projects["sanctioned_cost_inr"].sum()),
        "avg_risk_score": round(float(projects[RISK_SCORE_COLUMN].mean()), 2),
    }


@app.post("/projects/rescan")
def rescan_projects(request: Request) -> dict[str, object]:
    """Refresh the local unlabeled scoring cache for the current synthetic CSV."""
    _scored_table.cache_clear()
    _project_table.cache_clear()
    rescored = _scored_table()
    # A rescan is a review action too; retain a local audit record without
    # exposing or consuming evaluation labels.
    with _db() as connection:
        connection.execute(
            "INSERT INTO history (timestamp, username, action, input_summary, risk_score, risk_tier, reasons) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (datetime.now(timezone.utc).isoformat(), request.state.username, "rescan", f"{len(rescored)} synthetic Tier 2 projects", None, None, "[]"),
        )
    return {"status": "ok", "rescored_count": int(len(rescored))}

@app.get("/analysis/portfolio")
def portfolio_analysis() -> dict[str, object]:
    """Summarise synthetic Tier 2 risks for review only; never use hidden labels."""
    frame = _scored_table().copy()
    frame["risk_tier"] = pd.cut(frame[RISK_SCORE_COLUMN], [-1, 39.999, 70, 100], labels=["green", "amber", "red"])
    high_risk = frame.loc[frame[RISK_SCORE_COLUMN] > 70, REASONS_COLUMN]
    reason_codes: dict[str, int] = {}
    for reasons in high_risk:
        for reason in reasons:
            code = _reason_code(str(reason))
            if code != "no_material_warning":
                reason_codes[code] = reason_codes.get(code, 0) + 1
    return {"synthetic": True, "tiers": frame["risk_tier"].value_counts().to_dict(), "states": frame.groupby("state")[RISK_SCORE_COLUMN].mean().round(2).to_dict(), "work_categories": frame.groupby("work_category")[RISK_SCORE_COLUMN].mean().round(2).to_dict(), "contractors": frame.groupby("contractor_id")[RISK_SCORE_COLUMN].mean().nlargest(20).round(2).to_dict(), "high_risk_reason_codes": dict(sorted(reason_codes.items(), key=lambda item: (-item[1], item[0])))}


@app.get("/context/external-status")
def external_status() -> dict[str, object]:
    """Expose optional public aggregate context status, never model input or Tier 2 data."""
    return external_context_status()


@app.post("/simulate")
def simulate(payload: dict[str, object]) -> dict[str, object]:
    """Run the existing hybrid scorer against a synthetic what-if feature row."""
    features = build_feature_matrix(DATASET_PATH)
    row = features.loc[:, FEATURE_COLUMNS].median().to_dict()
    for column in FEATURE_COLUMNS:
        if column in payload:
            value = pd.to_numeric(pd.Series([payload[column]]), errors="coerce").iloc[0]
            if not np.isfinite(value):
                raise HTTPException(status_code=422, detail=f"{column} must be finite")
            row[column] = float(value)
    candidate = pd.DataFrame([{"project_id": "SIMULATION", **row}])
    scored = score_feature_matrix(pd.concat([features, candidate], ignore_index=True)).iloc[-1]
    reasons = [str(reason) for reason in scored[REASONS_COLUMN]]
    score = round(float(scored[RISK_SCORE_COLUMN]), 2)
    return {"risk_score": score, "reasons": _reason_objects(reasons), "breakdown": _breakdown(reasons, score)}


def _seed_alerts(connection: sqlite3.Connection) -> None:
    """Create persistent review alerts for current amber/red synthetic projects once."""
    for _, project in _scored_table().loc[lambda frame: frame[RISK_SCORE_COLUMN] >= 40].iterrows():
        reasons = [str(reason) for reason in project[REASONS_COLUMN]]
        code = next((_reason_code(reason) for reason in reasons if _reason_code(reason) != "no_material_warning"), "model_signal")
        connection.execute("INSERT OR IGNORE INTO alerts (project_id, anomaly_type, status) VALUES (?, ?, 'new')", (str(project["project_id"]), code))


@app.get("/alerts")
def alerts(status: Literal["new", "under_review", "investigating", "resolved"] | None = None, search: str | None = None) -> list[dict[str, object]]:
    """Return persisted reviewer alerts joined to live explainable synthetic scores."""
    with _db() as connection:
        _seed_alerts(connection)
        rows = connection.execute("SELECT id, project_id, anomaly_type, status FROM alerts").fetchall()
    table = _scored_table().set_index("project_id")
    results = []
    for alert_id, project_id, anomaly_type, alert_status in rows:
        if project_id not in table.index:
            continue
        project = table.loc[project_id]
        if status and alert_status != status:
            continue
        haystack = f"{alert_id} {project_id} {anomaly_type} {project['contractor_id']} {project['mp_constituency']}".lower()
        if search and search.lower() not in haystack:
            continue
        score = round(float(project[RISK_SCORE_COLUMN]), 2)
        results.append({"alert_id": alert_id, "project_id": project_id, "anomaly_type": anomaly_type, "risk_score": score, "severity": "red" if score > 70 else "amber", "status": alert_status})
    return sorted(results, key=lambda item: float(item["risk_score"]), reverse=True)


@app.patch("/alerts/{alert_id}")
def update_alert(alert_id: int, payload: dict[str, str]) -> dict[str, object]:
    """Persist an investigator's allowed alert-status transition."""
    status = payload.get("status")
    if status not in {"new", "under_review", "investigating", "resolved"}:
        raise HTTPException(status_code=422, detail="Invalid alert status")
    with _db() as connection:
        _seed_alerts(connection)
        connection.execute("UPDATE alerts SET status = ? WHERE id = ?", (status, alert_id))
    matches = [item for item in alerts() if item["alert_id"] == alert_id]
    if not matches:
        raise HTTPException(status_code=404, detail=f"Alert {alert_id} was not found")
    return matches[0]

@app.get("/history")
def history(request: Request) -> list[dict[str, object]]:
    """Return the authenticated user's local audit entries; audit data is not model input."""
    with _db() as connection:
        rows = connection.execute("SELECT timestamp, username, action, input_summary, risk_score, risk_tier, reasons, upload_id FROM history WHERE username = ? ORDER BY id DESC", (request.state.username,)).fetchall()
    return [{"timestamp": row[0], "user": row[1], "action": row[2], "input_summary": row[3], "risk_score": row[4], "risk_tier": row[5], "reasons": json.loads(row[6]), "upload_id": row[7]} for row in rows]


@app.get("/uploads/{upload_id}")
def get_upload(upload_id: int, request: Request) -> dict[str, object]:
    """Return one user's persisted upload batch and explainable review results."""
    with _db() as connection:
        row = connection.execute("SELECT id, created_at, record_count, results FROM uploads WHERE id = ? AND username = ?", (upload_id, request.state.username)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail=f"Upload {upload_id} was not found")
    return {"upload_id": row[0], "created_at": row[1], "record_count": row[2], "results": json.loads(row[3])}


def _uploaded_result(record: dict[str, object]) -> dict[str, object]:
    """Score a reviewer-confirmed record solely through the existing inference path."""
    inference = score_uploaded_scheme(record)
    score = 85.0 if inference["flagged_by_both"] else 60.0 if inference["isolation_forest_flag"] or inference["lof_flag"] else 20.0
    reasons = _reason_objects([str(text) for text in inference["reasons"]])
    tier = "red" if score > 70 else "amber" if score >= 40 else "green"
    return {"risk_score": score, "risk_tier": tier, "reasons": reasons, "message": "Risk/anomaly likelihood only; not a fraud verdict."}


def _deterministic_story(record: dict[str, object], result: dict[str, object]) -> str:
    """Create a traceable narrative from confirmed fields and actual scorer evidence."""
    sanctioned = record.get("sanctioned_cost_inr", "unknown")
    baseline = record.get("regional_baseline_cost_inr", "unknown")
    evidence = "; ".join(reason["text"] for reason in result["reasons"])
    return (f"The confirmed project was sanctioned for ₹{sanctioned} against a regional baseline of ₹{baseline}. "
            f"Its review score is {result['risk_score']:.0f}/100 ({result['risk_tier']}). "
            f"The existing detector's evidence is: {evidence}. This is a review signal, not a fraud verdict.")


@app.post("/upload/extract")
async def extract_file(request: Request) -> dict[str, object]:
    """Extract a single file for editable review; this endpoint never scores it.

    The browser posts raw file bytes with ``X-Filename`` so the local service
    avoids a required multipart runtime dependency while retaining the same
    one-file upload semantics.
    """
    filename = request.headers.get("X-Filename", "")
    if not filename:
        raise HTTPException(status_code=422, detail="Upload must include an X-Filename header")
    try:
        extracted = extract_upload(filename, await request.body())
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    return {"format": extracted.format, "record": extracted.record, "confidence": extracted.confidence, "source": extracted.source}


@app.post("/upload/score")
def score_extracted_upload(payload: dict[str, object], request: Request) -> dict[str, object]:
    """Persist a confirmed extraction after the shared inference validation succeeds."""
    record = payload.get("record")
    extraction = payload.get("extraction", {})
    if not isinstance(record, dict) or not isinstance(extraction, dict):
        raise HTTPException(status_code=422, detail="Upload scoring requires a confirmed record and extraction metadata")
    record = {str(key): value for key, value in record.items() if not str(key).startswith("_ground_truth_")}
    try:
        result = _uploaded_result(record)
    except (ValueError, FileNotFoundError, TypeError) as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    created_at = datetime.now(timezone.utc).isoformat()
    output = {**result, "story": {"deterministic": _deterministic_story(record, result), "ai_generated": False}, "evidence": {"confirmed_record": record, "confidence": extraction.get("confidence", {}), "source": extraction.get("source", {})}}
    with _db() as connection:
        cursor = connection.execute("INSERT INTO uploads (username, created_at, record_count, results) VALUES (?, ?, ?, ?)", (request.state.username, created_at, 1, json.dumps([output])))
        upload_id = int(cursor.lastrowid)
        connection.execute("INSERT INTO history (timestamp, username, action, input_summary, risk_score, risk_tier, reasons, upload_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?)", (created_at, request.state.username, "document_upload", f"{extraction.get('format', 'document')} project record", result["risk_score"], result["risk_tier"], json.dumps(result["reasons"]), upload_id))
    return {"upload_id": upload_id, "record_count": 1, "results": [output], "message": result["message"]}

@app.post("/verify/upload")
def verify_upload(payload: dict[str, object], request: Request) -> dict[str, object]:
    """Score one or more validated records through the existing inference pipeline.

    The browser may parse a CSV into ``records`` before posting it. Each record
    still follows the single-record inference validation and no upload retrains
    or extends the detector.
    """
    records = payload.get("records")
    if records is None:
        records = [payload.get("record", payload)]
    if not isinstance(records, list) or not records or not all(isinstance(record, dict) for record in records):
        raise HTTPException(status_code=422, detail="Upload must contain one record or a non-empty records array")
    results: list[dict[str, object]] = []
    for record in records:
        try:
            inference = score_uploaded_scheme(record)
        except (ValueError, FileNotFoundError, TypeError) as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        score = 85.0 if inference["flagged_by_both"] else 60.0 if inference["isolation_forest_flag"] or inference["lof_flag"] else 20.0
        reasons = _reason_objects([str(text) for text in inference["reasons"]])
        tier = "red" if score > 70 else "amber" if score >= 40 else "green"
        results.append({"risk_score": score, "risk_tier": tier, "reasons": reasons, "message": "Risk/anomaly likelihood only; not a fraud verdict."})
    created_at = datetime.now(timezone.utc).isoformat()
    with _db() as connection:
        first = results[0]
        cursor = connection.execute("INSERT INTO uploads (username, created_at, record_count, results) VALUES (?, ?, ?, ?)", (request.state.username, created_at, len(results), json.dumps(results)))
        upload_id = int(cursor.lastrowid)
        connection.execute("INSERT INTO history (timestamp, username, action, input_summary, risk_score, risk_tier, reasons, upload_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?)", (created_at, request.state.username, "upload", f"{len(results)} uploaded project record(s)", first["risk_score"], first["risk_tier"], json.dumps(first["reasons"]), upload_id))
    return {"upload_id": upload_id, "record_count": len(results), "results": results, "message": "Risk/anomaly likelihood only; not a fraud verdict."}
