"""
Programmatic generator for 500 diverse agent eval scenarios.

Covers hard edge cases: fuzzy variable mapping, fail-closed severity,
type mismatches, edge-case short-circuiting, inactive rules, outcome
precedence, legacy string fallback, string comparisons, and more.
"""

from __future__ import annotations

import itertools
import random
from typing import Any

from evals.agent_eval.models import AgentScenario, ReceiptAssertion, WorkflowStep

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_OUTCOME_RANK = {"REJECT": 3, "ASK_FOR_APPROVAL": 2, "APPROVE": 1}
_RESTRICTIVE = {"REJECT", "ASK_FOR_APPROVAL"}


def _eval_condition(op: str, val: Any, threshold: Any) -> bool:
    ops = {
        "<": lambda a, b: a < b,
        ">": lambda a, b: a > b,
        "<=": lambda a, b: a <= b,
        ">=": lambda a, b: a >= b,
        "==": lambda a, b: a == b,
        "!=": lambda a, b: a != b,
    }
    return ops[op](val, threshold)


def _make_rule(
    name: str, feature: str, var: str, op: str, threshold: Any, outcome: str,
    *, edge_cases: list[str] | None = None, edge_cases_json: list[dict] | None = None,
    active: bool = True, include_json: bool = True,
) -> dict:
    rule: dict[str, Any] = {
        "name": name,
        "feature": feature,
        "datapoints": [var],
        "edge_cases": edge_cases or [],
        "edge_cases_json": edge_cases_json or [],
        "rule_logic": f"IF {var} {op} {threshold} THEN {outcome}",
    }
    if include_json:
        rule["rule_logic_json"] = {"if": [{op: [{"var": var}, threshold]}, outcome, None]}
    else:
        rule["rule_logic_json"] = {}
    if not active:
        rule["active"] = False
    return rule


def _make_step(
    desc: str, context: dict, expected: str, human_approves: bool | None = None,
) -> WorkflowStep:
    kw: dict[str, Any] = {
        "action_description": desc,
        "context": context,
        "expected_outcome": expected,
    }
    if expected == "ASK_FOR_APPROVAL":
        kw["human_approves"] = human_approves if human_approves is not None else True
        kw["expected_approval_status"] = "APPROVED" if kw["human_approves"] else "REJECTED"
    return WorkflowStep(**kw)


def _make_assertion(outcome: str, human_approves: bool | None = None) -> ReceiptAssertion:
    events = ["REQUEST", "EVALUATION"]
    kw: dict[str, Any] = {"outcome_in_evaluation": outcome}
    if outcome == "ASK_FOR_APPROVAL":
        events.append("APPROVAL_STATUS")
        approved = human_approves if human_approves is not None else True
        kw["approval_status"] = "APPROVED" if approved else "REJECTED"
        kw["approver"] = "simulated-human"
    kw["must_have_event_types"] = events
    return ReceiptAssertion(**kw)


def _fail_closed_outcome(rule_outcome: str) -> str:
    """What the evaluator returns when data is missing/mistyped for this rule."""
    if rule_outcome in _RESTRICTIVE:
        return rule_outcome
    return "ASK_FOR_APPROVAL"


def _resolve_multi_rule(
    outcomes: list[str],
) -> str:
    """Most restrictive wins across multiple rule outcomes."""
    if not outcomes:
        return "APPROVE"
    return max(outcomes, key=lambda o: _OUTCOME_RANK.get(o, 0))


# ---------------------------------------------------------------------------
# Domain configs
# ---------------------------------------------------------------------------

