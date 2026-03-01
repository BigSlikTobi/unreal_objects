import asyncio
import json
import os

import openai

from decision_center.stress_test.models import StressTestCase


DATASET_SYS_PROMPT = """You are generating a dataset to test a Business Rule Engine.
Generate a batch of varied, highly-realistic business rules. Include a healthy mix of:
1. Simple threshold rules
2. Complex multi-condition rules
3. Edge cases disguised as main rules.

CRITICAL INSTRUCTION FOR VARIABLES:
Later, another LLM will blindly translate your `natural_language_rule` into strict JSON Logic.
You MUST use the exact same snake_case variable names in your `context_data` keys that you
explicitly write in the `natural_language_rule`.

For each rule, provide a specific `context_data` payload that explicitly triggers that rule to
reach the `expected_outcome`.

Output carefully formatted JSON matching the schema."""


def build_dataset_system_prompt(schema_dict: dict | None) -> str:
    prompt = DATASET_SYS_PROMPT
    if schema_dict:
        prompt += (
            "\n\nCRITICAL SCHEMA ENFORCEMENT:\n"
            "You MUST strictly use the variable names provided in the following JSON schema. "
            "Do not invent any names not present in this dictionary.\n"
            f"Schema:\n{json.dumps(schema_dict)}"
        )
    return prompt


async def _generate_batch(client, model_name: str, system_content: str, batch_size: int) -> list[dict]:
    response = await client.chat.completions.create(
        model=model_name,
        messages=[
            {"role": "system", "content": system_content},
            {"role": "user", "content": f"Generate {batch_size} rules now."},
        ],
        response_format={"type": "json_object"},
    )
    payload = json.loads(response.choices[0].message.content)
    return payload.get("test_cases", [])


async def generate_dataset(
    output_path,
    schema_dict: dict | None,
    *,
    model_name: str | None = None,
    api_key: str | None = None,
    batch_count: int = 10,
    batch_size: int = 50,
) -> list[dict]:
    api_key = api_key or os.environ.get("OPENAI_API_KEY") or os.environ.get("OPEN_AI_KEY")
    model_name = model_name or os.environ.get("GPT_MODEL", "gpt-5-mini-2025-08-07")
    if not api_key:
        raise ValueError("OPENAI_API_KEY environment variable not set")

    schema_json = {
        "type": "object",
        "properties": {
            "test_cases": {
                "type": "array",
                "items": StressTestCase.model_json_schema(),
            }
        },
        "required": ["test_cases"],
    }
    system_content = (
        build_dataset_system_prompt(schema_dict)
        + f"\n\nStrictly format your response to match this JSON schema:\n{json.dumps(schema_json)}"
    )
    client = openai.AsyncOpenAI(api_key=api_key)

    tasks = [
        _generate_batch(client, model_name, system_content, batch_size)
        for _ in range(batch_count)
    ]
    results = await asyncio.gather(*tasks)
    all_cases = [case for batch in results for case in batch]
    output_path.write_text(json.dumps(all_cases, indent=2))
    return all_cases
