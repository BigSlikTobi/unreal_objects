from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
import pytest
import sys

from mcp_server.auth import AuthService, AuthStore, get_current_principal
from mcp_server import server as server_module
from mcp_server.server import build_http_app, mcp


@pytest.fixture
def auth_service(tmp_path):
    store = AuthStore()
    return AuthService(store=store, token_ttl_seconds=60)


def _dummy_base_app():
    app = FastAPI()

    @app.get("/protected")
    async def protected():
        principal = get_current_principal()
        return {
            "agent_id": principal.agent_id if principal else None,
            "credential_id": principal.credential_id if principal else None,
            "scopes": principal.scopes if principal else [],
        }

    return app


def test_exchange_enrollment_token_does_not_persist_across_fresh_store(auth_service):
    agent = auth_service.create_agent(name="Ops Agent")
    issued = auth_service.create_enrollment_token(
        agent_id=agent.agent_id,
        credential_name="finance",
        scopes=["finance:execute"],
        default_group_id="grp_finance",
        allowed_group_ids=["grp_finance"],
    )

    exchange = auth_service.exchange_enrollment_token(issued["enrollment_token"])

    fresh_store = AuthStore()
    assert agent.agent_id not in fresh_store.data.agents
    assert exchange.credential_id not in fresh_store.data.credentials


def test_enrollment_token_can_only_be_used_once(auth_service):
    agent = auth_service.create_agent(name="Ops Agent")
    issued = auth_service.create_enrollment_token(
        agent_id=agent.agent_id,
        credential_name="finance",
        scopes=["finance:execute"],
        default_group_id="grp_finance",
        allowed_group_ids=["grp_finance"],
    )

    auth_service.exchange_enrollment_token(issued["enrollment_token"])

    with pytest.raises(ValueError, match="invalid or expired"):
        auth_service.exchange_enrollment_token(issued["enrollment_token"])


def test_build_http_app_requires_auth_service_when_auth_is_enabled():
    with pytest.raises(ValueError, match="auth_service is required when auth is enabled"):
        build_http_app(
            base_app=_dummy_base_app(),
            auth_enabled=True,
            auth_service=None,
            admin_api_key="admin-secret",
        )


def test_main_requires_auth_enabled_when_admin_api_key_is_set(monkeypatch):
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "server.py",
            "--transport",
            "streamable-http",
            "--admin-api-key",
            "admin-secret",
        ],
    )

    with pytest.raises(SystemExit, match="--admin-api-key requires --auth-enabled"):
        server_module.main()


