import json
import asyncio
import os
from pydantic import BaseModel, Field
import openai
from dotenv import load_dotenv

load_dotenv()

class LLMTestCase(BaseModel):
    natural_language_rule: str = Field(description="A human-readable business rule written in English. MUST explicitly include the exact snake_case variable names found in context_data. E.g., 'Reject the transaction if the transaction_amount is greater than 5000 and the user_risk_score is above 80.'")
    context_data: dict = Field(description="A sample JSON dictionary. Keys MUST exactly match the explicitly named snake_case variables in the natural_language_rule. E.g., {'transaction_amount': 6000, 'user_risk_score': 85}")
    expected_outcome: str = Field(description="The deterministic decision this rule and context should produce. Must be exactly 'APPROVE', 'REJECT', or 'ASK_FOR_APPROVAL'.")

class LLMTestCaseBatch(BaseModel):
    test_cases: list[LLMTestCase]

SYS_PROMPT = """You are generating a dataset to test a Business Rule Engine.
Generate a batch of 50 varied, highly-realistic business rules. Include a healthy mix of:
1. Simple threshold rules (e.g. transaction_amount > 100 -> ASK_FOR_APPROVAL)
2. Complex multi-condition rules (e.g. if category is electronics AND risk_score > 50 -> REJECT)
3. Edge cases disguised as main rules.

CRITICAL INSTRUCTION FOR VARIABLES:
Later, another LLM will blindly translate your `natural_language_rule` into strict JSON Logic. To ensure the evaluation succeeds, you MUST use the exact same snake_case variable names in your `context_data` keys that you explicitly write in the `natural_language_rule`. 
For example, if your context data has `{"transaction_amount": 500}`, your natural language rule *must* say "If the transaction_amount is greater than..." (using the exact snake_case variable name). Do not use generic terms like "amount" in the English rule if the JSON key is "transaction_amount".

For each rule, provide a specific `context_data` payload that explicitly triggers that rule to reach the `expected_outcome`.

Output carefully formatted JSON matching the schema."""

async def generate_batch(client, model_name, system_content, batch_index):
    try:
        response = await client.chat.completions.create(
            model=model_name,
            messages=[
                {"role": "system", "content": system_content},
                {"role": "user", "content": "Generate 50 rules now."}
            ],
            response_format={"type": "json_object"}
        )
        data = json.loads(response.choices[0].message.content)
        print(f"✅ Batch {batch_index+1}/10 generated.")
        return data.get("test_cases", [])
    except Exception as e:
        print(f"❌ Error during batch {batch_index+1}: {e}")
        return []

async def generate_dataset():
    api_key = os.environ.get("OPENAI_API_KEY") or os.environ.get("OPEN_AI_KEY")
    model_name = os.environ.get("GPT_MODEL", "gpt-5-mini-2025-08-07")
    
    if not api_key:
        print("❌ Error: OPENAI_API_KEY environment variable not set in .env")
        return
        
    client = openai.AsyncOpenAI(api_key=api_key)
    
    print(f"🚀 Querying OpenAI ({model_name}) concurrently to generate 500 LLM Test Cases (10 batches of 50)...")
    
    schema_json = LLMTestCaseBatch.model_json_schema()
    
    with open("schemas/ecommerce.json", "r") as f:
        ecommerce_schema = json.load(f)["schema"]
        
    system_content = f"{SYS_PROMPT}\n\nCRITICAL SCHEMA ENFORCEMENT:\nYou MUST strictly use the variable names provided in the following JSON schema. Do not invent any names not present in this dictionary.\nSchema:\n{json.dumps(ecommerce_schema)}\n\nStrictly format your response to match this JSON schema:\n{json.dumps(schema_json)}"
    
    tasks = [generate_batch(client, model_name, system_content, i) for i in range(10)]
    results = await asyncio.gather(*tasks)
    
    all_cases = []
    for batch_cases in results:
        all_cases.extend(batch_cases)
            
    # Save the dataset
    with open("scripts/stress_test/llm_test_dataset.json", "w") as f:
        json.dump(all_cases, f, indent=2)
        
    print(f"✅ Successfully generated and saved {len(all_cases)} LLM Test Cases!")

if __name__ == "__main__":
    asyncio.run(generate_dataset())
