import asyncio
import httpx
import json
import os
from pydantic import ValidationError

async def evaluate_batch():
    print("🧪 Starting End-to-End LLM Generative Evaluation from Batch Results...\n")
    
    # 1. Load Original Dataset
    try:
        with open("scripts/stress_test/llm_test_dataset.json", "r") as f:
            test_cases = json.load(f)
    except FileNotFoundError:
        print("❌ Error: scripts/stress_test/llm_test_dataset.json not found.")
        return

    # 2. Load Batch Results
    batch_results = {}
    try:
        with open("scripts/stress_test/batch_results.jsonl", "r") as f:
            for line in f:
                if not line.strip():
                    continue
                record = json.loads(line)
                custom_id = record.get("custom_id")
                # OpenAI format returns choices -> message -> content
                try:
                    content = record["response"]["body"]["choices"][0]["message"]["content"]
                    parsed_json = json.loads(content)
                    batch_results[custom_id] = parsed_json
                except (KeyError, json.JSONDecodeError) as e:
                    print(f"⚠️ Failed to parse result for {custom_id}: {e}")
    except FileNotFoundError:
        print("❌ Error: scripts/stress_test/batch_results.jsonl not found. Run batch_2_check.py first!")
        return
        
    stats = {"passed": 0, "failed": 0, "translation_errors": 0}
    
    async with httpx.AsyncClient(timeout=20.0) as client:
        # Create an isolated group
        resp = await client.post("http://127.0.0.1:8001/v1/groups", json={
            "name": "E2E LLM Batch Group",
            "description": "Isolated group for generative tests"
        })
        group_id = resp.json()["id"]
        
        print(f"Beginning evaluation of {len(batch_results)} processed cases out of {len(test_cases)} total...")
        
        try:
            for i, case in enumerate(test_cases):
                custom_id = f"request-{i}"
                if custom_id not in batch_results:
                    print(f"⚠️ [{i+1}] Missing batch translation for '{custom_id}'. Skipping.")
                    stats["translation_errors"] += 1
                    continue
                    
                nl_rule = case["natural_language_rule"]
                ctx = case["context_data"]
                expected = case["expected_outcome"]
                translated = batch_results[custom_id]
                
                # 1. Append Required API Fields
                translated["name"] = f"E2E Rule {i}"
                translated["feature"] = f"e2e_feature"
                
                # 2. Upload the translated rule
                rule_resp = await client.post(f"http://127.0.0.1:8001/v1/groups/{group_id}/rules", json=translated)
                if rule_resp.status_code != 201:
                    print(f"\n❌ [{i+1}] Failed to load translated rule. Status: {rule_resp.status_code}")
                    print(f"   API Response: {rule_resp.text}")
                    stats["translation_errors"] += 1
                    continue
                rule_id = rule_resp.json()["id"]
                
                # 3. Evaluate context via Decision Center
                dec_resp = await client.get(
                    f"http://127.0.0.1:8002/v1/decide",
                    params={
                        "request_description": f"Test {i}",
                        "context": json.dumps(ctx),
                        "group_id": group_id
                    }
                )
                if dec_resp.status_code != 200:
                    print(f"\n❌ [{i+1}] Final decision request failed.")
                    stats["failed"] += 1
                    continue
                    
                decision_outcome = dec_resp.json()["outcome"]
                
                # 4. Assert correctness
                if decision_outcome == expected:
                    stats["passed"] += 1
                else:
                    print(f"\n❌ [{i+1}] Mismatch!")
                    print(f"   NL Rule: {nl_rule}")
                    print(f"   Expected: {expected} | Actual Computed: {decision_outcome}")
                    if dec_resp.json().get("matched_details"):
                         print(f"   Matched Triggers: {[m['trigger_expression'] for m in dec_resp.json()['matched_details']]}")
                    else:
                         print(f"   Missing Variables (Fail-Closed Hit) - Context supplied vs Schema expected differed.")
                    stats["failed"] += 1
                
                # Clean up the rule so the group only has 1 rule actively tested per iteration
                await client.delete(f"http://127.0.0.1:8001/v1/groups/{group_id}/rules/{rule_id}")
                
                if (i+1) % 10 == 0:
                    print(f"   ...evaluated {i+1} cases.")
                    
        finally:
            print("\n🧹 Cleaning up test group...")
            await client.delete(f"http://127.0.0.1:8001/v1/groups/{group_id}")
    
    print("\n--- Final E2E Accuracy Report ---")
    total = len(test_cases)
    print(f"Total Cases     : {total}")
    print(f"Passed          : {stats['passed']} ({(stats['passed']/total)*100 if total > 0 else 0:.1f}%)")
    print(f"Fail-Closed Mismatches (Safe) : {stats['failed']} ({(stats['failed']/total)*100 if total > 0 else 0:.1f}%)")
    print(f"Parse Errors    : {stats['translation_errors']} ({(stats['translation_errors']/total)*100 if total > 0 else 0:.1f}%)")

if __name__ == "__main__":
    asyncio.run(evaluate_batch())