_DOMAINS = [
    {
        "domain": "finance",
        "variables": [
            ("amount", "transfer_amount", [100, 500, 1000, 4999, 5000, 5001, 10000, 50000]),
            ("aml_score", "aml_check", [0.0, 0.1, 0.3, 0.5, 0.79, 0.8, 0.81, 0.95]),
            ("fraud_score", "fraud_detection", [0.0, 0.1, 0.4, 0.5, 0.6, 0.8, 0.95]),
            ("credit_score", "credit_check", [300, 500, 580, 620, 700, 800]),
            ("account_age_days", "account_maturity", [0, 7, 30, 60, 90, 365]),
            ("balance", "balance_check", [0, 100, 1000, 5000, 50000]),
        ],
        "extra_context": {"currency": "USD", "beneficiary": "Eval-Corp"},
        # Fuzzy mapping pairs: (rule_var, context_var) — substring match expected
        "fuzzy_pairs": [
            ("amount", "transaction_amount"),
            ("score", "aml_score"),
            ("age_days", "account_age_days"),
        ],
    },
    {
        "domain": "ecommerce",
        "variables": [
            ("order_value", "order_value_check", [10, 50, 100, 499, 500, 501, 1000, 5000]),
            ("fraud_score", "fraud_detection", [0.0, 0.1, 0.5, 0.89, 0.9, 0.91, 0.99]),
            ("item_count", "bulk_order_check", [1, 5, 10, 20, 50, 100]),
            ("return_rate", "return_abuse", [0.0, 0.05, 0.1, 0.3, 0.5, 0.7]),
            ("discount_pct", "discount_check", [0, 5, 10, 20, 50, 90]),
        ],
        "extra_context": {"customer_id": "C-EVAL", "product": "Widget"},
        "fuzzy_pairs": [
            ("value", "order_value"),
            ("count", "item_count"),
        ],
    },
    {
        "domain": "healthcare",
        "variables": [
            ("dosage_mg", "dosage_check", [5, 10, 50, 100, 200, 500, 1000]),
            ("patient_age", "age_check", [0, 1, 12, 18, 50, 65, 100]),
            ("risk_score", "risk_assessment", [0.0, 0.1, 0.3, 0.5, 0.7, 0.95]),
            ("insurance_coverage_pct", "coverage_check", [0, 25, 50, 80, 100]),
        ],
        "extra_context": {"provider": "EvalClinic"},
        "fuzzy_pairs": [
            ("age", "patient_age"),
            ("dosage", "dosage_mg"),
        ],
    },
    {
        "domain": "logistics",
        "variables": [
            ("package_weight_kg", "weight_check", [0.1, 1, 5, 10, 25, 50, 100]),
            ("delivery_distance_km", "distance_check", [1, 50, 100, 500, 1000, 5000]),
            ("delay_hours", "delay_check", [0, 1, 4, 12, 24, 48, 72]),
            ("package_value", "value_check", [10, 100, 500, 1000, 5000, 10000]),
        ],
        "extra_context": {"carrier": "EvalShip"},
        "fuzzy_pairs": [
            ("weight", "package_weight_kg"),
            ("distance", "delivery_distance_km"),
        ],
    },
    {
        "domain": "hr",
        "variables": [
            ("salary", "salary_check", [30000, 50000, 75000, 100000, 200000]),
            ("tenure_years", "tenure_check", [0, 0.5, 1, 5, 10, 20]),
            ("performance_score", "performance_check", [1, 3, 5, 7, 10]),
            ("expense_amount", "expense_check", [10, 100, 250, 500, 1000, 5000]),
        ],
        "extra_context": {"employee_id": "E-EVAL"},
        "fuzzy_pairs": [
            ("expense", "expense_amount"),
            ("tenure", "tenure_years"),
        ],
    },
]

_OPERATORS = ["<", ">", "<=", ">="]
_OUTCOMES = ["APPROVE", "REJECT", "ASK_FOR_APPROVAL"]


# ---------------------------------------------------------------------------
# Pattern generators — each returns a list of AgentScenario
# ---------------------------------------------------------------------------


