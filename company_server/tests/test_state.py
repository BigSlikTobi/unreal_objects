"""Tests for CompanyState: seeding, case lifecycle."""

from company_server.state import CompanyState
from support_company.models import CaseStatus, CaseType, SupportCase


def _make_case(**kwargs) -> SupportCase:
    defaults = {"case_type": CaseType.ACCOUNT_UPDATE, "requested_action": "test"}
    defaults.update(kwargs)
    return SupportCase(**defaults)


def test_seed_customers():
    state = CompanyState()
    state.seed_customers(10)
    assert len(state.customers) == 10
    for c in state.customers.values():
        assert c.name
        assert c.email


def test_seed_orders_requires_customers():
    state = CompanyState()
    state.seed_orders(10)
    assert len(state.orders) == 0


def test_seed_orders():
    state = CompanyState()
    state.seed_customers(5)
    state.seed_orders(20)
    assert len(state.orders) == 20
    for o in state.orders.values():
        assert o.customer_id in state.customers


def test_add_case():
    state = CompanyState()
    case = _make_case()
    result = state.add_case(case)
    assert result.case_id == case.case_id
    assert case.case_id in state.cases


def test_get_open_cases():
    state = CompanyState()
    case1 = _make_case()
    case2 = _make_case()
    state.add_case(case1)
    state.add_case(case2)
    assert len(state.get_open_cases()) == 2


def test_assign_case():
    state = CompanyState()
    case = _make_case()
    state.add_case(case)

    assigned = state.assign_case(case.case_id, "bot-1")
    assert assigned is not None
    assert assigned.status == CaseStatus.ASSIGNED
    assert assigned.assigned_to == "bot-1"
    assert len(state.get_open_cases()) == 0


def test_assign_nonexistent_case():
    state = CompanyState()
    assert state.assign_case("nonexistent", "bot-1") is None


def test_cannot_assign_already_assigned():
    state = CompanyState()
    case = _make_case()
    state.add_case(case)
    state.assign_case(case.case_id, "bot-1")
    assert state.assign_case(case.case_id, "bot-2") is None


def test_resolve_case():
    state = CompanyState()
    case = _make_case()
    state.add_case(case)
    state.assign_case(case.case_id, "bot-1")

    resolved = state.resolve_case(case.case_id, "Issue fixed")
    assert resolved is not None
    assert resolved.status == CaseStatus.RESOLVED
    assert resolved.resolution == "Issue fixed"


def test_cannot_resolve_open_case():
    state = CompanyState()
    case = _make_case()
    state.add_case(case)
    assert state.resolve_case(case.case_id, "Nope") is None


def test_customer_history():
    state = CompanyState()
    state.seed_customers(1)
    cid = list(state.customers.keys())[0]
    state.seed_orders(5)

    case = _make_case(customer_id=cid)
    state.add_case(case)

    history = state.get_customer_history(cid)
    assert "name" in history
    assert "tier" in history
    assert history["previous_cases"] == 1


def test_stats():
    state = CompanyState()
    state.seed_customers(5)
    state.seed_orders(10)
    case = _make_case()
    state.add_case(case)

    s = state.stats()
    assert s["total_customers"] == 5
    assert s["total_orders"] == 10
    assert s["total_cases"] == 1
    assert s["open_cases"] == 1
