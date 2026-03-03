import json
import re
from pydantic import BaseModel, Field
from pydantic import ValidationError
import openai
import anthropic
from google import genai

class SchemaConceptMismatchError(ValueError):
    """Raised when a translated rule uses a variable that is not in the active
    schema, or when the LLM signals that the requested concept has no schema
    equivalent.  Carries an optional *proposed_field* dict that the caller can
    surface to let the user extend the schema inline."""

    def __init__(self, message: str, proposed_field: dict | None = None):
        super().__init__(message)
        self.proposed_field = proposed_field

PSEUDO_DATAPOINT_TOKENS = {
    "exists",
    "missing",
    "present",
    "field",
    "schema",
    "value",
    "time",
    "days",
    "valid",
    "invalid",
}

class RuleLogicDefinition(BaseModel):
    datapoints: list[str] = Field(..., description="A list of specific datapoints extracted from the natural language rule. Normalize variables into snake_case.")
    edge_cases: list[str] = Field(default_factory=list, description="A list of edge cases in the format: IF <condition> THEN <outcome>. E.g.: IF currency <> eur THEN REJECT")
    edge_cases_json: list[dict] = Field(default_factory=list, description="The JSON Logic formats for edge cases. Should evaluate to an outcome string or null. E.g. {'if': [{'!=': [{'var':'currency'}, 'eur']}, 'REJECT', null]}")
    rule_logic: str = Field(..., description="The main logic represented in the format: IF <condition> THEN <outcome>. E.g.: IF billing_amount > 100 THEN ASK_FOR_APPROVAL")
    rule_logic_json: dict = Field(..., description="The main logic parsed into standard JSON Logic format. E.g.: {'if': [{'>': [{'var': 'billing_amount'}, 100]}, 'ASK_FOR_APPROVAL', null]}")

SYS_PROMPT = """You are an expert business logic rule translator for the 'Decision Center'.
Your job is to translate a given natural language prompt detailing a business rule into strictly structured data containing datapoints, edge cases, and the logical formula.

You must provide BOTH a human-readable string representation (`rule_logic`, `edge_cases`) AND a deterministic JSON Logic representation (`rule_logic_json`, `edge_cases_json`).

Human Readable format: `IF <conditions> THEN <outcome>`
JSON Logic format: Must strictly follow jsonlogic.com specs and evaluate to an outcome string ("APPROVE", "REJECT", "ASK_FOR_APPROVAL") or null.
Note: For equality checking in JSON Logic use `"=="` instead of `"="`.

CRITICAL VARIABLE INSTRUCTION:
You MUST use the exact variable names that are explicitly mentioned in the natural language rule. For example, if the rule says "transaction_amount > 500", your JSON Logic must use `{"var": "transaction_amount"}`. DO NOT invent, normalize, or alter the variable names unless strictly necessary. If a variable is written in snake_case in the text, extract it verbatim.
Never output pseudo-datapoints or explanatory helper variables. Forbidden examples include `exists`, `missing`, `present`, `field`, `schema`, `value`, `time`, `days`, and similar words when they are not actual business field names.
Datapoints must be concrete domain fields only. Comments or explanations about missing schema support must stay in prose and must never become datapoints.

CRITICAL - String comparison values:
Always use the exact machine-readable format that a system or API would send, not human-readable equivalents.
- Currency: use ISO 4217 codes ("EUR", "USD", "GBP") not full names ("Euro", "Dollar", "Pound")
- Status fields: use lowercase codes ("active", "pending", "rejected") not display labels
- Country: use ISO 3166 codes ("DE", "US", "GB") not full names
- Boolean-like: use "true"/"false" not "yes"/"no"
When the natural language is ambiguous about the exact string format, pick the most common programmatic representation and add a comment in the human-readable rule_logic (e.g. "IF currency != 'EUR' /* ISO code */ THEN REJECT").

CRITICAL - JSON Logic string values must be bare strings. Do NOT wrap string values in extra quote characters inside JSON.
WRONG: {"!=": [{"var": "currency"}, "'EUR'"]}   ← 'EUR' has embedded single-quotes inside the JSON string
RIGHT: {"!=": [{"var": "currency"}, "EUR"]}      ← bare string, no extra quotes
The JSON format already represents the value as a string; adding surrounding apostrophes makes the comparison fail.

Example Main Logic JSON:
{"if": [{">": [{"var": "amount"}, 500]}, "ASK_FOR_APPROVAL", null]}
The else branch MUST always be null (never an outcome string). Only the matching branch returns an outcome.

Example Edge Case JSON (must return null if unaffected so evaluation can continue):
{"if": [{"!=": [{"var": "currency"}, "EUR"]}, "REJECT", null]}

Edge cases are isolated constraints or preconditions that apply before the main logic. Do not include normal logical checks as edge cases unless they denote invalid or separate error-causing conditions.
Output purely JSON conforming to the structural requirement."""

