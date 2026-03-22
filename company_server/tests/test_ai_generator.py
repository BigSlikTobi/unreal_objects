"""Tests for AICaseGenerator with mocked LLM responses."""

import json
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from company_server.clock import CompanyClock
from company_server.state import CompanyState
from support_company.ai_generator import AICaseGenerator
from support_company.models import CaseType


@pytest.fixture
def state():
    s = CompanyState()
    s.seed_customers(5)
    s.seed_orders(10)
    return s


@pytest.fixture
def clock():
    return CompanyClock(acceleration=1.0, virtual_start=datetime(2026, 1, 5, 12, 0, 0))


MOCK_LLM_RESPONSE = json.dumps({
    "case_type": "refund_request",
    "customer_tier": "premium",
    "priority": "medium",
    "risk_score": 25.0,
    "requested_action": "Full refund for defective headphones",
    "channel": "chat",
    "account_age_days": 450,
    "order_value": 89.99,
    "refund_amount": 89.99,
    "requires_identity_check": False,
    "contains_policy_exception": False,
    "narrative": "Customer reports headphones stopped working after 2 weeks. Wants full refund.",
})


@pytest.mark.asyncio
async def test_generate_with_mocked_openai(state, clock):
    gen = AICaseGenerator(provider="openai", model="gpt-4o", api_key="test-key")

    mock_message = MagicMock()
    mock_message.content = MOCK_LLM_RESPONSE
    mock_choice = MagicMock()
    mock_choice.message = mock_message
    mock_response = MagicMock()
    mock_response.choices = [mock_choice]

    mock_client = MagicMock()
    mock_client.chat.completions.create = MagicMock(return_value=mock_response)
    gen._client = mock_client

    case = await gen.generate_case(state, clock)
    assert case.case_type == CaseType.REFUND_REQUEST
    assert case.refund_amount == 89.99
    assert case.narrative != ""
    assert case.expected_business_path == "APPROVE"  # 89.99 < 500


@pytest.mark.asyncio
async def test_fallback_on_llm_failure(state, clock):
    gen = AICaseGenerator(provider="openai", model="gpt-4o", api_key="test-key")

    mock_client = MagicMock()
    mock_client.chat.completions.create = MagicMock(side_effect=Exception("API error"))
    gen._client = mock_client

    case = await gen.generate_case(state, clock)
    # Should fall back to deterministic generator
    assert case.case_id is not None
    assert case.case_type in list(CaseType)


@pytest.mark.asyncio
async def test_expected_path_computed_not_from_llm(state, clock):
    """expected_business_path should be computed deterministically, not from LLM output."""
    high_refund = json.dumps({
        "case_type": "refund_request",
        "customer_tier": "basic",
        "priority": "high",
        "risk_score": 30.0,
        "requested_action": "Refund for expensive order",
        "channel": "phone",
        "account_age_days": 100,
        "order_value": 800.0,
        "refund_amount": 750.0,
        "requires_identity_check": False,
        "contains_policy_exception": False,
        "narrative": "Customer wants refund for high-value order.",
    })

    mock_message = MagicMock()
    mock_message.content = high_refund
    mock_choice = MagicMock()
    mock_choice.message = mock_message
    mock_response = MagicMock()
    mock_response.choices = [mock_choice]

    mock_client = MagicMock()
    mock_client.chat.completions.create = MagicMock(return_value=mock_response)

    gen = AICaseGenerator(provider="openai", model="gpt-4o", api_key="test-key")
    gen._client = mock_client

    case = await gen.generate_case(state, clock)
    assert case.refund_amount == 750.0
    assert case.expected_business_path == "ASK_FOR_APPROVAL"  # > 500 threshold