@pytest.mark.asyncio
async def test_http_app_requires_bearer_token_when_auth_enabled(auth_service):
    app = build_http_app(
        base_app=_dummy_base_app(),
        auth_enabled=True,
        auth_service=auth_service,
        admin_api_key="admin-secret",
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/protected")

    assert response.status_code == 401
    assert response.json()["detail"] == "Missing bearer token"


@pytest.mark.asyncio
async def test_http_app_does_not_expose_auth_routes_when_auth_is_disabled():
    app = build_http_app(
        base_app=_dummy_base_app(),
        auth_enabled=False,
        auth_service=None,
        admin_api_key="admin-secret",
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        admin_response = await client.post(
            "/v1/admin/agents",
            headers={"X-Admin-Key": "admin-secret"},
            json={"name": "Ops Agent"},
        )
        enroll_response = await client.post(
            "/v1/agents/enroll",
            json={"enrollment_token": "enroll_123"},
        )
        token_response = await client.post(
            "/oauth/token",
            json={
                "grant_type": "client_credentials",
                "client_id": "uo_client_finance_a",
                "client_secret": "uo_secret_once_only",
            },
        )
        instructions_response = await client.get("/instructions")

    assert admin_response.status_code == 404
    assert enroll_response.status_code == 404
    assert token_response.status_code == 404
    assert instructions_response.status_code == 404


@pytest.mark.asyncio
async def test_http_app_allows_authenticated_request_and_propagates_principal(auth_service):
    app = build_http_app(
        base_app=_dummy_base_app(),
        auth_enabled=True,
        auth_service=auth_service,
        admin_api_key="admin-secret",
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        agent_response = await client.post(
            "/v1/admin/agents",
            headers={"X-Admin-Key": "admin-secret"},
            json={"name": "Ops Agent", "description": "multi-domain"},
        )
        assert agent_response.status_code == 201
        agent_id = agent_response.json()["agent_id"]

        enrollment_response = await client.post(
            f"/v1/admin/agents/{agent_id}/enrollment-tokens",
            headers={"X-Admin-Key": "admin-secret"},
            json={
                "credential_name": "finance",
                "scopes": ["finance:execute"],
                "default_group_id": "grp_finance",
                "allowed_group_ids": ["grp_finance"],
            },
        )
        assert enrollment_response.status_code == 201
        enrollment_token = enrollment_response.json()["enrollment_token"]

        exchange_response = await client.post(
            "/v1/agents/enroll",
            json={"enrollment_token": enrollment_token},
        )
        assert exchange_response.status_code == 200
        client_id = exchange_response.json()["client_id"]
        client_secret = exchange_response.json()["client_secret"]

        token_response = await client.post(
            "/oauth/token",
            json={
                "grant_type": "client_credentials",
                "client_id": client_id,
                "client_secret": client_secret,
                "scope": "finance:execute",
            },
        )
        assert token_response.status_code == 200
        access_token = token_response.json()["access_token"]

        protected_response = await client.get(
            "/protected",
            headers={"Authorization": f"Bearer {access_token}"},
        )

    assert protected_response.status_code == 200
    assert protected_response.json() == {
        "agent_id": agent_id,
        "credential_id": exchange_response.json()["credential_id"],
        "scopes": ["finance:execute"],
    }


@pytest.mark.asyncio
async def test_bootstrap_instructions_are_public_and_use_relative_paths(auth_service):
    app = build_http_app(
        base_app=_dummy_base_app(),
        auth_enabled=True,
        auth_service=auth_service,
        admin_api_key="admin-secret",
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://192.168.178.21:8000") as client:
        response = await client.get("/instructions")

    assert response.status_code == 200
    assert response.json() == {
        "version": 1,
        "name": "Unreal Objects Bootstrap",
        "bootstrap_prompt": "If you have already enrolled before, do not enroll again. Reuse your stored client_id and client_secret and request a fresh access token. Otherwise, ask the user for the one-time enrollment token, then follow the steps below on this same host.",
        "same_host_as": "http://192.168.178.21:8000",
        "mcp_http_path": "/mcp",
        "enroll_path": "/v1/agents/enroll",
        "token_path": "/oauth/token",
        "mcp_headers": {
            "Accept": "application/json, text/event-stream",
        },
        "steps": [
            "POST your one-time enrollment token to /v1/agents/enroll as JSON.",
            "Store agent_id, credential_id, client_id, and client_secret from the response.",
            "POST client_credentials to /oauth/token.",
            "Use the returned access_token as Bearer auth for POST /mcp requests.",
            "Include Accept: application/json, text/event-stream on MCP HTTP requests.",
            "Report back when MCP access is working.",
        ],
        "notes": [
            "Use the same host you called for /instructions; the paths above are relative.",
            "If you have already enrolled before, do not enroll again. Reuse stored client credentials and request a fresh access token.",
            "Do not send the enrollment token as a Bearer token.",
            "The enrollment token can only be used once.",
        ],
    }


@pytest.mark.asyncio
async def test_streamable_http_mcp_initialize_works_after_auth(auth_service):
    app = build_http_app(
        base_app=mcp.streamable_http_app(),
        auth_enabled=True,
        auth_service=auth_service,
        admin_api_key="admin-secret",
    )

    async with app.router.lifespan_context(app):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://localhost:8000") as client:
            agent_response = await client.post(
                "/v1/admin/agents",
                headers={"X-Admin-Key": "admin-secret"},
                json={"name": "Ops Agent", "description": "multi-domain"},
            )
            assert agent_response.status_code == 201
            agent_id = agent_response.json()["agent_id"]

            enrollment_response = await client.post(
                f"/v1/admin/agents/{agent_id}/enrollment-tokens",
                headers={"X-Admin-Key": "admin-secret"},
                json={"credential_name": "finance"},
            )
            assert enrollment_response.status_code == 201
            enrollment_token = enrollment_response.json()["enrollment_token"]

            exchange_response = await client.post(
                "/v1/agents/enroll",
                json={"enrollment_token": enrollment_token},
            )
            assert exchange_response.status_code == 200
            client_id = exchange_response.json()["client_id"]
            client_secret = exchange_response.json()["client_secret"]

            token_response = await client.post(
                "/oauth/token",
                json={
                    "grant_type": "client_credentials",
                    "client_id": client_id,
                    "client_secret": client_secret,
                },
            )
            assert token_response.status_code == 200
            access_token = token_response.json()["access_token"]

            initialize_response = await client.post(
                "/mcp",
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Accept": "application/json, text/event-stream",
                },
                json={
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "initialize",
                    "params": {
                        "protocolVersion": "2025-11-05",
                        "capabilities": {},
                        "clientInfo": {"name": "test-client", "version": "1.0"},
                    },
                },
            )

    assert initialize_response.status_code == 200
    assert initialize_response.headers["content-type"].startswith("text/event-stream")
    assert '"jsonrpc":"2.0"' in initialize_response.text
    assert '"serverInfo":{"name":"Unreal Objects"' in initialize_response.text


@pytest.mark.asyncio
async def test_expired_access_token_is_rejected(auth_service, monkeypatch):
    """An access token past its TTL must be rejected with 401 and evicted from the store."""
    from datetime import timedelta
    import mcp_server.auth as auth_module

    app = build_http_app(
        base_app=_dummy_base_app(),
        auth_enabled=True,
        auth_service=auth_service,
        admin_api_key="admin-secret",
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Create agent + credential + access token while time is normal
        agent_resp = await client.post(
            "/v1/admin/agents",
            headers={"X-Admin-Key": "admin-secret"},
            json={"name": "Expiry Agent"},
        )
        assert agent_resp.status_code == 201
        agent_id = agent_resp.json()["agent_id"]

        enroll_resp = await client.post(
            f"/v1/admin/agents/{agent_id}/enrollment-tokens",
            headers={"X-Admin-Key": "admin-secret"},
            json={"credential_name": "cred"},
        )
        assert enroll_resp.status_code == 201

        exchange_resp = await client.post(
            "/v1/agents/enroll",
            json={"enrollment_token": enroll_resp.json()["enrollment_token"]},
        )
        assert exchange_resp.status_code == 200
        client_id = exchange_resp.json()["client_id"]
        client_secret = exchange_resp.json()["client_secret"]

        token_resp = await client.post(
            "/oauth/token",
            json={
                "grant_type": "client_credentials",
                "client_id": client_id,
                "client_secret": client_secret,
            },
        )
        assert token_resp.status_code == 200
        access_token = token_resp.json()["access_token"]

        # Verify it works while not expired
        ok_resp = await client.get(
            "/protected",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert ok_resp.status_code == 200

        # Wind the clock past the TTL so the token is expired
        original_utcnow = auth_module._utcnow
        monkeypatch.setattr(
            auth_module,
            "_utcnow",
            lambda: original_utcnow() + timedelta(seconds=auth_service.token_ttl_seconds + 1),
        )

        expired_resp = await client.get(
            "/protected",
            headers={"Authorization": f"Bearer {access_token}"},
        )

    assert expired_resp.status_code == 401
    # Token must be evicted — the store should no longer contain it
    assert access_token not in auth_service._access_tokens