def _normalize_json_logic(logic, datapoint_names: set):
    """Fix two common LLM JSON Logic mistakes:
    1. {"var": X} where X is not a known datapoint variable -> treat X as a string literal.
       e.g. {"var": "EUR"} -> "EUR" when "EUR" is not in the datapoints list.
    2. String values wrapped in extra single quotes like "'EUR'" -> "EUR".
    """
    if isinstance(logic, str):
        if logic.startswith("'") and logic.endswith("'") and len(logic) > 2:
            return logic[1:-1]
        return logic
    elif isinstance(logic, dict):
        if "var" in logic and len(logic) == 1:
            var_name = logic["var"]
            if var_name not in datapoint_names:
                # Not a known variable — treat as string literal
                if isinstance(var_name, str) and var_name.startswith("'") and var_name.endswith("'"):
                    var_name = var_name[1:-1]
                return var_name
        return {k: _normalize_json_logic(v, datapoint_names) for k, v in logic.items()}
    elif isinstance(logic, list):
        return [_normalize_json_logic(item, datapoint_names) for item in logic]
    return logic


def _looks_like_schema_payload(parsed: dict) -> bool:
    return isinstance(parsed, dict) and "properties" in parsed and "required" in parsed


def _collect_datapoints_from_json_logic(logic, seen: set[str], ordered: list[str]):
    if isinstance(logic, dict):
        if "var" in logic and len(logic) == 1:
            var_name = logic["var"]
            if isinstance(var_name, str) and var_name and var_name not in seen:
                seen.add(var_name)
                ordered.append(var_name)
            elif isinstance(var_name, list) and var_name:
                candidate = var_name[0]
                if isinstance(candidate, str) and candidate and candidate not in seen:
                    seen.add(candidate)
                    ordered.append(candidate)
            return
        for value in logic.values():
            _collect_datapoints_from_json_logic(value, seen, ordered)
    elif isinstance(logic, list):
        for item in logic:
            _collect_datapoints_from_json_logic(item, seen, ordered)


def _extract_proposed_field(rule_logic: str) -> dict | None:
    """Try to derive a proposed new schema field from a failed rule_logic string.

    Scans the condition text for the first variable involved in a comparison
    and infers its type from the operator used.
    """
    condition_text = rule_logic.split("THEN", 1)[0]
    comparison_pattern = re.compile(
        r"\b([A-Za-z_][A-Za-z0-9_]*)\b\s*(>=|<=|!=|==|>|<)",
        re.IGNORECASE,
    )
    numeric_ops = {">=", "<=", ">", "<"}
    for match in comparison_pattern.finditer(condition_text):
        candidate = match.group(1)
        if candidate.upper() in ("IF", "THEN", "ELSE", "AND", "OR", "NOT"):
            continue
        field_type = "number" if match.group(2) in numeric_ops else "text"
        return {
            "name": candidate,
            "description": f"{field_type}",
            "type": field_type,
        }
    return None


def _find_candidate_fields(natural_language: str, schema: dict, top_n: int = 3) -> list[tuple[str, str]]:
    """Score every schema field by word-overlap with the natural language rule.

    Overlap is computed against both the field name tokens and the field
    description tokens.  Field-name matches count double because they carry a
    stronger semantic signal than description words.

    Returns a ranked list of ``(field_name, description)`` tuples, length at
    most *top_n*, with the best match first.  Fields with zero overlap are
    excluded so the hint list stays concise.
    """
    nl_words = set(re.findall(r'[a-z0-9]+', natural_language.lower()))
    scores: dict[str, int] = {}
    for field, description in schema.items():
        field_words = set(re.findall(r'[a-z0-9]+', field.lower()))
        desc_words = set(re.findall(r'[a-z0-9]+', str(description).lower()))
        overlap = len(nl_words & field_words) * 2 + len(nl_words & desc_words)
        if overlap > 0:
            scores[field] = overlap
    ranked = sorted(scores, key=lambda k: scores[k], reverse=True)[:top_n]
    return [(f, schema[f]) for f in ranked]


