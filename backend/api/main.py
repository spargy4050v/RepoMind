"""Offline FastAPI service for the calibrated synthetic MPLAD project dataset."""

from __future__ import annotations

from functools import lru_cache
from typing import Annotated, Final, Literal

import numpy as np
import pandas as pd
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from backend.ml.features import DATASET_PATH
from backend.ml.scorer import REASONS_COLUMN, RISK_SCORE_COLUMN, score_projects


APP_TITLE: Final[str] = "MPLAD Trace API"
NEARBY_RADIUS_METRES: Final[float] = 2_000.0
EARTH_RADIUS_METRES: Final[float] = 6_371_008.8
app = FastAPI(title=APP_TITLE, version="0.1.0")


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
def rescan_projects() -> dict[str, object]:
    """Refresh the local unlabeled scoring cache for the current synthetic CSV."""
    _scored_table.cache_clear()
    _project_table.cache_clear()
    rescored = _scored_table()
    return {"status": "ok", "rescored_count": int(len(rescored))}
