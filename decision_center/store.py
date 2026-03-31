from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from .models import AtomicLogEntry, ChainEvent, DecisionChain
from shared.persistence import atomic_write_json


class DecisionStoreData(BaseModel):
    atomic_logs: list[AtomicLogEntry] = Field(default_factory=list)
    chains: dict[str, DecisionChain] = Field(default_factory=dict)
    pending: dict[str, dict[str, Any]] = Field(default_factory=dict)


class DecisionStore:
    def __init__(
        self,
        data: DecisionStoreData | None = None,
        persistence_path: str | Path | None = None,
    ):
        self.data = data or DecisionStoreData()
        self.persistence_path = Path(persistence_path) if persistence_path else None
        if data is None:
            self._load()

    def _load(self) -> None:
        if self.persistence_path is None or not self.persistence_path.exists():
            return
        try:
            payload = json.loads(self.persistence_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"Failed to parse decision store at {self.persistence_path}: {exc}") from exc

        try:
            self.data = DecisionStoreData.model_validate(payload)
        except Exception as exc:
            raise RuntimeError(f"Failed to validate decision store at {self.persistence_path}: {exc}") from exc

    def _save(self) -> None:
        if self.persistence_path is None:
            return
        atomic_write_json(self.persistence_path, self.data.model_dump(mode="json"))

    def log_atomic(self, entry: AtomicLogEntry):
        self.data.atomic_logs.append(entry)
        self._save()

    def get_atomic_logs(self) -> list[AtomicLogEntry]:
        return self.data.atomic_logs

    def log_chain_event(self, request_id: str, event_type: str, details: dict | None = None):
        if request_id not in self.data.chains:
            self.data.chains[request_id] = DecisionChain(request_id=request_id)

        self.data.chains[request_id].events.append(
            ChainEvent(event_type=event_type, details=details or {})
        )
        self._save()

    def get_chain(self, request_id: str) -> DecisionChain | None:
        return self.data.chains.get(request_id)

    def get_all_chains(self) -> list[DecisionChain]:
        return list(self.data.chains.values())

    def add_pending(self, request_id: str, context: dict):
        self.data.pending[request_id] = context
        self._save()

    def is_pending(self, request_id: str) -> bool:
        return request_id in self.data.pending

    def resolve_pending(self, request_id: str):
        resolved = self.data.pending.pop(request_id, None)
        if resolved is not None:
            self._save()
        return resolved

    def get_pending(self) -> list[dict]:
        return [{"request_id": k, **v} for k, v in self.data.pending.items()]
