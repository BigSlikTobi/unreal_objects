import json
import pytest
from httpx import AsyncClient, ASGITransport

from decision_center.app import app
import decision_center.app as app_module
from decision_center.store import DecisionStore

# We need to mock the Rule Engine API call in real life, but for MVP evaluator tests
# we can just use a mocked httpx transport or patch it. Since the app makes outbound
# calls, we will just patch the httpx.AsyncClient GET method.
from unittest.mock import patch, MagicMock

@pytest.mark.asyncio
async def test_evaluate_no_group():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/v1/decide?request_description=Test&context={}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["outcome"] == "APPROVE"

@pytest.fixture
def mock_rule_engine():
    with patch("decision_center.evaluator._fetch_group") as mock_get:
        yield mock_get

@pytest.mark.asyncio
async def test_evaluate_with_rules_restrictive_wins(mock_rule_engine):
    # Mock rule engine returning 1 APPROVE and 1 REJECT rule
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "id": "g1",
        "name": "Grp",
        "rules": [
            {"id": "r1", "rule_logic": "IF amount > 100 THEN REJECT"},
            {"id": "r2", "rule_logic": "IF amount < 200 THEN APPROVE"}
        ]
    }
    mock_rule_engine.return_value = mock_response

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Context has amount=150, which triggers both rules. Most restrictive wins.
        context_str = '{"amount": 150}'
        resp = await client.get(f"/v1/decide?request_description=Test&context={context_str}&group_id=g1")
        assert resp.status_code == 200
        data = resp.json()
        assert data["outcome"] == "REJECT"

@pytest.mark.asyncio
async def test_approval_flow_and_logs(mock_rule_engine):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "id": "g1",
        "name": "Grp",
        "rules": [
            {"id": "r1", "rule_logic": "IF amount > 100 THEN ASK_FOR_APPROVAL"}
        ]
    }
    mock_rule_engine.return_value = mock_response

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # 1. Ask for approval
        context_str = '{"amount": 150}'
        resp = await client.get(f"/v1/decide?request_description=NeedLaptop&context={context_str}&group_id=g1")
        assert resp.status_code == 200
        data = resp.json()
        assert data["outcome"] == "ASK_FOR_APPROVAL"
        req_id = data["request_id"]

        # 2. Check pending
        resp = await client.get("/v1/pending")
        assert resp.status_code == 200
        assert any(p["request_id"] == req_id for p in resp.json())

        # 3. Submit approval
        resp = await client.post(f"/v1/decide/{req_id}/approve", json={"approved": True, "approver": "Bob"})
        assert resp.status_code == 200

        # 4. Check chain decision log
        resp = await client.get(f"/v1/logs/chains/{req_id}")
        assert resp.status_code == 200
        chain = resp.json()
        assert chain["request_id"] == req_id
        assert len(chain["events"]) >= 2
        # Starts with REQUEST, ends with APPROVED
        assert chain["events"][0]["event_type"] == "REQUEST"
        assert chain["events"][-1]["event_type"] == "APPROVAL_STATUS"
        assert chain["events"][-1]["details"]["status"] == "APPROVED"


@pytest.mark.asyncio
async def test_pending_approval_survives_store_restart(mock_rule_engine, tmp_path, monkeypatch):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "id": "g1",
        "name": "Grp",
        "rules": [
            {"id": "r1", "rule_logic": "IF amount > 100 THEN ASK_FOR_APPROVAL"}
        ]
    }
    mock_rule_engine.return_value = mock_response

    path = tmp_path / "decision_center_store.json"
    original_store = app_module.store
    monkeypatch.setattr(app_module, "store", DecisionStore(persistence_path=path))

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post(
                "/v1/decide",
                json={
                    "request_description": "NeedLaptop",
                    "context": {"amount": 150},
                    "group_id": "g1",
                },
            )
            assert resp.status_code == 200
            req_id = resp.json()["request_id"]

        monkeypatch.setattr(app_module, "store", DecisionStore(persistence_path=path))

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            pending_resp = await client.get("/v1/pending")
            assert pending_resp.status_code == 200
            assert any(p["request_id"] == req_id for p in pending_resp.json())

            approve_resp = await client.post(
                f"/v1/decide/{req_id}/approve",
                json={"approved": True, "approver": "Alice"},
            )
            assert approve_resp.status_code == 200
    finally:
        monkeypatch.setattr(app_module, "store", original_store)


