import json
import os
import re

from pydantic import BaseModel

try:
    import openai
except ImportError:
    openai = None

try:
    import anthropic
except ImportError:
    anthropic = None

try:
    from google import genai
    import google.generativeai.types as genai_types
except ImportError:
    try:
        import google.generativeai as genai
    except ImportError:
        genai = None

from .models import SchemaField

DEFAULT_SCHEMAS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "schemas"))

SCHEMA_GENERATION_SYS_PROMPT = """You are a domain schema assistant. Your job is to propose a structured field schema for a given business domain.

Rules:
- All field names MUST be snake_case (e.g. order_amount, customer_age_days)
- Types MUST be one of: "number", "string", "boolean"
- Do NOT include meta-fields like id, timestamp, created_at, updated_at
- Always return the FULL field list every turn (do not omit previously agreed fields)
- Keep descriptions concise (one short phrase) and business-focused
- Aim for 10–25 fields that cover the most important business concepts for the domain
- Reply in the "message" field with 1–3 sentences summarizing what you added, changed, or kept the same"""


class SchemaProposal(BaseModel):
    name: str
    description: str
    fields: list[SchemaField]
    message: str = ""


def generate_schema(
    user_message: str,
    conversation_history: list[dict],
    current_schema: dict | None,
    provider: str,
    model: str,
    api_key: str,
) -> SchemaProposal:
    """Call the specified LLM to generate or refine a domain schema."""
    # Trim history to last 20 entries to avoid token bloat
    history = list(conversation_history[-20:])

    prompt = user_message
    if current_schema:
        field_lines = "\n".join(
            f"  - {k}: {v}" for k, v in current_schema.items()
        )
        prompt += f"\n\nCurrent schema fields for reference:\n{field_lines}"

    if provider == "openai":
        if openai is None:
            raise ImportError("openai package not installed")
        client = openai.OpenAI(api_key=api_key)
        schema_json = SchemaProposal.model_json_schema()
        system_content = f"{SCHEMA_GENERATION_SYS_PROMPT}\n\nStrictly format your response to match this JSON schema:\n{json.dumps(schema_json)}"
        messages = [{"role": "system", "content": system_content}]
        messages.extend(history)
        messages.append({"role": "user", "content": prompt})
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            response_format={"type": "json_object"},
        )
        parsed = json.loads(response.choices[0].message.content)

    elif provider == "anthropic":
        if anthropic is None:
            raise ImportError("anthropic package not installed")
        client = anthropic.Anthropic(api_key=api_key)
        schema = SchemaProposal.model_json_schema()
        ant_messages = list(history)
        ant_messages.append({"role": "user", "content": prompt})
        response = client.messages.create(
            model=model,
            max_tokens=2048,
            system=SCHEMA_GENERATION_SYS_PROMPT,
            messages=ant_messages,
            tools=[{
                "name": "submit_schema",
                "description": "Submit the proposed domain schema.",
                "input_schema": schema,
            }],
            tool_choice={"type": "tool", "name": "submit_schema"},
        )
        parsed = None
        for block in response.content:
            if block.type == "tool_use" and block.name == "submit_schema":
                parsed = dict(block.input)
                break
        if parsed is None:
            raise ValueError("Anthropic did not return the expected tool use data.")

    elif provider == "gemini":
        if genai is None:
            raise ImportError("google-generativeai package not installed")
        client = genai.Client(api_key=api_key)
        full_prompt = SCHEMA_GENERATION_SYS_PROMPT + "\n\nTask:\n" + prompt
        response = client.models.generate_content(
            model=model,
            contents=full_prompt,
            config=genai.types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=SchemaProposal,
            ),
        )
        parsed = json.loads(response.text)

    else:
        raise ValueError(f"Unknown provider: {provider}")

    # Ensure message field has a default
    if "message" not in parsed:
        parsed["message"] = ""

    return SchemaProposal(**parsed)


def convert_to_canonical_schema(proposal: SchemaProposal) -> dict:
    """Convert a SchemaProposal to the canonical {name: "type (description)"} format."""
    return {f.name: f"{f.type} ({f.description})" for f in proposal.fields}


def save_schema(proposal: SchemaProposal, schemas_dir: str = DEFAULT_SCHEMAS_DIR) -> str:
    """Persist a SchemaProposal as a JSON file in the schemas directory."""
    os.makedirs(schemas_dir, exist_ok=True)

    # Normalize name to safe filename
    name = proposal.name.lower().replace(" ", "_").replace("-", "_")
    name = re.sub(r"[^a-z0-9_]", "", name)
    if not name:
        name = "custom_schema"

    data = {
        "name": proposal.name,
        "description": proposal.description,
        "schema": convert_to_canonical_schema(proposal),
    }

    path = os.path.join(schemas_dir, f"{name}.json")
    with open(path, "w") as f:
        json.dump(data, f, indent=2)

    return os.path.abspath(path)
