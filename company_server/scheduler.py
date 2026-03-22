"""Async scheduler that drives continuous case generation on the virtual clock."""

from __future__ import annotations

import asyncio
import logging
import random
from typing import TYPE_CHECKING

from support_company.ai_generator import AICaseGenerator
from support_company.generator import generate_case as deterministic_generate
from support_company.models import CaseType

if TYPE_CHECKING:
    from company_server.clock import CompanyClock
    from company_server.config import CompanyConfig
    from company_server.state import CompanyState
    from company_server.webhooks import WebhookDispatcher

logger = logging.getLogger(__name__)

CASE_TYPES = list(CaseType)


class CompanyScheduler:
    def __init__(
        self,
        config: CompanyConfig,
        state: CompanyState,
        clock: CompanyClock,
        webhook: WebhookDispatcher,
        use_ai: bool = True,
    ):
        self.config = config
        self.state = state
        self.clock = clock
        self.webhook = webhook
        self.use_ai = use_ai
        self._running = False
        self._task: asyncio.Task | None = None
        self._inflight = 0
        self._max_inflight = 3

        if use_ai and config.ai_api_key:
            self.ai_generator = AICaseGenerator(
                provider=config.ai_provider,
                model=config.ai_model,
                api_key=config.ai_api_key,
            )
        else:
            self.ai_generator = None

    def _compute_interval(self) -> float:
        multiplier = self.clock.activity_multiplier()
        effective_rate = self.config.base_cases_per_hour * multiplier
        if effective_rate <= 0:
            return 60.0
        base_interval = 3600.0 / (effective_rate * self.config.acceleration)
        jitter = random.uniform(-0.2, 0.2) * base_interval
        return max(1.0, base_interval + jitter)

    async def _generate_one(self) -> None:
        self._inflight += 1
        try:
            case_type_hint = random.choice(CASE_TYPES).value if random.random() < 0.3 else None

            if self.ai_generator and self._inflight <= self._max_inflight:
                case = await self.ai_generator.generate_case(
                    self.state, self.clock, case_type_hint=case_type_hint,
                )
            else:
                case = deterministic_generate()

            self.state.add_case(case)
            vt = self.clock.now()
            logger.info(
                "Case %s created [%s] at virtual time %s",
                case.case_id, case.case_type.value, vt.strftime("%Y-%m-%d %H:%M"),
            )

            server_url = f"http://{self.config.host}:{self.config.port}"
            if self.config.host == "0.0.0.0":
                server_url = f"http://localhost:{self.config.port}"
            await self.webhook.notify_case_created(case, vt, server_url)
        except Exception:
            logger.error("Failed to generate case", exc_info=True)
        finally:
            self._inflight -= 1

    async def run(self) -> None:
        self._running = True
        logger.info(
            "Scheduler started: %.1f cases/virtual-hour, %gx acceleration",
            self.config.base_cases_per_hour, self.config.acceleration,
        )
        while self._running:
            interval = self._compute_interval()
            await asyncio.sleep(interval)
            if self._running:
                asyncio.create_task(self._generate_one())

    def start(self) -> asyncio.Task:
        self._task = asyncio.create_task(self.run())
        return self._task

    def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()
