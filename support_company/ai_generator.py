"""LLM-powered case generator using OpenAI structured output."""

from __future__ import annotations

import json
import logging
import random
from typing import TYPE_CHECKING

from support_company.generator import _compute_expected_path, generate_case
from support_company.models import CaseType, SupportCase
from support_company.prompts import CASE_GENERATION_SYSTEM_PROMPT, build_case_prompt

if TYPE_CHECKING:
    from company_server.clock import CompanyClock
    from company_server.state import CompanyState

logger = logging.getLogger(__name__)


class AICaseGenerator:
    def __init__(self, provider: str = "openai", model: str = "gpt-4o", api_key: str = ""):
        self.provider = provider
        self.model = model
        self.api_key = api_key
        self._client = None

    def _get_client(self):
        if self._client is None:
            if self.provider == "openai":
                from openai import OpenAI
                self._client = OpenAI(api_key=self.api_key)
            else:
                raise ValueError(f"Unsupported AI provider: {self.provider}")
        return self._client

    async def generate_case(
        self,
        company_state: CompanyState,
        clock: CompanyClock,
        case_type_hint: str | None = None,
    ) -> SupportCase:
        try:
            return await self._generate_with_llm(company_state, clock, case_type_hint)
        except Exception:
            logger.warning("LLM case generation failed, falling back to deterministic", exc_info=True)
            return generate_case()

    async def _generate_with_llm(
        self,
        company_state: CompanyState,
        clock: CompanyClock,
        case_type_hint: str | None = None,
    ) -> SupportCase:
        # Pick a random customer for context
        customer = None
        customer_history = None
        customer_name = None
        if company_state.customers:
            customer_id = random.choice(list(company_state.customers.keys()))
            customer = company_state.customers[customer_id]
            customer_name = customer.name
            customer_history = company_state.get_customer_history(customer_id)

        vt = clock.now()
        time_context = f"{vt.strftime('%A %B %d, %Y %H:%M')} (company virtual time)"

        user_prompt = build_case_prompt(
            customer_name=customer_name,
            customer_history=customer_history,
            time_context=time_context,
            case_type_hint=case_type_hint,
        )

        client = self._get_client()

        # Run sync OpenAI call in thread to keep async
        import asyncio
        response = await asyncio.to_thread(
            client.chat.completions.create,
            model=self.model,
            messages=[
                {"role": "system", "content": CASE_GENERATION_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            response_format={"type": "json_object"},
            temperature=0.9,
        )

        raw = response.choices[0].message.content
        data = json.loads(raw)

        # Compute expected_business_path deterministically
        case_type = CaseType(data["case_type"])
        risk_score = float(data.get("risk_score", 0))
        refund_amount = float(data.get("refund_amount", 0))

        from support_company.models import CustomerTier, Priority
        priority = Priority(data.get("priority", "medium"))
        customer_tier = CustomerTier(data.get("customer_tier", "basic"))

        expected = _compute_expected_path(
            case_type, risk_score,
            refund_amount=refund_amount,
            priority=priority,
            customer_tier=customer_tier,
            requires_identity_check=data.get("requires_identity_check", False),
            contains_policy_exception=data.get("contains_policy_exception", False),
        )

        case = SupportCase(
            case_type=case_type,
            customer_tier=customer_tier,
            priority=priority,
            risk_score=risk_score,
            requested_action=data.get("requested_action", ""),
            channel=data.get("channel", "email"),
            account_age_days=int(data.get("account_age_days", 365)),
            order_value=float(data.get("order_value", 0)),
            refund_amount=refund_amount,
            requires_identity_check=data.get("requires_identity_check", False),
            contains_policy_exception=data.get("contains_policy_exception", False),
            expected_business_path=expected,
            narrative=data.get("narrative", ""),
            customer_id=customer.id if customer else None,
        )
        return case
