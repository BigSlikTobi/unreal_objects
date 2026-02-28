import asyncio
import httpx
import json
import time

async def test_complex_rule_set():
    print("🧪 Loading 500 Complex Conflicting Rules for Diagnostic Testing...\n")
    
    async with httpx.AsyncClient() as client:
        # Create group
        resp = await client.post("http://127.0.0.1:8001/v1/groups", json={
            "name": "Chaos Group",
            "description": "500 randomly conflicting JSON logic rules"
        })
        group_id = resp.json()["id"]
        
        # Load rules
        with open("scripts/stress_test/quality_rules_data.json", "r") as f:
            rules = json.load(f)
            
        print("Uploading 500 rules...")
        for r in rules:
            await client.post(f"http://127.0.0.1:8001/v1/groups/{group_id}/rules", json=r)
            
        print("✅ Rules Loaded. Commencing Shadowing & Conflict Diagnostic Tests...\n")
        
        # Define high-conflict scenarios
        test_contexts = [
            ("Low Value, High Trust", {"transaction_amount": 10, "ip_reputation": 99, "user_risk_score": 1}),
            ("Mid Value, Mid Trust", {"transaction_amount": 1500, "ip_reputation": 50, "user_risk_score": 50}),
            ("High Value, Low Trust", {"transaction_amount": 9500, "ip_reputation": 10, "user_risk_score": 90}),
            ("Missing Data (Fail-Closed Trigger)", {"user_name": "Tobias"}), # Missing numeric data
            ("Type Mismatch", {"transaction_amount": "one thousand"}) # String instead of int
        ]
        
        print("="*60)
        for name, ctx in test_contexts:
            print(f"📌 Scenario: {name}")
            print(f"Context Payload: {ctx}")
            
            start = time.time()
            res = await client.get(f"http://127.0.0.1:8002/v1/decide?request_description=QA&context={json.dumps(ctx)}&group_id={group_id}")
            end = time.time()
            
            data = res.json()
            matched_count = len(data.get("matched_rules", []))
            details = data.get("matched_details", [])
            
            print(f"➡ Final Outcome: {data['outcome']}")
            print(f"➡ Matched {matched_count} conflicting rules in {(end-start)*1000:.2f}ms")
            
            # Analyze resolution
            rejects = sum(1 for d in details if "REJECT" in d["trigger_expression"].upper())
            asks = sum(1 for d in details if "ASK_FOR_APPROVAL" in d["trigger_expression"].upper())
            approves = sum(1 for d in details if "APPROVE" in d["trigger_expression"].upper())
            edge_hits = sum(1 for d in details if d["hit_type"] == "edge_case")
            
            print(f"   [Breakdown] Approves: {approves} | Asks: {asks} | Rejects: {rejects} | Edge Cases Fired: {edge_hits}")
            
            # Print the most restrictive triggers that forced the decision
            restrictive_details = [d for d in details if (data['outcome'] == "REJECT" and "REJECT" in d["trigger_expression"].upper()) or (data['outcome'] == "ASK_FOR_APPROVAL" and "ASK_FOR_APPROVAL" in d["trigger_expression"].upper())]
            
            if restrictive_details:
                print("   [Winning Constraints (Sample)]:")
                for d in restrictive_details[:3]: # print top 3 matches forcing the decision
                    print(f"      - {d['hit_type'].upper()}: {d['trigger_expression']}")
            print("-" * 60)
            
        print("\n🧹 Cleaning up Chaos Group...")
        await client.delete(f"http://127.0.0.1:8001/v1/groups/{group_id}")

if __name__ == "__main__":
    asyncio.run(test_complex_rule_set())
