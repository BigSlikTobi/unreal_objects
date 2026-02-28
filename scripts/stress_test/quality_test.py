import asyncio
import httpx
import json

async def run_quality_tests():
    print("🧪 Starting Logical Quality & Conflict Tests...\n")
    
    async with httpx.AsyncClient(timeout=10.0) as client:
        
        # --- Helper for creating a group ---
        async def create_group(name):
            resp = await client.post("http://127.0.0.1:8001/v1/groups", json={
                "name": name,
                "description": "Deterministic semantic testing"
            })
            return resp.json()["id"]

        g1_id = await create_group("QA_Group_S1")
        g2_id = await create_group("QA_Group_S2")
        g3a_id = await create_group("QA_Group_S3a")
        g3b_id = await create_group("QA_Group_S3b")
        
        # --- SCENARIO 1: Edge Case Priority ---
        rule1 = {
            "name": "S1_EdgeCase_Priority",
            "feature": "edge_testing",
            "datapoints": ["amount"],
            "edge_cases": ["IF amount > 500 THEN REJECT"],
            "edge_cases_json": [{"if": [{">": [{"var": "amount"}, 500]}, "REJECT", None]}],
            "rule_logic": "IF amount > 100 THEN APPROVE",
            "rule_logic_json": {"if": [{">": [{"var": "amount"}, 100]}, "APPROVE", None]}
        }
        await client.post(f"http://127.0.0.1:8001/v1/groups/{g1_id}/rules", json=rule1)
        
        # --- SCENARIO 2: Conflict Resolution ---
        rule2a = {
            "name": "S2_Conflict_Reject",
            "feature": "conflict_testing",
            "datapoints": ["amount"],
            "edge_cases": [],
            "edge_cases_json": [],
            "rule_logic": "IF amount > 100 THEN REJECT",
            "rule_logic_json": {"if": [{">": [{"var": "amount"}, 100]}, "REJECT", None]}
        }
        rule2b = {
            "name": "S2_Conflict_Ask",
            "feature": "conflict_testing",
            "datapoints": ["amount"],
            "edge_cases": [],
            "edge_cases_json": [],
            "rule_logic": "IF amount > 50 THEN ASK_FOR_APPROVAL",
            "rule_logic_json": {"if": [{">": [{"var": "amount"}, 50]}, "ASK_FOR_APPROVAL", None]}
        }
        await client.post(f"http://127.0.0.1:8001/v1/groups/{g2_id}/rules", json=rule2a)
        await client.post(f"http://127.0.0.1:8001/v1/groups/{g2_id}/rules", json=rule2b)
        
        # --- SCENARIO 3: Fail-Closed Integrity ---
        rule3a = {
            "name": "S3_FailClosed_Approve",
            "feature": "fail_closed_testing",
            "datapoints": ["loyalty_score"],
            "edge_cases": [],
            "edge_cases_json": [],
            "rule_logic": "IF loyalty_score > 100 THEN APPROVE",
            "rule_logic_json": {"if": [{">": [{"var": "loyalty_score"}, 100]}, "APPROVE", None]}
        }
        rule3b = {
            "name": "S3_FailClosed_Reject",
            "feature": "fail_closed_testing",
            "datapoints": ["order_total"],
            "edge_cases": [],
            "edge_cases_json": [],
            "rule_logic": "IF order_total == 0 THEN REJECT",
            "rule_logic_json": {"if": [{"==": [{"var": "order_total"}, 0]}, "REJECT", None]}
        }
        await client.post(f"http://127.0.0.1:8001/v1/groups/{g3a_id}/rules", json=rule3a)
        await client.post(f"http://127.0.0.1:8001/v1/groups/{g3b_id}/rules", json=rule3b)
        
        # --- Execute Tests against Decision Center ---
        print("\n--- Running Evaluations ---")
        
        stats = {"passed": 0, "failed": 0}

        def assert_outcome(scenario, expected, actual, request_data):
            if expected == actual:
                print(f"✅ {scenario}: Expected {expected}, got {actual}")
                stats["passed"] += 1
            else:
                print(f"❌ {scenario}: Expected {expected}, got {actual}")
                print(f"    Request: {request_data}")
                stats["failed"] += 1

        r1 = await client.get(f"http://127.0.0.1:8002/v1/decide?request_description=S1&context={json.dumps({'amount': 600})}&group_id={g1_id}")
        assert_outcome("Scenario 1: Edge Case Priority", "REJECT", r1.json()["outcome"], r1.json())
        
        r2 = await client.get(f"http://127.0.0.1:8002/v1/decide?request_description=S2&context={json.dumps({'amount': 150})}&group_id={g2_id}")
        assert_outcome("Scenario 2: Conflict Resolution (Most Restrictive Wins)", "REJECT", r2.json()["outcome"], r2.json())
        
        r3a = await client.get(f"http://127.0.0.1:8002/v1/decide?request_description=S3a&context={json.dumps({})}&group_id={g3a_id}")
        assert_outcome("Scenario 3a: Fail-Closed Integrity (Missing Data -> Escalation)", "ASK_FOR_APPROVAL", r3a.json()["outcome"], r3a.json())
        
        r3b = await client.get(f"http://127.0.0.1:8002/v1/decide?request_description=S3b&context={json.dumps({'order_total': 'invalid'})}&group_id={g3b_id}")
        assert_outcome("Scenario 3b: Fail-Closed Integrity (Type Mismatch -> Restrictive)", "REJECT", r3b.json()["outcome"], r3b.json())
        
        print(f"\n🎯 Quality Suite Result: {stats['passed']} Passed, {stats['failed']} Failed")
        
        # Clean up groups
        await client.delete(f"http://127.0.0.1:8001/v1/groups/{g1_id}")
        await client.delete(f"http://127.0.0.1:8001/v1/groups/{g2_id}")
        await client.delete(f"http://127.0.0.1:8001/v1/groups/{g3a_id}")
        await client.delete(f"http://127.0.0.1:8001/v1/groups/{g3b_id}")

if __name__ == "__main__":
    asyncio.run(run_quality_tests())