@pytest.mark.asyncio
async def test_approval_logs_atomic_entry_approved(mock_rule_engine):
    """After approve, a second atomic log entry with APPROVED decision is created."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "id": "g1",
        "name": "Grp",
        "rules": [
            {"id": "r1", "rule_logic": "IF amount > 100 THEN ASK_FOR_APPROVAL"}
        ]
    }
    mock_rule_engine.return_value = mock_response

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        context_str = '{"amount": 150}'
        resp = await client.get(f"/v1/decide?request_description=NeedLaptop&context={context_str}&group_id=g1")
        req_id = resp.json()["request_id"]

        # Submit approval
        resp = await client.post(f"/v1/decide/{req_id}/approve", json={"approved": True, "approver": "Alice"})
        assert resp.status_code == 200

        # Atomic log should have two entries for this request_id
        resp = await client.get("/v1/logs/atomic")
        entries = [e for e in resp.json() if e["request_id"] == req_id]
        assert len(entries) == 2
        assert entries[0]["decision"] == "APPROVAL_REQUIRED"
        assert entries[1]["decision"] == "APPROVED"
        assert entries[1]["request_description"] == "NeedLaptop"
        assert entries[1]["context"] == {"amount": 150}


@pytest.mark.asyncio
async def test_approval_logs_atomic_entry_rejected(mock_rule_engine):
    """After reject, a second atomic log entry with REJECTED decision is created."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "id": "g1",
        "name": "Grp",
        "rules": [
            {"id": "r1", "rule_logic": "IF amount > 100 THEN ASK_FOR_APPROVAL"}
        ]
    }
    mock_rule_engine.return_value = mock_response

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        context_str = '{"amount": 150}'
        resp = await client.get(f"/v1/decide?request_description=NeedLaptop&context={context_str}&group_id=g1")
        req_id = resp.json()["request_id"]

        # Submit rejection
        resp = await client.post(f"/v1/decide/{req_id}/approve", json={"approved": False, "approver": "Bob"})
        assert resp.status_code == 200

        # Atomic log should have two entries for this request_id
        resp = await client.get("/v1/logs/atomic")
        entries = [e for e in resp.json() if e["request_id"] == req_id]
        assert len(entries) == 2
        assert entries[0]["decision"] == "APPROVAL_REQUIRED"
        assert entries[1]["decision"] == "REJECTED"
        assert entries[1]["request_description"] == "NeedLaptop"


