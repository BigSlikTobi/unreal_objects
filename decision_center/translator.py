import json
from pydantic import BaseModel, Field
import openai
import anthropic
from google import genai

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
        active_sys_prompt += f"\n\nCRITICAL SCHEMA ENFORCEMENT:\nYou MUST strictly use the variable names provided in the following JSON schema. Do not invent any names not present in this dictionary.\nSchema:\n{json.dumps(context_schema)}"

    if datapoint_definitions:
        lines = []
        for dp in datapoint_definitions:
            dp_type = dp.get('type', 'text')
            if dp_type == 'enum' and dp.get('values'):
                values_str = ', '.join(f'"{v}"' for v in dp['values'])
                lines.append(f"- {dp['name']} (enum): {values_str}")
            else:
                lines.append(f"- {dp['name']} ({dp_type}): {dp_type}")
        prompt = "Known datapoints (use ONLY these exact values in string comparisons):\n" + "\n".join(lines) + "\n\n" + prompt

    # Handle OpenAI
    if provider == "openai":
        client = openai.OpenAI(api_key=api_key)
        schema_json = RuleLogicDefinition.model_json_schema()
        system_content = f"{active_sys_prompt}\n\nStrictly format your response to match this JSON schema:\n{json.dumps(schema_json)}"

        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_content},
                {"role": "user", "content": prompt}
            ],
            response_format={"type": "json_object"},
        )
        parsed = json.loads(response.choices[0].message.content)

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

    # Filter out null-checking edge cases generated by strict LLMs.
    # zip() pairs each string with its corresponding JSON, so a filtered-out
    # string automatically drops its JSON counterpart — no index arithmetic needed.
    filtered_ec_str = []
    filtered_ec_json = []
    for ec_str, ec_json in zip(parsed.get("edge_cases", []), parsed.get("edge_cases_json", [])):
        if "null" not in ec_str.lower() and "invalid" not in ec_str.lower():
            filtered_ec_str.append(ec_str)
            filtered_ec_json.append(ec_json)

    parsed["edge_cases"] = filtered_ec_str
    parsed["edge_cases_json"] = filtered_ec_json

    result = RuleLogicDefinition(**parsed).model_dump()

    # Post-process: fix {"var": X} -> X when X is not a known datapoint variable,
    # and strip embedded single quotes from string comparison values.
    datapoint_names = set(result.get("datapoints", []))
    result["rule_logic_json"] = _normalize_json_logic(result.get("rule_logic_json", {}), datapoint_names)
    result["edge_cases_json"] = [
        _normalize_json_logic(ec, datapoint_names) for ec in result.get("edge_cases_json", [])
    ]
    return result
