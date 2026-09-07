"""Contract tests for the local synthetic-data FastAPI service."""

from __future__ import annotations

from fastapi.testclient import TestClient

from backend.api.main import app


client = TestClient(app)


def test_projects_endpoint_paginates_filters_and_hides_evaluation_fields() -> None:
    """The list API must return the documented compact, unlabeled project shape."""
    response = client.get("/projects", params={"page": 1, "page_size": 3, "min_risk": 70})
    assert response.status_code == 200
    payload = response.json()
    assert payload["page_size"] == 3
    assert len(payload["results"]) <= 3
    assert all(result["risk_score"] >= 70 for result in payload["results"])
    assert not any(key.startswith("_ground_truth_") for result in payload["results"] for key in result)


def test_project_detail_includes_coded_reasons_and_contract_error_shape() -> None:
    """Detail responses must remain explainable and missing projects use the shared error shape."""
    listed = client.get("/projects", params={"page_size": 1}).json()["results"][0]
    detail = client.get(f"/projects/{listed['project_id']}")
    assert detail.status_code == 200
    assert detail.json()["reasons"]
    assert {"code", "text"}.issubset(detail.json()["reasons"][0])
    assert not any(key.startswith("_ground_truth_") for key in detail.json())
    missing = client.get("/projects/not-a-project")
    assert missing.status_code == 404
    assert missing.json()["error"]


def test_summary_contractor_and_rescan_endpoints() -> None:
    """Dashboard support endpoints return local synthetic dataset aggregates."""
    first = client.get("/projects", params={"page_size": 1}).json()["results"][0]
    contractor = client.get(f"/contractors/{first['contractor_id']}")
    assert contractor.status_code == 200
    assert first["project_id"] in contractor.json()["projects"]
    assert client.get("/stats/summary").json()["total_projects"] == 3_000
    assert client.post("/projects/rescan").json() == {"status": "ok", "rescored_count": 3_000}