def _collect_datapoints_from_rule_text(rule_text: str, seen: set[str], ordered: list[str]):
    if not isinstance(rule_text, str):
        return

    condition_text = rule_text.split("THEN", 1)[0]
    comparison_pattern = re.compile(
        r"\b([A-Za-z_][A-Za-z0-9_]*)\b\s*(?:>=|<=|!=|==|=|>|<|\bIN\b|\bNOT\s+IN\b)",
        re.IGNORECASE,
    )
    for match in comparison_pattern.finditer(condition_text):
        candidate = match.group(1)
        if candidate.upper() == "IF" or candidate in seen:
            continue
        seen.add(candidate)
        ordered.append(candidate)


def _derive_datapoints(parsed: dict) -> list[str]:
    seen = set()
    ordered = []

    _collect_datapoints_from_json_logic(parsed.get("rule_logic_json", {}), seen, ordered)
    for edge_case_json in parsed.get("edge_cases_json", []):
        _collect_datapoints_from_json_logic(edge_case_json, seen, ordered)

    if ordered:
        return ordered

    _collect_datapoints_from_rule_text(parsed.get("rule_logic", ""), seen, ordered)
    for edge_case in parsed.get("edge_cases", []):
        _collect_datapoints_from_rule_text(edge_case, seen, ordered)
    return ordered


def _swap_var_in_json_logic(logic, old_var: str, new_var: str):
    """Recursively replace ``{"var": old_var}`` with ``{"var": new_var}``."""
    if isinstance(logic, dict):
        if "var" in logic and len(logic) == 1 and logic["var"] == old_var:
            return {"var": new_var}
        return {k: _swap_var_in_json_logic(v, old_var, new_var) for k, v in logic.items()}
    elif isinstance(logic, list):
        return [_swap_var_in_json_logic(item, old_var, new_var) for item in logic]
    return logic


def _replace_variable_token(text: str, old_var: str, new_var: str) -> str:
    """Replace all occurrences of *old_var* with *new_var* in *text* using
    word-boundary matching to avoid replacing substrings inside other variable
    names.

    Example: replacing "amount" in "transaction_amount > 100" leaves it unchanged,
    but "amount > 100 AND amount < 500" becomes "price > 100 AND price < 500".
    """
    # Escape special regex chars in variable names
    escaped_old = re.escape(old_var)
    # Use word boundaries (\b) to match only complete tokens
    pattern = r'\b' + escaped_old + r'\b'
    return re.sub(pattern, new_var, text)


def swap_variable_in_result(result: dict, old_var: str, new_var: str) -> dict:
    """Replace every occurrence of *old_var* with *new_var* throughout a
    translation result dict.

    Updates ``datapoints``, ``rule_logic`` (string), ``rule_logic_json``,
    ``edge_cases`` (strings) and ``edge_cases_json``.

    Uses token-aware replacement for strings to avoid replacing substrings
    inside other variable names (e.g., "amount" won't match "transaction_amount").

    Returns the mutated *result* for convenience.
    """
    result["datapoints"] = [
        new_var if dp == old_var else dp
        for dp in result.get("datapoints", [])
    ]

    if isinstance(result.get("rule_logic"), str):
        result["rule_logic"] = _replace_variable_token(
            result["rule_logic"], old_var, new_var
        )

    result["rule_logic_json"] = _swap_var_in_json_logic(
        result.get("rule_logic_json", {}), old_var, new_var,
    )

    result["edge_cases"] = [
        _replace_variable_token(ec, old_var, new_var) if isinstance(ec, str) else ec
        for ec in result.get("edge_cases", [])
    ]

    result["edge_cases_json"] = [
        _swap_var_in_json_logic(ec, old_var, new_var)
        for ec in result.get("edge_cases_json", [])
    ]

    return result


def _sanitize_datapoints_for_schema(result: dict, context_schema: dict | None) -> dict:
    if not context_schema:
        return result

    allowed_datapoints = set(context_schema.keys())
    sanitized = [dp for dp in result.get("datapoints", []) if dp in allowed_datapoints]
    if sanitized:
        result["datapoints"] = sanitized
        return result

    derived = [dp for dp in _derive_datapoints(result) if dp in allowed_datapoints]
    result["datapoints"] = derived
    return result


