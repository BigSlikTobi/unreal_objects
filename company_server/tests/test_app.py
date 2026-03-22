"""Tests for the company server FastAPI endpoints."""

import pytest
from fastapi.testclient import TestClient

from company_server import app as app_module
from company_server.app import app
from company_server.clock import CompanyClock
from company_server.state import CompanyState
from support_company.models import CaseType, SupportCase


@pytest.fixture(autouse=True)
def setup_state():
    """Inject test state directly into the app module."""
    from datetime import datetime

    state = CompanyState()
    state.seed_customers(5)
    state.seed_orders(10)
    clock = CompanyClock(acceleration=1.0, virtual_start=datetime(2026, 1, 5, 12, 0, 0))

    app_module._state = state
    app_module._clock = clock
    app_module._config = app_module.CompanyConfig()
    app_module._group_id = "test-group-id"

    yield state

    app_module._state = None
    app_module._clock = None
    app_module._config = None
    app_module._group_id = None


@pytest.fixture
def client():
    return TestClient(app, raise_server_exceptions=False)


def test_get_status(client):
    resp = client.get("/api/v1/status")
    assert resp.status_code == 200
    data = resp.json()
    assert "virtual_time" in data
    assert "stats" in data


def test_get_clock(client):
    resp = client.get("/api/v1/clock")
    assert resp.status_code == 200
    data = resp.json()
    assert "virtual_time" in data
    assert "acceleration" in data
    assert "is_business_hours" in data
    assert "activity_multiplier" in data


def test_list_cases_empty(client):
    resp = client.get("/api/v1/cases")
    assert resp.status_code == 200
    assert resp.json()["total"] == 0


def test_case_lifecycle(client, setup_state):
    state = setup_state
    case = SupportCase(case_type=CaseType.REFUND_REQUEST, requested_action="Refund me")
    state.add_case(case)

    # List open cases
    resp = client.get("/api/v1/cases?status=open")
    assert resp.status_code == 200
    assert resp.json()["total"] == 1

    # Get case detail
    resp = client.get(f"/api/v1/cases/{case.case_id}")
    assert resp.status_code == 200
    assert resp.json()["case_type"] == "refund_request"

    # Assign
    resp = client.post(f"/api/v1/cases/{case.case_id}/assign", json={"bot_id": "bot-1"})
    assert resp.status_code == 200
    assert resp.json()["status"] == "assigned"

    # Resolve
    resp = client.post(f"/api/v1/cases/{case.case_id}/resolve", json={"resolution": "Refunded $50"})
    assert resp.status_code == 200
    assert resp.json()["status"] == "resolved"

    # No more open cases
    resp = client.get("/api/v1/cases?status=open")
    assert resp.json()["total"] == 0


def test_get_case_not_found(client):
    resp = client.get("/api/v1/cases/nonexistent")
    assert resp.status_code == 404


def test_assign_not_found(client):
    resp = client.post("/api/v1/cases/nonexistent/assign", json={"bot_id": "bot-1"})
    assert resp.status_code == 404


def test_list_customers(client):
    resp = client.get("/api/v1/customers")
    assert resp.status_code == 200
    assert resp.json()["total"] == 5


def test_get_customer(client, setup_state):
    state = setup_state
    cid = list(state.customers.keys())[0]
    resp = client.get(f"/api/v1/customers/{cid}")
    assert resp.status_code == 200
    assert "history" in resp.json()


def test_get_customer_not_found(client):
    resp = client.get("/api/v1/customers/nonexistent")
    assert resp.status_code == 404


def test_invalid_status_filter(client):
    resp = client.get("/api/v1/cases?status=invalid")
    assert resp.status_code == 400
