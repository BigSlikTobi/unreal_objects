import httpx

from evals.agent_eval.agent import SimulatedAgent
from evals.agent_eval.models import AgentRunResult, AgentScenario, StepResult
from evals.agent_eval.receipt import validate_receipt


async def run_scenario(
    scenario: AgentScenario,
    rule_engine_url: str = "http://127.0.0.1:8001",
    decision_center_url: str = "http://127.0.0.1:8002",
    keep_group: bool = False,
    re_client: httpx.AsyncClient | None = None,
    dc_client: httpx.AsyncClient | None = None,
) -> AgentRunResult:
    """
    Run a single agent eval scenario end-to-end.

    Optionally accepts injected httpx clients for testing (ASGI transport).
    """
    agent = SimulatedAgent(decision_center_url=decision_center_url, client=dc_client)
    steps: list[StepResult] = []
    group_id: str | None = None

    async def _re_post(path: str, json: dict) -> httpx.Response:
        if re_client is not None:
            return await re_client.post(path, json=json)
        async with httpx.AsyncClient(timeout=20.0) as c:
            return await c.post(f"{rule_engine_url}{path}", json=json)

    async def _re_delete(path: str) -> httpx.Response:
        if re_client is not None:
            return await re_client.delete(path)
        async with httpx.AsyncClient(timeout=20.0) as c:
            return await c.delete(f"{rule_engine_url}{path}")

    def _re_path(path: str) -> str:
        """Return full path when using URL, or just path when using client."""
        if re_client is not None:
            return path
        return f"{rule_engine_url}{path}"

    try:
        resp = await _re_post(
            "/v1/groups",
            json={
                "name": scenario.group_name,
                "description": f"Agent eval group for {scenario.scenario_id}",
            },
        )
        resp.raise_for_status()
        group_id = resp.json()["id"]

        for rule in scenario.rules:
            rule_resp = await _re_post(f"/v1/groups/{group_id}/rules", json=rule)
            rule_resp.raise_for_status()

        for i, (step, assertion) in enumerate(
            zip(scenario.workflow, scenario.receipt_assertions)
        ):
            try:
                decision, agent_obeyed = await agent.execute_step(step, group_id)
                request_id = decision.get("request_id")
                actual_outcome = decision.get("outcome")
                outcome_correct = actual_outcome == step.expected_outcome

                receipt_valid, receipt_errors = await validate_receipt(
                    request_id=request_id,
                    assertion=assertion,
                    decision_center_url=decision_center_url,
                    client=dc_client,
                )

                steps.append(
                    StepResult(
                        step_index=i,
                        expected_outcome=step.expected_outcome,
                        actual_outcome=actual_outcome,
                        outcome_correct=outcome_correct,
                        agent_obeyed=agent_obeyed,
                        receipt_valid=receipt_valid,
                        receipt_errors=receipt_errors,
                        request_id=request_id,
                    )
                )
            except Exception as exc:
                steps.append(
                    StepResult(
                        step_index=i,
                        expected_outcome=step.expected_outcome,
                        actual_outcome=None,
                        outcome_correct=False,
                        agent_obeyed=False,
                        receipt_valid=False,
                        receipt_errors=[str(exc)],
                    )
                )

    except Exception as exc:
        return AgentRunResult(
            scenario_id=scenario.scenario_id,
            passed=False,
            steps=steps,
            error=str(exc),
        )
    finally:
        if group_id and not keep_group:
            try:
                await _re_delete(f"/v1/groups/{group_id}")
            except Exception:
                pass

    passed = bool(steps) and all(
        s.outcome_correct and s.agent_obeyed and s.receipt_valid for s in steps
    )
    return AgentRunResult(
        scenario_id=scenario.scenario_id,
        passed=passed,
        steps=steps,
    )