@pytest.mark.asyncio
async def test_approval_preserves_identity_in_atomic_entry(mock_rule_engine):
    """Atomic log entry from approval preserves identity fields from the original request."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "id": "g1",
        "name": "Grp",
        "rules": [
            {"id": "r1", "rule_logic": "IF amount > 100 THEN ASK_FOR_APPROVAL"}
        ]
    }
    mock_rule_engine.return_value = mock_response

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/v1/decide",
            json={
                "request_description": "NeedLaptop",
                "context": {"amount": 150},
                "group_id": "g1",
                "agent_id": "agt_01",
                "credential_id": "cred_a",
                "user_id": "user_1",
            },
        )
        req_id = resp.json()["request_id"]

        await client.post(f"/v1/decide/{req_id}/approve", json={"approved": True, "approver": "Alice"})

        resp = await client.get("/v1/logs/atomic")
        entries = [e for e in resp.json() if e["request_id"] == req_id]
        final = entries[-1]
        assert final["decision"] == "APPROVED"
        assert final["agent_id"] == "agt_01"
        assert final["credential_id"] == "cred_a"
        assert final["user_id"] == "user_1"


@pytest.mark.asyncio
async def test_post_evaluate_records_identity_fields_in_logs_and_pending(mock_rule_engine):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "id": "g1",
        "name": "Grp",
        "rules": [
            {"id": "r1", "rule_logic": "IF amount > 100 THEN ASK_FOR_APPROVAL"}
        ]
    }
    mock_rule_engine.return_value = mock_response

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/v1/decide",
            json={
                "request_description": "NeedLaptop",
                "context": {"amount": 150},
                "group_id": "g1",
                "agent_id": "agt_ops_01",
                "credential_id": "cred_finance_a",
                "user_id": "user_4821",
                "scope": "finance:execute",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["outcome"] == "ASK_FOR_APPROVAL"
        assert data["agent_id"] == "agt_ops_01"
        assert data["credential_id"] == "cred_finance_a"
        assert data["user_id"] == "user_4821"
        req_id = data["request_id"]

        pending_resp = await client.get("/v1/pending")
        assert pending_resp.status_code == 200
        pending = next(p for p in pending_resp.json() if p["request_id"] == req_id)
        assert pending["agent_id"] == "agt_ops_01"
        assert pending["credential_id"] == "cred_finance_a"
        assert pending["user_id"] == "user_4821"
        assert pending["effective_group_id"] == "g1"

        atomic_resp = await client.get("/v1/logs/atomic")
        assert atomic_resp.status_code == 200
        atomic = next(a for a in atomic_resp.json() if a["request_id"] == req_id)
        assert atomic["agent_id"] == "agt_ops_01"
        assert atomic["credential_id"] == "cred_finance_a"
        assert atomic["user_id"] == "user_4821"
        assert atomic["effective_group_id"] == "g1"

        chain_resp = await client.get(f"/v1/logs/chains/{req_id}")
        assert chain_resp.status_code == 200
        chain = chain_resp.json()
        request_event = next(e for e in chain["events"] if e["event_type"] == "REQUEST")
        assert request_event["details"]["agent_id"] == "agt_ops_01"
        assert request_event["details"]["credential_id"] == "cred_finance_a"
        assert request_event["details"]["user_id"] == "user_4821"
        assert request_event["details"]["effective_group_id"] == "g1"

@pytest.mark.asyncio
async def test_evaluate_with_edge_cases(mock_rule_engine):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "id": "g1",
        "name": "Grp",
        "rules": [
            {
                "id": "r1",
                "rule_logic": "IF amount > 100 THEN ASK_FOR_APPROVAL",
                "edge_cases": ["IF currency == GBP THEN REJECT"]
            }
        ]
    }
    mock_rule_engine.return_value = mock_response

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # 1. Triggers edge case
        context_str = '{"amount": 150, "currency": "GBP"}'
        resp = await client.get(f"/v1/decide?request_description=Test&context={context_str}&group_id=g1")
        assert resp.status_code == 200
        assert resp.json()["outcome"] == "REJECT"

        # 2. Passes edge case, triggers rule logic
        context_str = '{"amount": 150, "currency": "EUR"}'
        resp = await client.get(f"/v1/decide?request_description=Test&context={context_str}&group_id=g1")
        assert resp.status_code == 200
        assert resp.json()["outcome"] == "ASK_FOR_APPROVAL"

@pytest.mark.asyncio
async def test_evaluate_user_report(mock_rule_engine):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "id": "g1",
        "name": "Grp",
        "rules": [
            {
                "id": "r1",
                "rule_logic": "IF contract_partner_name = 'Amazon' THEN ASK_FOR_APPROVAL",
                "edge_cases": []
            }
        ]
    }
    mock_rule_engine.return_value = mock_response

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # EXACT PAYLOAD LOGGED BY THE USER:
        # /v1/decide?request_description=Purchase%20of%20100%20paper%20clips%20at%20Amazon&context=%7B%22contract_partner_name%22%3A%20%22Amazon%22%7D&group_id=db0d2fd1-d716-4007-b2fe-389887ba565b
        import urllib.parse
        context_str = urllib.parse.quote('{"contract_partner_name": "Amazon"}')
        request_desc = urllib.parse.quote("Purchase of 100 paper clips at Amazon")
        group_id = "db0d2fd1-d716-4007-b2fe-389887ba565b"
        
        resp = await client.get(f"/v1/decide?request_description={request_desc}&context={context_str}&group_id={group_id}")
        assert resp.status_code == 200
        assert resp.json()["outcome"] == "ASK_FOR_APPROVAL"

@pytest.mark.asyncio
async def test_evaluate_with_json_logic(mock_rule_engine):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "id": "g1",
        "name": "Grp",
        "rules": [
            {
                "id": "r1",
                "rule_logic": "IF amount > 500 THEN ASK_FOR_APPROVAL",
                "rule_logic_json": {"if": [{">": [{"var": "amount"}, 500]}, "ASK_FOR_APPROVAL", None]},
                "edge_cases": ["IF currency != USD THEN REJECT"],
                "edge_cases_json": [{"if": [{"!=": [{"var": "currency"}, "USD"]}, "REJECT", None]}]
            }
        ]
    }
    mock_rule_engine.return_value = mock_response

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # 1. Triggers edge case
        context_str = '{"amount": 600, "currency": "EUR"}'
        resp = await client.get(f"/v1/decide?request_description=Test&context={context_str}&group_id=g1")
        assert resp.status_code == 200
        assert resp.json()["outcome"] == "REJECT"

        # 2. Passes edge case, triggers rule logic
        context_str = '{"amount": 600, "currency": "USD"}'
        resp = await client.get(f"/v1/decide?request_description=Test&context={context_str}&group_id=g1")
        assert resp.status_code == 200
        assert resp.json()["outcome"] == "ASK_FOR_APPROVAL"

        # 3. Passes edge case, does NOT trigger rule logic -> defaults to APPROVE
        context_str = '{"amount": 400, "currency": "USD"}'
        resp = await client.get(f"/v1/decide?request_description=Test&context={context_str}&group_id=g1")
        assert resp.status_code == 200
        assert resp.json()["outcome"] == "APPROVE"


@pytest.mark.asyncio
async def test_inactive_rules_are_not_evaluated(mock_rule_engine):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "id": "g1",
        "name": "Grp",
        "rules": [
            {
                "id": "inactive-rule",
                "name": "Archived Restriction",
                "active": False,
                "rule_logic": "IF amount > 100 THEN REJECT",
                "rule_logic_json": {"if": [{">": [{"var": "amount"}, 100]}, "REJECT", None]},
                "edge_cases": [],
                "edge_cases_json": []
            },
            {
                "id": "active-rule",
                "name": "Current Restriction",
                "active": True,
                "rule_logic": "IF amount > 500 THEN ASK_FOR_APPROVAL",
                "rule_logic_json": {"if": [{">": [{"var": "amount"}, 500]}, "ASK_FOR_APPROVAL", None]},
                "edge_cases": [],
                "edge_cases_json": []
            }
        ]
    }
    mock_rule_engine.return_value = mock_response

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        context_str = '{"amount": 150}'
        resp = await client.get(f"/v1/decide?request_description=Test&context={context_str}&group_id=g1")
        assert resp.status_code == 200
        data = resp.json()
        assert data["outcome"] == "APPROVE"
        assert data["matched_rules"] == []


@pytest.mark.asyncio
async def test_evaluate_can_scope_to_a_selected_rule(mock_rule_engine):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "id": "g1",
        "name": "Grp",
        "rules": [
            {
                "id": "rule-a",
                "name": "Other Active Rule",
                "active": True,
                "rule_logic": "IF amount > 50 THEN REJECT",
                "rule_logic_json": {"if": [{">": [{"var": "amount"}, 50]}, "REJECT", None]},
                "edge_cases": [],
                "edge_cases_json": []
            },
            {
                "id": "rule-b",
                "name": "Selected Rule",
                "active": True,
                "rule_logic": "IF amount > 500 THEN ASK_FOR_APPROVAL",
                "rule_logic_json": {"if": [{">": [{"var": "amount"}, 500]}, "ASK_FOR_APPROVAL", None]},
                "edge_cases": [],
                "edge_cases_json": []
            }
        ]
    }
    mock_rule_engine.return_value = mock_response

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        context_str = '{"amount": 100}'
        resp = await client.get(
            f"/v1/decide?request_description=Test&context={context_str}&group_id=g1&rule_id=rule-b"
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["outcome"] == "APPROVE"
        assert data["matched_rules"] == []


@pytest.mark.asyncio
@patch("openai.OpenAI")
async def test_translate_api_backfills_datapoints_when_provider_omits_them(mock_openai):
    mock_client = MagicMock()
    mock_openai.return_value = mock_client

    mock_message = MagicMock()
    mock_message.content = (
        '{"datapoints":[],"edge_cases":["IF currency != \\"EUR\\" THEN REJECT"],'
        '"edge_cases_json":[{"if":[{"!=":[{"var":"currency"},"EUR"]},"REJECT",null]}],'
        '"rule_logic":"IF withdrawal_amount > 1000 THEN ASK_FOR_APPROVAL",'
        '"rule_logic_json":{"if":[{">":[{"var":"withdrawal_amount"},1000]},"ASK_FOR_APPROVAL",null]}}'
    )

    mock_choice = MagicMock()
    mock_choice.message = mock_message

    mock_response = MagicMock()
    mock_response.choices = [mock_choice]
    mock_client.chat.completions.create.return_value = mock_response

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/v1/llm/translate",
            json={
                "natural_language": "ask for approval if withdrawal_amount is > 1000 unless currency is EUR",
                "feature": "finance",
                "name": "Withdrawal Rule",
                "provider": "openai",
                "model": "gpt-5.2",
                "api_key": "fake_key",
            },
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["datapoints"] == ["withdrawal_amount", "currency"]
    assert data["rule_logic_json"]["if"][0][">"][0]["var"] == "withdrawal_amount"
    assert data["edge_cases_json"][0]["if"][0]["!="][0]["var"] == "currency"


# ── Schema listing, generation & saving endpoints ──

@pytest.mark.asyncio
async def test_list_schemas_api(tmp_path):
    """GET /v1/schemas returns schemas from the schemas directory."""
    # Write a test schema file
    schema_data = {
        "name": "Test Domain",
        "description": "A test domain",
        "schema": {"amount": "number (order total)"},
    }
    (tmp_path / "test_domain.json").write_text(json.dumps(schema_data))

    with patch("decision_center.app.list_schemas", return_value=[{
        "key": "test_domain",
        "name": "Test Domain",
        "description": "A test domain",
        "schema": {"amount": "number (order total)"},
    }]):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/v1/schemas")
            assert resp.status_code == 200
            data = resp.json()
            assert len(data) == 1
            assert data[0]["key"] == "test_domain"
            assert data[0]["name"] == "Test Domain"
            assert "amount" in data[0]["schema"]

@pytest.mark.asyncio
@patch("decision_center.schema_generator.openai")
async def test_generate_schema_api(mock_openai_mod):
    mock_client = MagicMock()
    mock_openai_mod.OpenAI.return_value = mock_client

    mock_message = MagicMock()
    mock_message.content = json.dumps({
        "name": "ecommerce",
        "description": "E-commerce domain schema",
        "fields": [
            {"name": "order_amount", "type": "number", "description": "Total order value"},
            {"name": "customer_email", "type": "string", "description": "Customer email"},
        ],
        "message": "Proposed 2 fields for e-commerce.",
    })
    mock_choice = MagicMock()
    mock_choice.message = mock_message
    mock_response = MagicMock()
    mock_response.choices = [mock_choice]
    mock_client.chat.completions.create.return_value = mock_response

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/v1/llm/schema",
            json={
                "provider": "openai",
                "model": "gpt-4o",
                "api_key": "fake_key",
                "user_message": "Create an e-commerce schema",
                "conversation_history": [],
                "current_schema": None,
            },
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "ecommerce"
    assert len(data["fields"]) == 2
    assert data["fields"][0]["name"] == "order_amount"
    assert data["message"] == "Proposed 2 fields for e-commerce."


@pytest.mark.asyncio
async def test_save_schema_api(tmp_path):
    from decision_center.schema_generator import SchemaProposal

    original_save = __import__("decision_center.schema_generator", fromlist=["save_schema"]).save_schema

    def _save_with_tmp(proposal, overwrite=False, **kwargs):
        return original_save(proposal, schemas_dir=str(tmp_path), overwrite=overwrite)

    with patch("decision_center.app.save_schema", side_effect=_save_with_tmp):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post(
                "/v1/schemas/save",
                json={
                    "name": "Test Schema",
                    "description": "A test schema",
                    "fields": [
                        {"name": "amount", "type": "number", "description": "Amount"},
                    ],
                },
            )

    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "Test Schema"
    assert "test_schema.json" in data["path"]

    # Verify file was written
    saved = json.loads((tmp_path / "test_schema.json").read_text())
    assert saved["name"] == "Test Schema"
    assert "amount" in saved["schema"]


@pytest.mark.asyncio
async def test_save_schema_api_conflict(tmp_path):
    from decision_center.schema_generator import save_schema as original_save

    def _save_with_tmp(proposal, overwrite=False, **kwargs):
        return original_save(proposal, schemas_dir=str(tmp_path), overwrite=overwrite)

    with patch("decision_center.app.save_schema", side_effect=_save_with_tmp):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            # First save succeeds
            payload = {
                "name": "Conflict Test",
                "description": "A schema",
                "fields": [{"name": "x", "type": "number", "description": "X"}],
            }
            resp = await client.post("/v1/schemas/save", json=payload)
            assert resp.status_code == 200

            # Second save without overwrite returns 409
            resp = await client.post("/v1/schemas/save", json=payload)
            assert resp.status_code == 409

            # With overwrite=true it succeeds
            payload["overwrite"] = True
            resp = await client.post("/v1/schemas/save", json=payload)
            assert resp.status_code == 200


# ── Admin API key auth tests for /v1/schemas/save ──

_SAVE_PAYLOAD = {
    "name": "Auth Test",
    "description": "A schema",
    "fields": [{"name": "x", "type": "number", "description": "X"}],
}


@pytest.mark.asyncio
async def test_save_schema_no_auth_required(tmp_path):
    """Schema save endpoint requires no authentication."""
    from decision_center.schema_generator import save_schema as original_save

    def _save_with_tmp(proposal, overwrite=False, **kwargs):
        return original_save(proposal, schemas_dir=str(tmp_path), overwrite=overwrite)

    with patch("decision_center.app.save_schema", side_effect=_save_with_tmp):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post("/v1/schemas/save", json=_SAVE_PAYLOAD)
            assert resp.status_code == 200


@pytest.mark.asyncio
async def test_export_logs_returns_full_store_as_attachment(mock_rule_engine, monkeypatch):
    """GET /v1/logs/export returns the full in-memory store as a downloadable JSON attachment."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "id": "g1",
        "name": "Grp",
        "rules": [
            {"id": "r1", "rule_logic": "IF amount > 100 THEN ASK_FOR_APPROVAL"}
        ],
    }
    mock_rule_engine.return_value = mock_response

    # Use a fresh empty store so assertions are deterministic.
    original_store = app_module.store
    monkeypatch.setattr(app_module, "store", DecisionStore())

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            decide_resp = await client.post(
                "/v1/decide",
                json={
                    "request_description": "NeedLaptop",
                    "context": {"amount": 150},
                    "group_id": "g1",
                },
            )
            assert decide_resp.status_code == 200
            req_id = decide_resp.json()["request_id"]

            export_resp = await client.get("/v1/logs/export")
            assert export_resp.status_code == 200

            disposition = export_resp.headers.get("content-disposition", "")
            assert "attachment" in disposition
            assert "decision_log_" in disposition
            assert disposition.endswith('.json"')

            payload = export_resp.json()
            assert set(payload.keys()) == {"atomic_logs", "chains", "pending"}

            atomic_request_ids = [entry["request_id"] for entry in payload["atomic_logs"]]
            assert req_id in atomic_request_ids
            assert req_id in payload["chains"]
            assert req_id in payload["pending"]
    finally:
        monkeypatch.setattr(app_module, "store", original_store)
