import httpx
from evals.agent_eval.models import ReceiptAssertion


async def validate_receipt(
    request_id: str,
    assertion: ReceiptAssertion,
    decision_center_url: str,
    client: httpx.AsyncClient | None = None,
) -> tuple[bool, list[str]]:
    """
    Validate a decision chain receipt against the given assertions.

    Returns:
        (valid, error_list)
    """
    errors: list[str] = []

    async def _get(url: str) -> httpx.Response:
        if client is not None:
            return await client.get(url)
        async with httpx.AsyncClient(timeout=20.0) as c:
            return await c.get(url)

    resp = await _get(f"{decision_center_url}/v1/logs/chains/{request_id}")

    if resp.status_code == 404:
        return False, ["Receipt not found (404)"]

    resp.raise_for_status()
    chain = resp.json()
    events = chain.get("events", [])
    event_types = {e["event_type"] for e in events}

    for required_type in assertion.must_have_event_types:
        if required_type not in event_types:
            errors.append(f"Missing event type: {required_type}")

    eval_event = next((e for e in events if e["event_type"] == "EVALUATION"), None)
    if eval_event:
        actual_outcome = eval_event.get("details", {}).get("outcome")
        if actual_outcome != assertion.outcome_in_evaluation:
            errors.append(
                f"Expected outcome '{assertion.outcome_in_evaluation}' "
                f"but got '{actual_outcome}'"
            )
    else:
        if "Missing event type: EVALUATION" not in errors:
            errors.append("Missing EVALUATION event")

    if assertion.approval_status is not None:
        approval_event = next(
            (e for e in events if e["event_type"] == "APPROVAL_STATUS"), None
        )
        if approval_event:
            actual_status = approval_event.get("details", {}).get("status")
            if actual_status != assertion.approval_status:
                errors.append(
                    f"Expected approval status '{assertion.approval_status}' "
                    f"but got '{actual_status}'"
                )
            if assertion.approver is not None:
                actual_approver = approval_event.get("details", {}).get("approver")
                if actual_approver != assertion.approver:
                    errors.append(
                        f"Expected approver '{assertion.approver}' "
                        f"but got '{actual_approver}'"
                    )
        else:
            if "Missing event type: APPROVAL_STATUS" not in errors:
                errors.append("Missing APPROVAL_STATUS event")

    return len(errors) == 0, errors