def _validate_schema_variables(result: dict, context_schema: dict | None) -> None:
    """Deterministic post-translation guard.

    Verifies that every variable referenced in ``rule_logic_json`` and
    ``edge_cases_json`` is present in *context_schema*.  Raises
    :class:`SchemaConceptMismatchError` on the first offender.

    When *context_schema* is ``None`` or empty the check is skipped so that
    schema-free translations are unaffected.
    """
    if not context_schema:
        return

    allowed = set(context_schema.keys())
    seen: set[str] = set()
    ordered: list[str] = []
    _collect_datapoints_from_json_logic(result.get("rule_logic_json", {}), seen, ordered)
    for ec in result.get("edge_cases_json", []):
        _collect_datapoints_from_json_logic(ec, seen, ordered)

    for var in ordered:
        if var not in allowed:
            raise SchemaConceptMismatchError(
                f"Variable '{var}' is not defined in the selected schema. "
                f"The model mapped your concept to a field that does not exist "
                f"in this schema. Please rephrase your rule or choose a different schema."
            )


def _detect_unsupported_sentinel(result: dict) -> None:
    """Raises :class:`SchemaConceptMismatchError` when the LLM could not map
    the requested concept to any schema field and signalled this by prefixing
    ``rule_logic`` with ``UNSUPPORTED:``."""
    rule_logic = result.get("rule_logic", "")
    if isinstance(rule_logic, str) and rule_logic.strip().upper().startswith("UNSUPPORTED:"):
        raise SchemaConceptMismatchError(
            f"The requested concept is not supported by the selected schema. "
            f"Model message: {rule_logic.strip()}"
        )


def _validate_candidate_alignment(
    result: dict,
    natural_language: str,
    context_schema: dict | None,
) -> None:
    """Reject translations where the LLM picked a semantically poor field
    while a much better candidate exists in the schema.

    For every variable used in ``rule_logic_json`` we compute the same
    word-overlap score that :func:`_find_candidate_fields` uses.  If a used
    variable scores below half the best available score the translation is
    rejected via :class:`SchemaConceptMismatchError`, pointing the user at the
    better field.

    Skipped when *context_schema* is ``None`` / empty or when all scores are
    zero (meaning the rule text has no vocabulary overlap with any field).
    """
    if not context_schema:
        return

    nl_words = set(re.findall(r'[a-z0-9]+', natural_language.lower()))

    # Score every schema field.
    scores: dict[str, int] = {}
    for field, description in context_schema.items():
        field_words = set(re.findall(r'[a-z0-9]+', field.lower()))
        desc_words = set(re.findall(r'[a-z0-9]+', str(description).lower()))
        scores[field] = len(nl_words & field_words) * 2 + len(nl_words & desc_words)

    top_score = max(scores.values()) if scores else 0
    if top_score == 0:
        return

    # Collect variables from main rule logic only (edge cases may reference
    # unrelated concepts and are validated separately by _validate_schema_variables).
    used_vars: set[str] = set()
    ordered: list[str] = []
    _collect_datapoints_from_json_logic(
        result.get("rule_logic_json", {}), used_vars, ordered,
    )

    threshold = top_score * 0.5
    best_field = max(scores, key=lambda k: scores[k])
    for var in ordered:
        var_score = scores.get(var, 0)
        if var_score < threshold:
            best_desc = context_schema.get(best_field, "")
            # Infer type from operator in rule_logic
            rule_logic_str = result.get("rule_logic", "")
            inferred_type = (
                "number"
                if any(op in str(rule_logic_str) for op in [">", "<", ">=", "<="])
                else "text"
            )
            raise SchemaConceptMismatchError(
                f"The translator picked '{var}' but '{best_field}' is a much "
                f"better semantic match for this rule. "
                f"'{var}' means \"{context_schema.get(var, '?')}\" while your "
                f"rule is about \"{best_desc}\".",
                proposed_field={
                    "name": best_field,
                    "description": best_desc,
                    "type": inferred_type,
                },
            )


def _validate_rule_logic_json_populated(result: dict, context_schema: dict | None) -> None:
    """When a schema is active and the rule text contains a condition, the
    ``rule_logic_json`` must not be empty.

    An empty ``rule_logic_json`` combined with a non-trivial rule string means
    the LLM could not map any concept to a schema field.  That is a concept
    mismatch, not a valid rule.
    """
    if not context_schema:
        return
    rule_logic = result.get("rule_logic", "")
    has_condition = (
        isinstance(rule_logic, str)
        and "IF" in rule_logic.upper()
        and "THEN" in rule_logic.upper()
    )
    if has_condition and not result.get("rule_logic_json"):
        proposed_field = _extract_proposed_field(rule_logic)
        raise SchemaConceptMismatchError(
            "The rule concept does not map to any field in the selected schema. "
            "Please rephrase your rule using terms that match the schema field descriptions, "
            "or add this concept as a new schema field.",
            proposed_field=proposed_field,
        )


