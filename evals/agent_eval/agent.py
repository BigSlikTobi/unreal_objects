import httpx
from evals.agent_eval.models import WorkflowStep


class SimulatedAgent:
    """Deterministic state machine agent — no LLM, fully reproducible."""

    def __init__(self, decision_center_url: str, client: httpx.AsyncClient | None = None):
        self.decision_center_url = decision_center_url
        self._client = client

    async def execute_step(
        self, step: WorkflowStep, group_id: str
    ) -> tuple[dict, bool]:
        """
        Execute one workflow step.

        Returns:
            (raw_decision_response, agent_obeyed)
        """
        payload = {
            "request_description": step.action_description,
            "context": step.context,
            "group_id": group_id,
            "agent_id": "simulated-agent",
            "credential_id": "eval-credential",
            "user_id": "eval-user",
        }

        if self._client is not None:
            resp = await self._client.post(
                f"{self.decision_center_url}/v1/decide", json=payload
            )
            resp.raise_for_status()
            decision = resp.json()
        else:
            async with httpx.AsyncClient(timeout=20.0) as client:
                resp = await client.post(
                    f"{self.decision_center_url}/v1/decide", json=payload
                )
                resp.raise_for_status()
                decision = resp.json()

        request_id = decision.get("request_id")
        outcome = decision.get("outcome")

        if outcome == "ASK_FOR_APPROVAL":
            approval_payload = {
                "approved": step.human_approves,
                "approver": "simulated-human",
            }
            if self._client is not None:
                approval_resp = await self._client.post(
                    f"{self.decision_center_url}/v1/decide/{request_id}/approve",
                    json=approval_payload,
                )
                approval_resp.raise_for_status()
            else:
                async with httpx.AsyncClient(timeout=20.0) as client:
                    approval_resp = await client.post(
                        f"{self.decision_center_url}/v1/decide/{request_id}/approve",
                        json=approval_payload,
                    )
                    approval_resp.raise_for_status()
            agent_obeyed = True
        elif outcome in ("APPROVE", "REJECT"):
            agent_obeyed = True
        else:
            agent_obeyed = False

        return decision, agent_obeyed
