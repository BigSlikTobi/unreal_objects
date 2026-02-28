import json
import os
import asyncio
from dotenv import load_dotenv
import openai
from pydantic import BaseModel

load_dotenv()

SYS_PROMPT = """You are an expert business logic rule translator for the 'Decision Center'.
Your job is to translate a given natural language prompt detailing a business rule into strictly structured data containing datapoints, edge cases, and the logical formula.

You must provide BOTH a human-readable string representation (`rule_logic`, `edge_cases`) AND a deterministic JSON Logic representation (`rule_logic_json`, `edge_cases_json`).

Human Readable format: `IF <conditions> THEN <outcome>`
JSON Logic format: Must strictly follow jsonlogic.com specs and evaluate to an outcome string ("APPROVE", "REJECT", "ASK_FOR_APPROVAL") or null.
Note: For equality checking in JSON Logic use `"=="` instead of `"="`.

CRITICAL VARIABLE INSTRUCTION:
You MUST use the exact variable names that are explicitly mentioned in the natural language rule. For example, if the rule says "transaction_amount > 500", your JSON Logic must use `{"var": "transaction_amount"}`. DO NOT invent, normalize, or alter the variable names unless strictly necessary. If a variable is written in snake_case in the text, extract it verbatim.

Example Main Logic JSON:
{"if": [{">": [{"var": "amount"}, 500]}, "ASK_FOR_APPROVAL", null]}
The else branch MUST always be null (never an outcome string). Only the matching branch returns an outcome.

Example Edge Case JSON (must return null if unaffected so evaluation can continue): 
{"if": [{"!=": [{"var": "currency"}, "eur"]}, "REJECT", null]}

Edge cases are isolated constraints or preconditions that apply before the main logic. Do not include normal logical checks as edge cases unless they denote invalid or separate error-causing conditions.
Output purely JSON conforming to the structural requirement."""

# Minimal schema extraction just for the system prompt formatting
SCHEMA = {
  "properties": {
    "datapoints": {"items": {"type": "string"}, "type": "array"},
    "edge_cases": {"items": {"type": "string"}, "type": "array"},
    "edge_cases_json": {"items": {"type": "object"}, "type": "array"},
    "rule_logic": {"type": "string"},
    "rule_logic_json": {"type": "object"}
  },
  "required": ["datapoints", "rule_logic", "rule_logic_json"],
  "type": "object"
}

async def process_case(client, model_name, system_content, i, case, sem):
    async with sem:
        nl_rule = case["natural_language_rule"]
        prompt = f"Rule Name: E2E Rule {i}\nFeature: e2e_feature\nNatural Language Rule: {nl_rule}"
        
        try:
            response = await client.chat.completions.create(
                model=model_name,
                messages=[
                    {"role": "system", "content": system_content},
                    {"role": "user", "content": prompt}
                ],
                response_format={"type": "json_object"}
            )
            parsed = json.loads(response.choices[0].message.content)

            filtered_ec_str = []
            filtered_ec_json = []
            ec_list = parsed.get("edge_cases") or []
            ec_json_list = parsed.get("edge_cases_json") or []
            
            for ec_idx, ec_str in enumerate(ec_list):
                if "null" not in ec_str.lower() and "invalid" not in ec_str.lower():
                    filtered_ec_str.append(ec_str)
                    if ec_idx < len(ec_json_list):
                        filtered_ec_json.append(ec_json_list[ec_idx])
            parsed["edge_cases"] = filtered_ec_str
            parsed["edge_cases_json"] = filtered_ec_json
            
            return {
                "custom_id": f"request-{i}",
                "response": {
                    "body": {
                        "choices": [
                            {
                                "message": {
                                    "content": json.dumps(parsed)
                                }
                            }
                        ]
                    }
                }
            }
        except Exception as e:
            print(f"Error on request {i}: {e}")
            return None

async def create_sync():
    api_key = os.environ.get("OPENAI_API_KEY") or os.environ.get("OPEN_AI_KEY")
    model_name = os.environ.get("GPT_MODEL", "gpt-5-mini-2025-08-07")
    
    if not api_key:
        print("❌ Error: OPENAI_API_KEY environment variable not set in .env")
        return
        
    client = openai.AsyncOpenAI(api_key=api_key)
    
    with open("scripts/stress_test/llm_test_dataset.json", "r") as f:
        test_cases = json.load(f)
        
    print(f"📦 Generating {len(test_cases)} translations concurrently...")
    
    with open("schemas/ecommerce.json", "r") as f:
        ecommerce_schema = json.load(f)["schema"]
    
    active_sys_prompt = SYS_PROMPT + f"\n\nCRITICAL SCHEMA ENFORCEMENT:\nYou MUST strictly use the variable names provided in the following JSON schema. Do not invent any names not present in this dictionary.\nSchema:\n{json.dumps(ecommerce_schema)}"
    
    system_content = f"{active_sys_prompt}\n\nStrictly format your response to match this JSON schema:\n{json.dumps(SCHEMA)}"
    
    sem = asyncio.Semaphore(50)  # Max 50 concurrent requests
    
    tasks = [process_case(client, model_name, system_content, i, case, sem) for i, case in enumerate(test_cases)]
    results = await asyncio.gather(*tasks)
    
    jsonl_path = "scripts/stress_test/batch_results.jsonl"
    with open(jsonl_path, "w") as f:
        for res in results:
            if res:
                f.write(json.dumps(res) + "\n")
            
    print(f"✅ Generated {jsonl_path} directly without Batch API!")
    print("\nNext step: Run `python3 scripts/stress_test/batch_3_evaluate.py` to evaluate.")

if __name__ == "__main__":
    asyncio.run(create_sync())
