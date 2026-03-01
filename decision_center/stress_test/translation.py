import json
import os

from decision_center.translator import SYS_PROMPT as TRANSLATOR_SYS_PROMPT
from decision_center.translator import translate_rule


SCHEMA = {
    "properties": {
        "datapoints": {"items": {"type": "string"}, "type": "array"},
        "edge_cases": {"items": {"type": "string"}, "type": "array"},
        "edge_cases_json": {"items": {"type": "object"}, "type": "array"},
        "rule_logic": {"type": "string"},
        "rule_logic_json": {"type": "object"},
    },
    "required": ["datapoints", "rule_logic", "rule_logic_json"],
    "type": "object",
}


def build_translation_system_prompt(schema_dict: dict | None) -> str:
    prompt = TRANSLATOR_SYS_PROMPT
    if schema_dict:
        prompt += (
            "\n\nCRITICAL SCHEMA ENFORCEMENT:\n"
            "You MUST strictly use the variable names provided in the following JSON schema. "
            "Do not invent any names not present in this dictionary.\n"
            f"Schema:\n{json.dumps(schema_dict)}"
        )
    return prompt + f"\n\nStrictly format your response to match this JSON schema:\n{json.dumps(SCHEMA)}"


def translate_cases(
    test_cases: list[dict],
    output_path,
    *,
    provider: str = "openai",
    model: str | None = None,
    api_key: str | None = None,
    schema_dict: dict | None = None,
) -> list[dict]:
    model = model or os.environ.get("GPT_MODEL", "gpt-5-mini-2025-08-07")
    api_key = api_key or os.environ.get(f"{provider.upper()}_API_KEY") or os.environ.get("OPEN_AI_KEY")
    if not api_key:
        raise ValueError(f"{provider.upper()}_API_KEY environment variable not set")

    results = []
    for index, case in enumerate(test_cases):
        try:
            translated = translate_rule(
                natural_language=case["natural_language_rule"],
                feature="e2e_feature",
                name=f"E2E Rule {index}",
                provider=provider,
                model=model,
                api_key=api_key,
                context_schema=schema_dict,
            )
            results.append(
                {
                    "custom_id": f"request-{index}",
                    "response": {
                        "body": {
                            "choices": [
                                {
                                    "message": {
                                        "content": json.dumps(translated)
                                    }
                                }
                            ]
                        }
                    },
                }
            )
        except Exception as exc:
            print(f"⚠️ Translation failed for request-{index}: {exc}")

    output_path.write_text("\n".join(json.dumps(result) for result in results) + ("\n" if results else ""))
    return results
