from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import json
from pathlib import Path
import secrets
from typing import Any

from pydantic import BaseModel, Field

from shared.persistence import atomic_write_json


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _generate_id(prefix: str) -> str:
    return f"{prefix}_{secrets.token_urlsafe(8)}"


def _hash_secret(secret: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", secret.encode("utf-8"), salt, 200_000)
    return f"{salt.hex()}:{digest.hex()}"


def _verify_secret(secret: str, encoded_hash: str) -> bool:
    try:
        salt_hex, digest_hex = encoded_hash.split(":", 1)
    except ValueError:
        return False
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        secret.encode("utf-8"),
        bytes.fromhex(salt_hex),
        200_000,
    )
    return hmac.compare_digest(digest.hex(), digest_hex)


class AgentRecord(BaseModel):
    agent_id: str = Field(default_factory=lambda: _generate_id("agt"))
    name: str
    description: str = ""
    status: str = "active"
    created_at: datetime = Field(default_factory=_utcnow)
    metadata: dict[str, Any] = Field(default_factory=dict)


class CredentialRecord(BaseModel):
    credential_id: str = Field(default_factory=lambda: _generate_id("cred"))
    agent_id: str
    name: str
    client_id: str
    client_secret_hash: str
    scopes: list[str]
    default_group_id: str | None = None
    allowed_group_ids: list[str] = Field(default_factory=list)
    status: str = "active"
    created_at: datetime = Field(default_factory=_utcnow)
    revoked_at: datetime | None = None


class EnrollmentTokenRecord(BaseModel):
    enrollment_token_id: str = Field(default_factory=lambda: _generate_id("enroll"))
    agent_id: str
    credential_name: str
    token_hash: str
    scopes: list[str]
    default_group_id: str | None = None
    allowed_group_ids: list[str] = Field(default_factory=list)
    expires_at: datetime
    used_at: datetime | None = None
    status: str = "active"


class AuthStoreData(BaseModel):
    agents: dict[str, AgentRecord] = Field(default_factory=dict)
    credentials: dict[str, CredentialRecord] = Field(default_factory=dict)
    enrollment_tokens: dict[str, EnrollmentTokenRecord] = Field(default_factory=dict)


class CredentialBootstrap(BaseModel):
    agent_id: str
    credential_id: str
    client_id: str
    client_secret: str
    scopes: list[str]
    default_group_id: str | None = None
    allowed_group_ids: list[str] = Field(default_factory=list)


class AccessTokenRecord(BaseModel):
    token: str
    credential_id: str
    agent_id: str
    scopes: list[str]
    expires_at: datetime


class AccessTokenIssue(BaseModel):
    access_token: str
    token_type: str = "Bearer"
    expires_in: int
    scope: str


class AuthenticatedPrincipal(BaseModel):
    agent_id: str
    credential_id: str
    scopes: list[str]
    default_group_id: str | None = None
    allowed_group_ids: list[str] = Field(default_factory=list)


class AuthStore:
    def __init__(
        self,
        data: AuthStoreData | None = None,
        persistence_path: str | Path | None = None,
    ):
        self.data = data or AuthStoreData()
        self.persistence_path = Path(persistence_path) if persistence_path else None
        if data is None:
            self._load()

    def _load(self) -> None:
        if self.persistence_path is None or not self.persistence_path.exists():
            return
        try:
            payload = json.loads(self.persistence_path.read_text())
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"Failed to parse auth store at {self.persistence_path}: {exc}") from exc

        try:
            self.data = AuthStoreData.model_validate(payload)
        except Exception as exc:
            raise RuntimeError(f"Failed to validate auth store at {self.persistence_path}: {exc}") from exc

    def save(self):
        if self.persistence_path is None:
            return None
        atomic_write_json(self.persistence_path, self.data.model_dump(mode="json"))
        return None