def _sanitize_datapoints_without_schema(result: dict) -> dict:
    sanitized = []
    seen = set()
    for datapoint in result.get("datapoints", []):
        if not isinstance(datapoint, str):
            continue
        normalized = datapoint.strip()
        if not normalized or normalized.lower() in PSEUDO_DATAPOINT_TOKENS or normalized in seen:
            continue
        seen.add(normalized)
        sanitized.append(normalized)

    if sanitized:
        result["datapoints"] = sanitized
        return result

    derived = []
    for datapoint in _derive_datapoints(result):
        if datapoint.lower() in PSEUDO_DATAPOINT_TOKENS or datapoint in derived:
            continue
        derived.append(datapoint)
    result["datapoints"] = derived
    return result


def _validate_rule_payload(parsed: dict) -> dict:
    parsed.setdefault("edge_cases", [])
    parsed.setdefault("edge_cases_json", [])
    parsed.setdefault("rule_logic_json", {})
    if not parsed.get("datapoints"):
        parsed["datapoints"] = _derive_datapoints(parsed)

    # Filter out null-checking edge cases generated by strict LLMs.
    # Some providers return edge-case strings without JSON siblings, so pad
    # missing entries with empty dicts instead of dropping the rule text.
    filtered_ec_str = []
    filtered_ec_json = []
    for index, ec_str in enumerate(parsed.get("edge_cases", [])):
        ec_json = parsed.get("edge_cases_json", [])
        ec_logic = ec_json[index] if index < len(ec_json) else {}
        if isinstance(ec_str, str):
            normalized_edge_case = ec_str.lower()
            if "null" in normalized_edge_case or "invalid" in normalized_edge_case:
                continue
        filtered_ec_str.append(ec_str)
        filtered_ec_json.append(ec_logic)

    parsed["edge_cases"] = filtered_ec_str
    parsed["edge_cases_json"] = filtered_ec_json
    return RuleLogicDefinition(**parsed).model_dump()

def check_llm_connection(provider: str, model: str, api_key: str) -> bool:
    """Smoke test to verify API keys for the selected provider."""
    try:
        if provider == "openai":
            client = openai.OpenAI(api_key=api_key)
            client.models.retrieve(model) # Basic auth check
            return True
        elif provider == "anthropic":
            client = anthropic.Anthropic(api_key=api_key)
            # Anthropic doesn't have a simple auth check endpoint, so we do a tiny completion
            client.messages.create(
                model=model,
                max_tokens=1,
                messages=[{"role": "user", "content": "Hi"}]
            )
            return True
        elif provider == "gemini":
            client = genai.Client(api_key=api_key)
            client.models.get(name=f"models/{model}")
            return True
        return False
    except Exception as e:
        print(f"\n[!] Error connecting to {provider}: {e}")
        return False