def _gen_single_rule(rng: random.Random, start_id: int, count: int) -> list[AgentScenario]:
    """Pattern 1: basic single-rule, single-step across domains."""
    scenarios: list[AgentScenario] = []
    sid = start_id
    combos = []
    for d in _DOMAINS:
        for var, feat, vals in d["variables"]:
            for op in _OPERATORS:
                for outcome in _OUTCOMES:
                    combos.append((d, var, feat, vals, op, outcome))
    rng.shuffle(combos)
    for d, var, feat, vals, op, outcome in combos[:count]:
        mid = vals[len(vals) // 2]
        # pick a value that triggers the rule
        trigger = vals[-1] if op in ("<", "<=") else vals[0]
        if not _eval_condition(op, trigger, mid):
            trigger = vals[0] if op in ("<", "<=") else vals[-1]
        if not _eval_condition(op, trigger, mid):
            continue
        ctx = {var: trigger, **d["extra_context"]}
        ha = rng.choice([True, False]) if outcome == "ASK_FOR_APPROVAL" else None
        scenarios.append(AgentScenario(
            scenario_id=f"gen_single_{sid:04d}",
            description=f"{d['domain']}: {var} {op} {mid} → {outcome}",
            group_name=f"Gen Single {sid}",
            rules=[_make_rule(f"R-{sid}", feat, var, op, mid, outcome)],
            workflow=[_make_step(f"single {var}={trigger}", ctx, outcome, ha)],
            receipt_assertions=[_make_assertion(outcome, ha)],
        ))
        sid += 1
    return scenarios[:count]


def _gen_boundary(rng: random.Random, start_id: int, count: int) -> list[AgentScenario]:
    """Pattern 2: value exactly at threshold — tests <, <=, >, >= boundary semantics."""
    scenarios: list[AgentScenario] = []
    sid = start_id
    for d in _DOMAINS:
        for var, feat, vals in d["variables"]:
            for threshold in vals[1:-1]:
                for op in _OPERATORS:
                    if len(scenarios) >= count:
                        return scenarios[:count]
                    outcome = rng.choice(_OUTCOMES)
                    # Value == threshold: < and > are false, <= and >= are true
                    triggers = op in ("<=", ">=", "==")
                    if triggers:
                        resolved = outcome
                    else:
                        resolved = "APPROVE"  # rule doesn't fire → default APPROVE
                    ctx = {var: threshold, **d["extra_context"]}
                    ha = rng.choice([True, False]) if resolved == "ASK_FOR_APPROVAL" else None
                    scenarios.append(AgentScenario(
                        scenario_id=f"gen_boundary_{sid:04d}",
                        description=f"{d['domain']}: boundary {var}={threshold}, op={op}",
                        group_name=f"Gen Boundary {sid}",
                        rules=[_make_rule(f"Bnd-{sid}", feat, var, op, threshold, outcome)],
                        workflow=[_make_step(f"boundary {var}={threshold}", ctx, resolved, ha)],
                        receipt_assertions=[_make_assertion(resolved, ha)],
                    ))
                    sid += 1
    return scenarios[:count]


def _gen_no_match_fallthrough(rng: random.Random, start_id: int, count: int) -> list[AgentScenario]:
    """Pattern 3: rule condition NOT met → default APPROVE."""
    scenarios: list[AgentScenario] = []
    sid = start_id
    for _ in range(count):
        d = rng.choice(_DOMAINS)
        var, feat, vals = rng.choice(d["variables"])
        op = rng.choice(_OPERATORS)
        threshold = vals[len(vals) // 2]
        outcome = rng.choice(["REJECT", "ASK_FOR_APPROVAL"])
        # Pick value that does NOT trigger the condition
        non_trigger = vals[0] if op in ("<", "<=") else vals[-1]
        if _eval_condition(op, non_trigger, threshold):
            non_trigger = vals[-1] if op in ("<", "<=") else vals[0]
        if _eval_condition(op, non_trigger, threshold):
            continue  # skip if we can't find a non-triggering value
        ctx = {var: non_trigger, **d["extra_context"]}
        scenarios.append(AgentScenario(
            scenario_id=f"gen_nomatch_{sid:04d}",
            description=f"{d['domain']}: {var}={non_trigger} does NOT trigger {op} {threshold}",
            group_name=f"Gen NoMatch {sid}",
            rules=[_make_rule(f"NM-{sid}", feat, var, op, threshold, outcome)],
            workflow=[_make_step(f"no-match {var}={non_trigger}", ctx, "APPROVE")],
            receipt_assertions=[_make_assertion("APPROVE")],
        ))
        sid += 1
    return scenarios[:count]


def _gen_fail_closed_missing(rng: random.Random, start_id: int, count: int) -> list[AgentScenario]:
    """Pattern 4: missing variable → fail-closed.
    APPROVE rules fail to ASK_FOR_APPROVAL, REJECT rules fail to REJECT.
    """
    scenarios: list[AgentScenario] = []
    sid = start_id
    for d in _DOMAINS:
        for var, feat, vals in d["variables"]:
            for outcome in _OUTCOMES:
                if len(scenarios) >= count:
                    return scenarios[:count]
                threshold = vals[len(vals) // 2]
                op = rng.choice(_OPERATORS)
                rules = [_make_rule(f"FC-{sid}", feat, var, op, threshold, outcome)]
                ctx = dict(d["extra_context"])  # deliberately missing the variable
                expected = _fail_closed_outcome(outcome)
                ha = rng.choice([True, False]) if expected == "ASK_FOR_APPROVAL" else None
                scenarios.append(AgentScenario(
                    scenario_id=f"gen_failclosed_{sid:04d}",
                    description=f"{d['domain']}: missing {var}, rule={outcome} → fail-closed {expected}",
                    group_name=f"Gen FailClosed {sid}",
                    rules=rules,
                    workflow=[_make_step(f"missing {var}", ctx, expected, ha)],
                    receipt_assertions=[_make_assertion(expected, ha)],
                ))
                sid += 1
    return scenarios[:count]


def _gen_type_mismatch(rng: random.Random, start_id: int, count: int) -> list[AgentScenario]:
    """Pattern 5: string value where number expected → fail-closed."""
    scenarios: list[AgentScenario] = []
    sid = start_id
    bad_values = ["not_a_number", "NaN", "null", "", "true", "high"]
    for d in _DOMAINS:
        for var, feat, vals in d["variables"]:
            for bad_val in rng.sample(bad_values, min(2, len(bad_values))):
                if len(scenarios) >= count:
                    return scenarios[:count]
                outcome = rng.choice(_OUTCOMES)
                threshold = vals[len(vals) // 2]
                op = rng.choice(_OPERATORS)
                expected = _fail_closed_outcome(outcome)
                ctx = {var: bad_val, **d["extra_context"]}
                ha = rng.choice([True, False]) if expected == "ASK_FOR_APPROVAL" else None
                scenarios.append(AgentScenario(
                    scenario_id=f"gen_typemismatch_{sid:04d}",
                    description=f"{d['domain']}: {var}='{bad_val}' (type mismatch) → {expected}",
                    group_name=f"Gen TypeMismatch {sid}",
                    rules=[_make_rule(f"TM-{sid}", feat, var, op, threshold, outcome)],
                    workflow=[_make_step(f"type mismatch {var}='{bad_val}'", ctx, expected, ha)],
                    receipt_assertions=[_make_assertion(expected, ha)],
                ))
                sid += 1
    return scenarios[:count]


def _gen_fuzzy_mapping(rng: random.Random, start_id: int, count: int) -> list[AgentScenario]:
    """Pattern 6: context key differs from rule var — fuzzy/substring match should resolve."""
    scenarios: list[AgentScenario] = []
    sid = start_id
    for d in _DOMAINS:
        fuzzy_pairs = d.get("fuzzy_pairs", [])
        if not fuzzy_pairs:
            continue
        for rule_var, ctx_var in fuzzy_pairs:
            for op in _OPERATORS:
                for outcome in _OUTCOMES:
                    if len(scenarios) >= count:
                        return scenarios[:count]
                    # Find the real variable definition to get valid values
                    var_def = None
                    for v, f, vs in d["variables"]:
                        if v == ctx_var or rule_var in v:
                            var_def = (v, f, vs)
                            break
                    if not var_def:
                        continue
                    _, feat, vals = var_def
                    threshold = vals[len(vals) // 2]
                    trigger = vals[-1] if op in ("<", "<=") else vals[0]
                    if not _eval_condition(op, trigger, threshold):
                        trigger = vals[0] if op in ("<", "<=") else vals[-1]
                    if not _eval_condition(op, trigger, threshold):
                        continue
                    # Context uses the DIFFERENT key name — evaluator must fuzzy-resolve
                    ctx = {ctx_var: trigger, **d["extra_context"]}
                    ha = rng.choice([True, False]) if outcome == "ASK_FOR_APPROVAL" else None
                    scenarios.append(AgentScenario(
                        scenario_id=f"gen_fuzzy_{sid:04d}",
                        description=f"{d['domain']}: rule expects '{rule_var}', ctx has '{ctx_var}'",
                        group_name=f"Gen Fuzzy {sid}",
                        rules=[_make_rule(f"Fz-{sid}", feat, rule_var, op, threshold, outcome)],
                        workflow=[_make_step(f"fuzzy {ctx_var}={trigger}", ctx, outcome, ha)],
                        receipt_assertions=[_make_assertion(outcome, ha)],
                    ))
                    sid += 1
    return scenarios[:count]


def _gen_edge_case_shortcircuit(rng: random.Random, start_id: int, count: int) -> list[AgentScenario]:
    """Pattern 7: edge_cases_json fires and overrides the main rule logic."""
    scenarios: list[AgentScenario] = []
    sid = start_id
    for _ in range(count):
        d = rng.choice(_DOMAINS)
        var, feat, vals = rng.choice(d["variables"])
        threshold = vals[len(vals) // 2]
        edge_threshold = vals[1]  # lower threshold for edge case
        main_outcome = "APPROVE"
        edge_outcome = rng.choice(["REJECT", "ASK_FOR_APPROVAL"])

        # Edge case: if var < edge_threshold → edge_outcome
        # Main rule: if var > threshold → APPROVE
        # Test with a value that triggers the edge case but NOT the main rule
        trigger_val = vals[0]  # smallest value
        ec_op = "<="
        main_op = ">"

        if not _eval_condition(ec_op, trigger_val, edge_threshold):
            continue

        ctx = {var: trigger_val, **d["extra_context"]}
        ha = rng.choice([True, False]) if edge_outcome == "ASK_FOR_APPROVAL" else None
        rule = _make_rule(
            f"EC-{sid}", feat, var, main_op, threshold, main_outcome,
            edge_cases=[f"IF {var} {ec_op} {edge_threshold} THEN {edge_outcome}"],
            edge_cases_json=[{"if": [{ec_op: [{"var": var}, edge_threshold]}, edge_outcome, None]}],
        )
        scenarios.append(AgentScenario(
            scenario_id=f"gen_edgecase_{sid:04d}",
            description=f"{d['domain']}: edge case {var} {ec_op} {edge_threshold} overrides main rule",
            group_name=f"Gen EdgeCase {sid}",
            rules=[rule],
            workflow=[_make_step(f"edge case {var}={trigger_val}", ctx, edge_outcome, ha)],
            receipt_assertions=[_make_assertion(edge_outcome, ha)],
        ))
        sid += 1
    return scenarios[:count]


def _gen_inactive_rule(rng: random.Random, start_id: int, count: int) -> list[AgentScenario]:
    """Pattern 8: inactive rule should be skipped → APPROVE (no active rules match)."""
    scenarios: list[AgentScenario] = []
    sid = start_id
    for _ in range(count):
        d = rng.choice(_DOMAINS)
        var, feat, vals = rng.choice(d["variables"])
        threshold = vals[len(vals) // 2]
        op = rng.choice(_OPERATORS)
        trigger = vals[-1] if op in (">", ">=") else vals[0]
        if not _eval_condition(op, trigger, threshold):
            trigger = vals[0] if op in (">", ">=") else vals[-1]
        if not _eval_condition(op, trigger, threshold):
            continue
        ctx = {var: trigger, **d["extra_context"]}
        # Rule would fire REJECT, but it's inactive → APPROVE
        rule = _make_rule(f"Inactive-{sid}", feat, var, op, threshold, "REJECT", active=False)
        scenarios.append(AgentScenario(
            scenario_id=f"gen_inactive_{sid:04d}",
            description=f"{d['domain']}: inactive REJECT rule on {var} → APPROVE",
            group_name=f"Gen Inactive {sid}",
            rules=[rule],
            workflow=[_make_step(f"inactive rule {var}={trigger}", ctx, "APPROVE")],
            receipt_assertions=[_make_assertion("APPROVE")],
        ))
        sid += 1
    return scenarios[:count]


def _gen_precedence(rng: random.Random, start_id: int, count: int) -> list[AgentScenario]:
    """Pattern 9: multi-rule with conflicting outcomes — most restrictive wins."""
    scenarios: list[AgentScenario] = []
    sid = start_id
    # Specific precedence combos to test
    combos = [
        (["APPROVE", "REJECT"], "REJECT"),
        (["APPROVE", "ASK_FOR_APPROVAL"], "ASK_FOR_APPROVAL"),
        (["APPROVE", "ASK_FOR_APPROVAL", "REJECT"], "REJECT"),
        (["ASK_FOR_APPROVAL", "REJECT"], "REJECT"),
        (["APPROVE", "APPROVE"], "APPROVE"),
        (["ASK_FOR_APPROVAL", "ASK_FOR_APPROVAL"], "ASK_FOR_APPROVAL"),
    ]
    for rule_outcomes, expected in combos:
        for _ in range(count // len(combos) + 1):
            if len(scenarios) >= count:
                return scenarios[:count]
            d = rng.choice(_DOMAINS)
            if len(d["variables"]) < len(rule_outcomes):
                continue
            chosen = rng.sample(d["variables"], len(rule_outcomes))
            rules = []
            ctx = dict(d["extra_context"])
            for i, ((var, feat, vals), outcome) in enumerate(zip(chosen, rule_outcomes)):
                op = rng.choice(_OPERATORS)
                threshold = vals[len(vals) // 2]
                trigger = vals[-1] if op in ("<", "<=") else vals[0]
                if not _eval_condition(op, trigger, threshold):
                    trigger = vals[0] if op in ("<", "<=") else vals[-1]
                if not _eval_condition(op, trigger, threshold):
                    break
                ctx[var] = trigger
                rules.append(_make_rule(f"Prec-{sid}-{i}", feat, var, op, threshold, outcome))
            else:
                ha = rng.choice([True, False]) if expected == "ASK_FOR_APPROVAL" else None
                scenarios.append(AgentScenario(
                    scenario_id=f"gen_prec_{sid:04d}",
                    description=f"{d['domain']}: precedence {'+'.join(rule_outcomes)} → {expected}",
                    group_name=f"Gen Precedence {sid}",
                    rules=rules,
                    workflow=[_make_step(f"precedence test", ctx, expected, ha)],
                    receipt_assertions=[_make_assertion(expected, ha)],
                ))
                sid += 1
    return scenarios[:count]


def _gen_legacy_fallback(rng: random.Random, start_id: int, count: int) -> list[AgentScenario]:
    """Pattern 10: rule_logic_json is empty → falls back to legacy string parsing."""
    scenarios: list[AgentScenario] = []
    sid = start_id
    for _ in range(count):
        d = rng.choice(_DOMAINS)
        var, feat, vals = rng.choice(d["variables"])
        op = rng.choice(_OPERATORS)
        outcome = rng.choice(_OUTCOMES)
        threshold = vals[len(vals) // 2]
        trigger = vals[-1] if op in ("<", "<=") else vals[0]
        if not _eval_condition(op, trigger, threshold):
            trigger = vals[0] if op in ("<", "<=") else vals[-1]
        if not _eval_condition(op, trigger, threshold):
            continue
        ctx = {var: trigger, **d["extra_context"]}
        ha = rng.choice([True, False]) if outcome == "ASK_FOR_APPROVAL" else None
        rule = _make_rule(f"Legacy-{sid}", feat, var, op, threshold, outcome, include_json=False)
        scenarios.append(AgentScenario(
            scenario_id=f"gen_legacy_{sid:04d}",
            description=f"{d['domain']}: legacy string fallback {var} {op} {threshold}",
            group_name=f"Gen Legacy {sid}",
            rules=[rule],
            workflow=[_make_step(f"legacy {var}={trigger}", ctx, outcome, ha)],
            receipt_assertions=[_make_assertion(outcome, ha)],
        ))
        sid += 1
    return scenarios[:count]


def _gen_multi_step(rng: random.Random, start_id: int, count: int) -> list[AgentScenario]:
    """Pattern 11: multi-step workflows mixing outcomes."""
    scenarios: list[AgentScenario] = []
    sid = start_id
    for _ in range(count):
        d = rng.choice(_DOMAINS)
        var, feat, vals = rng.choice(d["variables"])
        op = rng.choice(_OPERATORS)
        threshold = vals[len(vals) // 2]
        outcome = rng.choice(_OUTCOMES)
        rules = [_make_rule(f"MS-{sid}", feat, var, op, threshold, outcome)]

        n_steps = rng.choice([2, 3, 4])
        steps = []
        assertions = []
        for _ in range(n_steps):
            val = rng.choice(vals)
            ctx = {var: val, **d["extra_context"]}
            if _eval_condition(op, val, threshold):
                resolved = outcome
            else:
                resolved = "APPROVE"
            ha = rng.choice([True, False]) if resolved == "ASK_FOR_APPROVAL" else None
            steps.append(_make_step(f"step {var}={val}", ctx, resolved, ha))
            assertions.append(_make_assertion(resolved, ha))

        scenarios.append(AgentScenario(
            scenario_id=f"gen_multistep_{sid:04d}",
            description=f"{d['domain']}: {n_steps}-step on {var} {op} {threshold}",
            group_name=f"Gen MultiStep {sid}",
            rules=rules,
            workflow=steps,
            receipt_assertions=assertions,
        ))
        sid += 1
    return scenarios[:count]


def _gen_fail_closed_type_mismatch_multi(rng: random.Random, start_id: int, count: int) -> list[AgentScenario]:
    """Pattern 12: multi-rule where one has missing data, testing precedence with fail-closed."""
    scenarios: list[AgentScenario] = []
    sid = start_id
    for _ in range(count):
        d = rng.choice(_DOMAINS)
        if len(d["variables"]) < 2:
            continue
        (var1, feat1, vals1), (var2, feat2, vals2) = rng.sample(d["variables"], 2)
        op1 = rng.choice(_OPERATORS)
        op2 = rng.choice(_OPERATORS)
        t1 = vals1[len(vals1) // 2]
        t2 = vals2[len(vals2) // 2]
        outcome1 = rng.choice(_OUTCOMES)
        outcome2 = rng.choice(_OUTCOMES)

        # var1 is present and triggers, var2 is MISSING
        trigger1 = vals1[-1] if op1 in ("<", "<=") else vals1[0]
        if not _eval_condition(op1, trigger1, t1):
            trigger1 = vals1[0] if op1 in ("<", "<=") else vals1[-1]
        if not _eval_condition(op1, trigger1, t1):
            continue

        ctx = {var1: trigger1, **d["extra_context"]}  # var2 missing
        # Rule 1 fires with outcome1, Rule 2 fail-closes
        fc = _fail_closed_outcome(outcome2)
        expected = _resolve_multi_rule([outcome1, fc])
        ha = rng.choice([True, False]) if expected == "ASK_FOR_APPROVAL" else None

        scenarios.append(AgentScenario(
            scenario_id=f"gen_fcmulti_{sid:04d}",
            description=f"{d['domain']}: {var1} fires {outcome1} + missing {var2} fail-closes {fc} → {expected}",
            group_name=f"Gen FCMulti {sid}",
            rules=[
                _make_rule(f"FCM-{sid}-0", feat1, var1, op1, t1, outcome1),
                _make_rule(f"FCM-{sid}-1", feat2, var2, op2, t2, outcome2),
            ],
            workflow=[_make_step(f"mixed {var1}={trigger1}, {var2}=missing", ctx, expected, ha)],
            receipt_assertions=[_make_assertion(expected, ha)],
        ))
        sid += 1
    return scenarios[:count]


# ---------------------------------------------------------------------------
# Main generator with quotas
# ---------------------------------------------------------------------------

def generate_scenarios(count: int = 500, seed: int = 42) -> list[AgentScenario]:
    rng = random.Random(seed)

    # Quota allocation — prioritize hard edge cases
    # Slightly over-allocate so we can trim to exactly `count`
    quotas = {
        "single_rule": 55,
        "boundary": 60,
        "no_match": 45,
        "fail_closed": 60,
        "type_mismatch": 55,
        "fuzzy_mapping": 40,
        "edge_case_sc": 35,
        "inactive_rule": 25,
        "precedence": 40,
        "legacy_fallback": 35,
        "multi_step": 40,
        "fc_multi": 40,
    }

    sid = 0
    all_scenarios: list[AgentScenario] = []

    generators = [
        ("single_rule", _gen_single_rule),
        ("boundary", _gen_boundary),
        ("no_match", _gen_no_match_fallthrough),
        ("fail_closed", _gen_fail_closed_missing),
        ("type_mismatch", _gen_type_mismatch),
        ("fuzzy_mapping", _gen_fuzzy_mapping),
        ("edge_case_sc", _gen_edge_case_shortcircuit),
        ("inactive_rule", _gen_inactive_rule),
        ("precedence", _gen_precedence),
        ("legacy_fallback", _gen_legacy_fallback),
        ("multi_step", _gen_multi_step),
        ("fc_multi", _gen_fail_closed_type_mismatch_multi),
    ]

    for name, gen_fn in generators:
        batch = gen_fn(rng, sid, quotas[name])
        all_scenarios.extend(batch)
        sid += len(batch)

    return all_scenarios[:count]


GENERATED_SCENARIOS = generate_scenarios(500)