class AuthService:
    def __init__(self, store: AuthStore, token_ttl_seconds: int = 900):
        self.store = store
        self.token_ttl_seconds = token_ttl_seconds
        self._access_tokens: dict[str, AccessTokenRecord] = {}

    def create_agent(self, name: str, description: str = "", metadata: dict[str, Any] | None = None) -> AgentRecord:
        agent = AgentRecord(name=name, description=description, metadata=metadata or {})
        self.store.data.agents[agent.agent_id] = agent
        self.store.save()
        return agent

    def list_agents(self) -> list[AgentRecord]:
        return list(self.store.data.agents.values())

    def list_credentials(self) -> list[CredentialRecord]:
        return list(self.store.data.credentials.values())

    def create_enrollment_token(
        self,
        agent_id: str,
        credential_name: str,
        scopes: list[str],
        default_group_id: str | None = None,
        allowed_group_ids: list[str] | None = None,
        ttl_seconds: int = 3600,
    ) -> dict[str, Any]:
        agent = self.store.data.agents.get(agent_id)
        if not agent or agent.status != "active":
            raise ValueError("agent not found or inactive")

        allowed_groups = list(allowed_group_ids or [])
        if default_group_id and default_group_id not in allowed_groups:
            allowed_groups.append(default_group_id)

        raw_token = _generate_id("enroll")
        record = EnrollmentTokenRecord(
            agent_id=agent_id,
            credential_name=credential_name,
            token_hash=_hash_secret(raw_token),
            scopes=list(scopes),
            default_group_id=default_group_id,
            allowed_group_ids=allowed_groups,
            expires_at=_utcnow() + timedelta(seconds=ttl_seconds),
        )
        self.store.data.enrollment_tokens[record.enrollment_token_id] = record
        self.store.save()
        return {
            "enrollment_token": raw_token,
            "enrollment_token_id": record.enrollment_token_id,
            "agent_id": agent_id,
            "credential_name": credential_name,
            "scopes": record.scopes,
            "default_group_id": record.default_group_id,
            "allowed_group_ids": record.allowed_group_ids,
            "expires_at": record.expires_at,
        }

    def exchange_enrollment_token(self, enrollment_token: str) -> CredentialBootstrap:
        now = _utcnow()
        for record in self.store.data.enrollment_tokens.values():
            if record.status != "active" or record.used_at is not None or record.expires_at <= now:
                continue
            if not _verify_secret(enrollment_token, record.token_hash):
                continue

            record.status = "used"
            record.used_at = now

            client_id = _generate_id("uo_client")
            client_secret = _generate_id("uo_secret")
            credential = CredentialRecord(
                agent_id=record.agent_id,
                name=record.credential_name,
                client_id=client_id,
                client_secret_hash=_hash_secret(client_secret),
                scopes=list(record.scopes),
                default_group_id=record.default_group_id,
                allowed_group_ids=list(record.allowed_group_ids),
            )
            self.store.data.credentials[credential.credential_id] = credential
            self.store.save()
            return CredentialBootstrap(
                agent_id=credential.agent_id,
                credential_id=credential.credential_id,
                client_id=client_id,
                client_secret=client_secret,
                scopes=credential.scopes,
                default_group_id=credential.default_group_id,
                allowed_group_ids=credential.allowed_group_ids,
            )

        raise ValueError("Enrollment token is invalid or expired")

    def issue_access_token(
        self,
        client_id: str,
        client_secret: str,
        requested_scope: str | None = None,
    ) -> AccessTokenIssue:
        credential = next(
            (c for c in self.store.data.credentials.values() if c.client_id == client_id),
            None,
        )
        if not credential or credential.status != "active":
            raise ValueError("Invalid client credentials")
        if not _verify_secret(client_secret, credential.client_secret_hash):
            raise ValueError("Invalid client credentials")

        requested_scopes = requested_scope.split() if requested_scope else list(credential.scopes)
        if not set(requested_scopes).issubset(set(credential.scopes)):
            raise ValueError("Requested scope is not allowed")

        token = _generate_id("uo_at")
        expires_in = self.token_ttl_seconds
        self._access_tokens[token] = AccessTokenRecord(
            token=token,
            credential_id=credential.credential_id,
            agent_id=credential.agent_id,
            scopes=requested_scopes,
            expires_at=_utcnow() + timedelta(seconds=expires_in),
        )
        return AccessTokenIssue(
            access_token=token,
            expires_in=expires_in,
            scope=" ".join(requested_scopes),
        )

    def authenticate_bearer(self, token: str) -> AuthenticatedPrincipal | None:
        record = self._access_tokens.get(token)
        if not record:
            return None
        if record.expires_at <= _utcnow():
            del self._access_tokens[token]
            return None

        credential = self.store.data.credentials.get(record.credential_id)
        agent = self.store.data.agents.get(record.agent_id)
        if not credential or credential.status != "active" or not agent or agent.status != "active":
            return None

        return AuthenticatedPrincipal(
            agent_id=record.agent_id,
            credential_id=record.credential_id,
            scopes=list(record.scopes),
            default_group_id=credential.default_group_id,
            allowed_group_ids=list(credential.allowed_group_ids),
        )

    def revoke_credential(self, credential_id: str) -> CredentialRecord:
        credential = self.store.data.credentials.get(credential_id)
        if not credential:
            raise ValueError("credential not found")
        credential.status = "revoked"
        credential.revoked_at = _utcnow()
        self.store.save()
        return credential

    def revoke_agent(self, agent_id: str) -> AgentRecord:
        agent = self.store.data.agents.get(agent_id)
        if not agent:
            raise ValueError("agent not found")
        agent.status = "revoked"
        for credential in self.store.data.credentials.values():
            if credential.agent_id == agent_id and credential.status == "active":
                credential.status = "revoked"
                credential.revoked_at = _utcnow()
        self.store.save()
        return agent


_CURRENT_PRINCIPAL: ContextVar[AuthenticatedPrincipal | None] = ContextVar(
    "unreal_objects_current_principal",
    default=None,
)


def get_current_principal() -> AuthenticatedPrincipal | None:
    return _CURRENT_PRINCIPAL.get()


@contextmanager
def principal_context(principal: AuthenticatedPrincipal):
    token = _CURRENT_PRINCIPAL.set(principal)
    try:
        yield
    finally:
        _CURRENT_PRINCIPAL.reset(token)
