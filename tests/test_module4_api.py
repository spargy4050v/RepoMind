"""Contract tests for the local synthetic-data FastAPI service."""

from __future__ import annotations

from fastapi.testclient import TestClient
import backend.api.main as api_module
import secrets

from backend.api.main import app
from backend.api.main import _reason_code


client = TestClient(app)


def auth_headers() -> dict[str, str]:
    """Create a local demo session for protected API contract tests."""
    response = client.post("/auth/login", json={"username": "demo", "password": "demo123"})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['token']}"}


def test_projects_endpoint_paginates_filters_and_hides_evaluation_fields() -> None:
    """The list API must return the documented compact, unlabeled project shape."""
    response = client.get("/projects", params={"page": 1, "page_size": 3, "min_risk": 70}, headers=auth_headers())
    assert response.status_code == 200
    payload = response.json()
    assert payload["page_size"] == 3
    assert len(payload["results"]) <= 3
    assert all(result["risk_score"] >= 70 for result in payload["results"])
    assert not any(key.startswith("_ground_truth_") for result in payload["results"] for key in result)


def test_project_detail_includes_coded_reasons_and_contract_error_shape() -> None:
    """Detail responses must remain explainable and missing projects use the shared error shape."""
    headers = auth_headers()
    listed = client.get("/projects", params={"page_size": 1}, headers=headers).json()["results"][0]
    detail = client.get(f"/projects/{listed['project_id']}", headers=headers)
    assert detail.status_code == 200
    assert detail.json()["reasons"]
    assert {"code", "text"}.issubset(detail.json()["reasons"][0])
    assert not any(key.startswith("_ground_truth_") for key in detail.json())
    missing = client.get("/projects/not-a-project", headers=headers)
    assert missing.status_code == 404
    assert missing.json()["error"]


def test_detector_agreement_uses_a_positive_corroboration_reason_code() -> None:
    """Two independent detector flags must not be presented as no warning."""
    assert _reason_code("Flagged by both isolation-based and neighborhood-based detection.") == "detector_agreement"


def test_summary_contractor_and_rescan_endpoints() -> None:
    """Dashboard support endpoints return local synthetic dataset aggregates."""
    headers = auth_headers()
    first = client.get("/projects", params={"page_size": 1}, headers=headers).json()["results"][0]
    contractor = client.get(f"/contractors/{first['contractor_id']}", headers=headers)
    assert contractor.status_code == 200
    assert first["project_id"] in contractor.json()["projects"]
    assert client.get("/stats/summary", headers=headers).json()["total_projects"] == 3_000
    assert client.post("/projects/rescan", headers=headers).json() == {"status": "ok", "rescored_count": 3_000}


def test_dashboard_origin_is_allowed_to_call_the_api() -> None:
    """The separately served dashboard must receive CORS permission from the local API."""
    response = client.options(
        "/projects",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"


def test_auth_history_and_portfolio_endpoints_remain_local_and_explainable() -> None:
    """Demo authentication protects new review views and records a rescan audit entry."""
    assert client.get("/history").status_code == 401
    headers = auth_headers()
    assert client.get("/analysis/portfolio", headers=headers).json()["synthetic"] is True
    assert client.post("/projects/rescan", headers=headers).status_code == 200
    history = client.get("/history", headers=headers).json()
    assert any(entry["action"] == "rescan" and entry["user"] == "demo" for entry in history)
    logout = client.post("/auth/logout", headers=headers)
    assert logout.status_code == 200
    assert client.get("/projects", headers=headers).status_code == 401


def test_verify_upload_returns_coded_reasons_and_audits_the_authenticated_user(monkeypatch) -> None:
    """Upload verification must retain the single-record inference path and audit result."""
    monkeypatch.setattr(api_module, "score_uploaded_scheme", lambda _: {"flagged_by_both": False, "isolation_forest_flag": True, "lof_flag": False, "reasons": ["Funds were released 2 days before certified completion."]})
    headers = auth_headers()
    response = client.post("/verify/upload", json={"record": {"cost_ratio": 2}}, headers=headers)
    assert response.status_code == 200
    payload = response.json()
    assert payload["results"][0]["reasons"][0]["code"] == "payment_before_completion"
    saved = client.get(f"/uploads/{payload['upload_id']}", headers=headers)
    assert saved.status_code == 200
    assert saved.json()["record_count"] == 1
    assert any(entry["action"] == "upload" and entry["upload_id"] == payload["upload_id"] for entry in client.get("/history", headers=headers).json())


def test_local_account_registration_and_login() -> None:
    """A registered local reviewer can authenticate without the shared demo password."""
    username = f"reviewer_{secrets.token_hex(4)}"
    created = client.post("/auth/register", json={"username": username, "password": "local-pass-123"})
    assert created.status_code == 200
    assert created.json()["username"] == username
    assert client.get("/projects", headers={"Authorization": f"Bearer {created.json()['token']}"}).status_code == 200
    assert client.post("/auth/login", json={"username": username, "password": "wrong-pass"}).status_code == 401
    assert client.post("/auth/login", json={"username": username, "password": "local-pass-123"}).status_code == 200


def test_simulator_and_persisted_alert_statuses_use_live_scoring() -> None:
    """The what-if tool and alert queue remain explainable, authenticated API data."""
    headers = auth_headers()
    simulation = client.post("/simulate", json={"cost_ratio": 3.0, "payment_gap_days": -10}, headers=headers)
    assert simulation.status_code == 200
    assert 0 <= simulation.json()["risk_score"] <= 100
    assert simulation.json()["reasons"] and "breakdown" in simulation.json()
    queue = client.get("/alerts", headers=headers)
    assert queue.status_code == 200 and queue.json()
    alert = queue.json()[0]
    updated = client.patch(f"/alerts/{alert['alert_id']}", json={"status": "under_review"}, headers=headers)
    assert updated.status_code == 200
    assert updated.json()["status"] == "under_review"
    refreshed = client.get("/alerts", headers=headers)
    assert refreshed.status_code == 200
    assert next(item for item in refreshed.json() if item["alert_id"] == alert["alert_id"])["status"] == "under_review"
