from decision_center.models import AtomicLogEntry, DecisionState
from decision_center.store import DecisionStore


def test_decision_store_restores_logs_chains_and_pending(tmp_path):
    path = tmp_path / "decision_center_store.json"
    store = DecisionStore(persistence_path=path)

    store.log_atomic(
        AtomicLogEntry(
            request_id="req-1",
            request_description="NeedLaptop",
            context={"amount": 150},
            decision=DecisionState.APPROVAL_REQUIRED,
            agent_id="agt_01",
            credential_id="cred_a",
            user_id="user_1",
            effective_group_id="g1",
        )
    )
    store.log_chain_event("req-1", "REQUEST", details={"description": "NeedLaptop"})
    store.add_pending(
        "req-1",
        {
            "description": "NeedLaptop",
            "context": {"amount": 150},
            "agent_id": "agt_01",
            "credential_id": "cred_a",
            "user_id": "user_1",
            "effective_group_id": "g1",
        },
    )

    restored = DecisionStore(persistence_path=path)

    assert restored.get_atomic_logs()[0].request_id == "req-1"
    assert restored.get_chain("req-1") is not None
    assert restored.get_chain("req-1").events[0].event_type == "REQUEST"
    assert restored.is_pending("req-1") is True
    assert restored.get_pending()[0]["effective_group_id"] == "g1"


def test_resolving_pending_persists_across_restart(tmp_path):
    path = tmp_path / "decision_center_store.json"
    store = DecisionStore(persistence_path=path)
    store.add_pending("req-1", {"description": "NeedLaptop"})

    resolved = store.resolve_pending("req-1")
    assert resolved == {"description": "NeedLaptop"}

    restored = DecisionStore(persistence_path=path)
    assert restored.is_pending("req-1") is False


def test_corrupted_decision_store_raises(tmp_path):
    path = tmp_path / "decision_center_store.json"
    path.write_text("{not-valid-json")

    try:
        DecisionStore(persistence_path=path)
    except RuntimeError as exc:
        assert "Failed to parse decision store" in str(exc)
    else:
        raise AssertionError("Expected RuntimeError for corrupted decision store")
