import httpx
import subprocess
import time
import json
import urllib.parse
import os

def prompt_start_servers():
    choice = input("Start Rule Engine (8001) and Decision Center (8002) locally? [y/N] ").strip().lower()
    if choice == 'y':
        print("Starting servers in the background...")
        subprocess.Popen(["uvicorn", "rule_engine.app:app", "--port", "8001"])
        subprocess.Popen(["uvicorn", "decision_center.app:app", "--port", "8002"])
        time.sleep(2)  # Give them a moment to bind
        print("Servers started.")
    else:
        print("Skipping auto-start. Please ensure servers are running manually.")

def prompt_group_selection() -> str:
    print("\n--- Group Selection ---")
    with httpx.Client() as client:
        try:
            resp = client.get("http://127.0.0.1:8001/v1/groups")
            groups = resp.json() if resp.status_code == 200 else []
        except httpx.RequestError:
            groups = []

    if groups:
        print("Existing Groups:")
        for idx, g in enumerate(groups, 1):
            print(f"  {idx}. {g['name']} ({g['id']})")
        print("  C. Create a new group")
    else:
        print("No existing groups found. You must create a new one.")
    
    choice = input("Select a group number, or type 'CREATE' to make a new one: ").strip().upper()
    
    if choice == 'C' or choice == 'CREATE' or not groups:
        name = input("New Group Name: ").strip()
        desc = input("New Group Description: ").strip()
        with httpx.Client() as client:
            resp = client.post("http://127.0.0.1:8001/v1/groups", json={"name": name, "description": desc})
            resp.raise_for_status()
            data = resp.json()
            print(f"Created group '{data['name']}' with ID: {data['id']}")
            return data["id"]
    else:
        try:
            idx = int(choice) - 1
            if 0 <= idx < len(groups):
                return groups[idx]["id"]
        except ValueError:
            pass
        print("Invalid choice. Restarting selection.")
        return prompt_group_selection()

def prompt_rule_creation(group_id: str) -> dict:
    print("\n--- Rule Creation ---")
    name = input("Rule Name: ").strip()
    feature = input("Feature (e.g. Fraud Check): ").strip()
    dp_str = input("Datapoints (comma-separated): ").strip()
    datapoints = [d.strip() for d in dp_str.split(",") if d.strip()]
    rule_logic = input("Rule Logic (e.g. IF amount > 500 THEN ASK_FOR_APPROVAL): ").strip()

    payload = {
        "name": name,
        "feature": feature,
        "datapoints": datapoints,
        "edge_cases": [],
        "rule_logic": rule_logic
    }

    with httpx.Client() as client:
        resp = client.post(f"http://127.0.0.1:8001/v1/groups/{group_id}/rules", json=payload)
        resp.raise_for_status()
        rule = resp.json()
        print(f"Created rule '{rule['name']}' with ID: {rule['id']}")
        return rule

def prompt_auto_test(group_id: str, rule: dict):
    print(f"\n--- Auto-Test for Rule: {rule.get('name', 'Unknown')} ---")
    print("Let's test this rule!")
    
    context = {}
    for dp in rule.get("datapoints", []):
        val = input(f"Provide a value for datapoint '{dp}': ").strip()
        try:
            val = float(val) if '.' in val else int(val)
        except ValueError:
            pass
        context[dp] = val
        
    desc = input("Please provide a request description: ").strip()
    
    with httpx.Client() as client:
        try:
            ctx_str = urllib.parse.quote(json.dumps(context))
            desc_str = urllib.parse.quote(desc)
            url = f"http://127.0.0.1:8002/v1/decide?request_description={desc_str}&context={ctx_str}&group_id={group_id}"
            resp = client.get(url)
            resp.raise_for_status()
            data = resp.json()
            print("\n✅ Test Evaluation Complete!")
            print(f"Outcome: {data.get('outcome')}")
            print(f"Matched Rules: {data.get('matched_rules', [])}")
            print(f"Log ID: {data.get('request_id')}")
        except Exception as e:
            print(f"\n❌ Test Failed: {e}")

def main():
    os.system('cls' if os.name == 'nt' else 'clear')
    print(r"""
  _   _ _   _ _____  ______          _         ____  ____     _ ______  _____ _______  _____ 
 | | | | \ | |  __ \|  ____|   /\   | |       / __ \|  _ \   | |  ____|/ ____|__   __|/ ____|
 | | | |  \| | |__) | |__     /  \  | |      | |  | | |_) |  | | |__  | |       | |  | (___  
 | | | | . ` |  _  /|  __|   / /\ \ | |      | |  | |  _ <_  | |  __| | |       | |   \___ \ 
 | |_| | |\  | | \ \| |____ / ____ \| |____  | |__| | |_) | |_| | |____| |____   | |   ____) |
  \___/|_| \_|_|  \_\______/_/    \_\______|  \____/|____/ \___/|______|\_____|  |_|  |_____/ 
                                                                                              
                       R  U  L  E  S      E  N  G  I  N  E
""")
    prompt_start_servers()
    group_id = prompt_group_selection()
    print(f"\nFinal Selected Group ID: {group_id}")
    rule = prompt_rule_creation(group_id)
    print(f"\nFinal Created Rule ID: {rule['id']}")
    prompt_auto_test(group_id, rule)

if __name__ == "__main__":
    main()