def translate_rule(natural_language: str, feature: str, name: str, provider: str, model: str, api_key: str, context_schema: dict = None, datapoint_definitions: list = None) -> dict:
    """Calls the specified LLM to translate natural language into structured logic."""
    prompt = f"Rule Name: {name}\nFeature: {feature}\nNatural Language Rule: {natural_language}"

    active_sys_prompt = SYS_PROMPT
    if context_schema:
        schema_field_lines = "\n".join(
            f"  - {field}: {description}" for field, description in context_schema.items()
        )
        candidates = _find_candidate_fields(natural_language, context_schema)
        if candidates:
            candidate_lines = "\n".join(
                f"  {i+1}. {field} — {desc}" for i, (field, desc) in enumerate(candidates)
            )
            candidate_block = (
                f"\nMost likely matching fields for this rule (ranked by relevance):\n"
                f"{candidate_lines}\n\n"
                f"Pick from the ranked list first. "
                f"If none semantically fits, pick the best field from the full list below."
            )
        else:
            candidate_block = (
                "\nNo schema field appears to share vocabulary with this rule. "
                "Review the full list below carefully and pick the field whose "
                "description best matches the concept. "
                "If truly none match, set rule_logic_json to {{}} and leave datapoints empty."
            )
        active_sys_prompt += f"""

CRITICAL SCHEMA ENFORCEMENT — THIS OVERRIDES ALL EARLIER VARIABLE NAMING INSTRUCTIONS:
Use ONLY the schema field names listed below. Variable names the user typed are a concept
hint only — you MUST output the exact schema field name, not the user's wording.{candidate_block}

Do NOT use a field whose description covers a completely different concept (e.g. do not use
`account_age_days` for a rule about delivery duration — those describe unrelated things).

All allowed schema fields:
{schema_field_lines}"""

    if datapoint_definitions:
        lines = []
        for dp in datapoint_definitions:
            dp_type = dp.get('type', 'text')
            if dp_type == 'enum' and dp.get('values'):
                values_str = ', '.join(f'"{v}"' for v in dp['values'])
                lines.append(f"- {dp['name']} (enum): {values_str}")
            else:
                lines.append(f"- {dp['name']} ({dp_type}): {dp_type}")
        preface = "Known datapoints (use ONLY these exact values in string comparisons):\n"
        if not context_schema:
            preface += "Prefer reusing these exact datapoint names when they fit the rule. If none fit, create one new concrete snake_case business field.\n"
        prompt = preface + "\n".join(lines) + "\n\n" + prompt

    # Handle OpenAI
    if provider == "openai":
        client = openai.OpenAI(api_key=api_key)
        schema_json = RuleLogicDefinition.model_json_schema()
        system_content = f"{active_sys_prompt}\n\nStrictly format your response to match this JSON schema:\n{json.dumps(schema_json)}"
        retry_instruction = (
            "You returned the JSON schema definition or another invalid payload. "
            "Return one concrete rule instance only. Do not return the schema, "
            "field descriptions, or property definitions."
        )
        attempt_messages = [
            [
                {"role": "system", "content": system_content},
                {"role": "user", "content": prompt},
            ],
            [
                {"role": "system", "content": system_content},
                {"role": "user", "content": prompt},
                {"role": "assistant", "content": json.dumps(schema_json)},
                {"role": "user", "content": retry_instruction},
            ],
        ]
        last_error = None
        result = None
        for messages in attempt_messages:
            response = client.chat.completions.create(
                model=model,
                messages=messages,
                response_format={"type": "json_object"},
            )
            parsed = json.loads(response.choices[0].message.content)
            try:
                result = _validate_rule_payload(parsed)
                break
            except ValidationError as exc:
                last_error = exc
                if not _looks_like_schema_payload(parsed):
                    raise
        if result is None:
            raise last_error

    # Handle Anthropic
    elif provider == "anthropic":
        client = anthropic.Anthropic(api_key=api_key)
        schema = RuleLogicDefinition.model_json_schema()
        response = client.messages.create(
            model=model,
            max_tokens=1024,
            system=active_sys_prompt,
            messages=[{"role": "user", "content": prompt}],
            tools=[{
                "name": "submit_rule",
                "description": "Submit the parsed rule.",
                "input_schema": schema
            }],
            tool_choice={"type": "tool", "name": "submit_rule"}
        )
        parsed = None
        for block in response.content:
            if block.type == "tool_use" and block.name == "submit_rule":
                parsed = dict(block.input)
                break
        if parsed is None:
            raise ValueError("Anthropic did not return the expected tool use data.")

    # Handle Gemini
    elif provider == "gemini":
        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model=model,
            contents=f"{active_sys_prompt}\n\nTask:\n{prompt}",
            config=genai.types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=RuleLogicDefinition,
            )
        )
        parsed = json.loads(response.text)

    else:
        raise ValueError(f"Unknown provider: {provider}")

    if provider != "openai":
        result = _validate_rule_payload(parsed)

    if context_schema:
        result = _sanitize_datapoints_for_schema(result, context_schema)
    else:
        result = _sanitize_datapoints_without_schema(result)

    # Deterministic guards (schema mode only).
    if context_schema:
        _validate_rule_logic_json_populated(result, context_schema)
        _validate_candidate_alignment(result, natural_language, context_schema)
        _validate_schema_variables(result, context_schema)

    # Post-process: fix {"var": X} -> X when X is not a known datapoint variable,
    # and strip embedded single quotes from string comparison values.
    datapoint_names = set(result.get("datapoints", []))
    result["rule_logic_json"] = _normalize_json_logic(result.get("rule_logic_json", {}), datapoint_names)
    result["edge_cases_json"] = [
        _normalize_json_logic(ec, datapoint_names) for ec in result.get("edge_cases_json", [])
    ]
    return result
