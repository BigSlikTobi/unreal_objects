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
    rule_logic_json: dict = Field(..., description="The main logic parsed into standard JSON Logic format. E.g.: {'if': [{'>': [{'var': 'billing_amount'}, 100]}, 'ASK_FOR_APPROVAL', 'APPROVE']}")

SYS_PROMPT = """You are an expert business logic rule translator for the 'Decision Center'.
Your job is to translate a given natural language prompt detailing a business rule into strictly structured data containing datapoints, edge cases, and the logical formula.

You must provide BOTH a human-readable string representation (`rule_logic`, `edge_cases`) AND a deterministic JSON Logic representation (`rule_logic_json`, `edge_cases_json`).

Human Readable format: `IF <conditions> THEN <outcome>`
JSON Logic format: Must strictly follow jsonlogic.com specs and evaluate to an outcome string ("APPROVE", "REJECT", "ASK_FOR_APPROVAL") or null.
Note: For equality checking in JSON Logic use `"=="` instead of `"="`.

Example Main Logic JSON:
{"if": [{">": [{"var": "amount"}, 500]}, "ASK_FOR_APPROVAL", "APPROVE"]}

Example Edge Case JSON (must return null if unaffected so evaluation can continue): 
{"if": [{"!=": [{"var": "currency"}, "eur"]}, "REJECT", null]}

Edge cases are isolated constraints or preconditions that apply before the main logic. Do not include normal logical checks as edge cases unless they denote invalid or separate error-causing conditions.
Output purely JSON conforming to the structural requirement."""

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

def translate_rule(natural_language: str, feature: str, name: str, provider: str, model: str, api_key: str) -> dict:
    """Calls the specified LLM to translate natural language into structured logic."""
    prompt = f"Rule Name: {name}\nFeature: {feature}\nNatural Language Rule: {natural_language}"

    # Handle OpenAI
    if provider == "openai":
        client = openai.OpenAI(api_key=api_key)
        response = client.beta.chat.completions.parse(
            model=model,
            messages=[
                {"role": "system", "content": SYS_PROMPT},
                {"role": "user", "content": prompt}
            ],
            response_format=RuleLogicDefinition,
        )
        return response.choices[0].message.parsed.model_dump()

    # Handle Anthropic
    elif provider == "anthropic":
        client = anthropic.Anthropic(api_key=api_key)
        # Anthropic Tool Use for structured output
        schema = RuleLogicDefinition.model_json_schema()
        response = client.messages.create(
            model=model,
            max_tokens=1024,
            system=SYS_PROMPT,
            messages=[{"role": "user", "content": prompt}],
            tools=[{
                "name": "submit_rule",
                "description": "Submit the parsed rule.",
                "input_schema": schema
            }],
            tool_choice={"type": "tool", "name": "submit_rule"}
        )
        for block in response.content:
            if block.type == "tool_use" and block.name == "submit_rule":
                return block.input
        raise ValueError("Anthropic did not return the expected tool use data.")

    # Handle Gemini
    elif provider == "gemini":
        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model=model,
            contents=f"{SYS_PROMPT}\n\nTask:\n{prompt}",
            config=genai.types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=RuleLogicDefinition,
            )
        )
        return json.loads(response.text)

    else:
        raise ValueError(f"Unknown provider: {provider}")
