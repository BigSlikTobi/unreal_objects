from typing import List
from .models import AtomicLogEntry, DecisionChain, ChainEvent

class DecisionStore:
    def __init__(self):
        self.atomic_logs: List[AtomicLogEntry] = []
        self.chains: dict[str, DecisionChain] = {}
        # Simple pending queue mapping request_id -> group_id context if needed
        self.pending: dict[str, dict] = {}

    def log_atomic(self, entry: AtomicLogEntry):
        self.atomic_logs.append(entry)

    def get_atomic_logs(self) -> List[AtomicLogEntry]:
        return self.atomic_logs

    def log_chain_event(self, request_id: str, event_type: str, details: dict = None):
        if request_id not in self.chains:
            self.chains[request_id] = DecisionChain(request_id=request_id)
        
        self.chains[request_id].events.append(
            ChainEvent(event_type=event_type, details=details or {})
        )

    def get_chain(self, request_id: str) -> DecisionChain | None:
        return self.chains.get(request_id)

    def get_all_chains(self) -> List[DecisionChain]:
        return list(self.chains.values())

    def add_pending(self, request_id: str, context: dict):
        self.pending[request_id] = context

    def is_pending(self, request_id: str) -> bool:
        return request_id in self.pending

    def resolve_pending(self, request_id: str):
        return self.pending.pop(request_id, None)

    def get_pending(self) -> List[dict]:
        return [{"request_id": k, **v} for k, v in self.pending.items()]
