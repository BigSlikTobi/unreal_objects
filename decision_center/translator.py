import json
from pydantic import BaseModel, Field
import openai
import anthropic
from google import genai

class RuleLogicDefinition(BaseModel):
    datapoints: list[str] = Field(..., description="A list of specific datapoints extracted from the natural language rule. Normalize variables into snake_case.")
    rule_logic: str = Field(..., description="The logic represented in the format: IF <condition> THEN <outcome>. E.g.: IF billing_amount > 100 THEN ASK_FOR_APPROVAL")

SYS_PROMPT = """You are an expert business logic rule translator for the 'Decision Center'.
Your job is to translate a given natural language prompt detailing a business rule into strictly structured data containing datapoints and the logical formula.
The logical formula must strictly use the structure `IF <conditions> THEN <outcome>`, allowing AND/OR for multiple conditions.
Possible outcomes are typically APPROVE, REJECT, or ASK_FOR_APPROVAL based on the context.
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
