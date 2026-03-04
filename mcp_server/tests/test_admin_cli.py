from unittest.mock import MagicMock

import pytest

from mcp_server import admin_cli


class _FakeClient:
    def __init__(self):
        self.calls = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def post(self, url, headers=None, json=None):
        self.calls.append(("POST", url, headers, json))
        response = MagicMock()
        response.raise_for_status = MagicMock()
        if url.endswith("/v1/admin/agents"):
            response.json.return_value = {"agent_id": "agt_ops_01", "name": json["name"]}
        elif url.endswith("/enrollment-tokens"):
            response.json.return_value = {"enrollment_token": "enroll_123", "agent_id": "agt_ops_01"}
        else:
            response.json.return_value = {"credential_id": "cred_finance_a", "status": "revoked"}
        return response

    def get(self, url):
        self.calls.append(("GET", url, None, None))
        response = MagicMock()
        response.raise_for_status = MagicMock()
        response.json.return_value = [
            {"id": "grp_finance", "name": "Finance"},
            {"id": "grp_support", "name": "Support"},
        ]
        return response


@pytest.fixture
def fake_client(monkeypatch):
    client = _FakeClient()
    monkeypatch.setattr(admin_cli.httpx, "Client", lambda: client)
    return client


def test_create_agent_command_posts_expected_payload(fake_client, capsys):
    admin_cli.main([
        "--base-url", "http://127.0.0.1:8000",
        "--admin-api-key", "admin-secret",
        "create-agent",
        "--name", "Ops Agent",
        "--description", "Shared runtime",
    ])

    method, url, headers, payload = fake_client.calls[0]
    assert method == "POST"
    assert url == "http://127.0.0.1:8000/v1/admin/agents"
    assert headers["X-Admin-Key"] == "admin-secret"
    assert payload == {"name": "Ops Agent", "description": "Shared runtime"}
    assert "agt_ops_01" in capsys.readouterr().out


def test_issue_enrollment_token_command_posts_expected_payload(fake_client, capsys):
    admin_cli.main([
        "--base-url", "http://127.0.0.1:8000",
        "--admin-api-key", "admin-secret",
        "issue-enrollment-token",
        "agt_ops_01",
        "--credential-name", "finance",
        "--default-group-id", "grp_finance",
        "--allowed-group-id", "grp_finance",
    ])

    method, url, headers, payload = fake_client.calls[0]
    assert method == "POST"
    assert url == "http://127.0.0.1:8000/v1/admin/agents/agt_ops_01/enrollment-tokens"
    assert payload["credential_name"] == "finance"
    assert payload["scopes"] == []
    assert payload["default_group_id"] == "grp_finance"
    assert payload["allowed_group_ids"] == ["grp_finance"]
    assert "enroll_123" in capsys.readouterr().out


def test_issue_enrollment_token_can_interactively_select_groups(fake_client, monkeypatch, capsys):
    answers = iter(["1", "1,2"])
    monkeypatch.setattr("builtins.input", lambda _: next(answers))

    admin_cli.main([
        "--base-url", "http://127.0.0.1:8000",
        "--rule-engine-url", "http://127.0.0.1:8001",
        "--admin-api-key", "admin-secret",
        "issue-enrollment-token",
        "agt_ops_01",
        "--credential-name", "finance",
    ])

    get_method, get_url, _, _ = fake_client.calls[0]
    assert get_method == "GET"
    assert get_url == "http://127.0.0.1:8001/v1/groups"

    _, post_url, _, payload = fake_client.calls[1]
    assert post_url == "http://127.0.0.1:8000/v1/admin/agents/agt_ops_01/enrollment-tokens"
    assert payload["default_group_id"] == "grp_finance"
    assert payload["allowed_group_ids"] == ["grp_finance", "grp_support"]
    assert payload["scopes"] == []
    assert "enroll_123" in capsys.readouterr().out


def test_revoke_credential_command_posts_expected_payload(fake_client, capsys):
    admin_cli.main([
        "--base-url", "http://127.0.0.1:8000",
        "--admin-api-key", "admin-secret",
        "revoke-credential",
        "cred_finance_a",
    ])

    method, url, headers, payload = fake_client.calls[0]
    assert method == "POST"
    assert url == "http://127.0.0.1:8000/v1/admin/credentials/cred_finance_a/revoke"
    assert payload is None
    assert headers["X-Admin-Key"] == "admin-secret"
    assert "revoked" in capsys.readouterr().out
