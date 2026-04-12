"""Fire-and-forget webhook dispatcher for case events."""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import logging
from datetime import datetime, timezone

import httpx

from support_company.models import SupportCase

logger = logging.getLogger(__name__)


class WebhookDispatcher:
    def __init__(self, webhook_url: str | None = None, webhook_secret: str | None = None):
        self.webhook_url = webhook_url
        self.webhook_secret = webhook_secret

    def _sign(self, body: bytes) -> str | None:
        if not self.webhook_secret:
            return None
        return hmac.new(
            self.webhook_secret.encode(), body, hashlib.sha256
        ).hexdigest()

    async def notify_case_created(
        self, case: SupportCase, company_time: datetime, server_base_url: str = "http://localhost:8010"
    ) -> None:
        if not self.webhook_url:
            return

        payload = {
            "event": "case.created",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "company_time": company_time.isoformat(),
            "data": {
                "case_id": case.case_id,
                "case_type": case.case_type.value,
                "priority": case.priority.value,
                "narrative": case.narrative,
                "pickup_url": f"{server_base_url}/api/v1/cases/{case.case_id}",
            },
        }

        body = json.dumps(payload).encode()
        headers = {"Content-Type": "application/json"}
        sig = self._sign(body)
        if sig:
            headers["X-Webhook-Signature"] = sig

        for attempt in range(2):
            try:
                async with httpx.AsyncClient(timeout=10) as client:
                    resp = await client.post(self.webhook_url, content=body, headers=headers)
                    resp.raise_for_status()
                    logger.info("Webhook delivered for case %s", case.case_id)
                    return
            except Exception:
                if attempt == 0:
                    logger.warning("Webhook attempt 1 failed, retrying in 2s", exc_info=True)
                    await asyncio.sleep(2)
                else:
                    logger.error("Webhook delivery failed for case %s after 2 attempts", case.case_id)
