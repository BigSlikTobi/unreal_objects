import httpx
import subprocess
import time
import json
import urllib.parse
import os
import getpass

from decision_center.translator import check_llm_connection, translate_rule

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

def prompt_llm_setup() -> dict | None:
    print("\n--- LLM Rule Wizard ---")
    use_llm = input("Do you want to use an LLM for Rule Creation? [y/N] ").strip().lower()
    
    if use_llm != 'y':
        return None
        
    print("\nProviders:")
    print("  1. OpenAI")
    print("  2. Anthropic")
    print("  3. Gemini")
    
    provider_choice = input("Select provider [1-3]: ").strip()
    provider_map = {"1": "openai", "2": "anthropic", "3": "gemini"}
    
    provider = provider_map.get(provider_choice)
    if not provider:
        print("Invalid provider. Falling back to manual rule creation.")
        return None
        
    print(f"\nModels for {provider}:")
    if provider == "openai":
        models = ["gpt-5.2", "gpt-5-mini", "gpt-5-nano"]
    elif provider == "anthropic":
        models = ["claude-4.6-opus", "claude-4.6-sonnet", "claude-4.5-haiku"]
    elif provider == "gemini":
        models = ["gemini-3.1-pro", "gemini-3.0-flash"]
        
    for idx, model in enumerate(models, 1):
        print(f"  {idx}. {model}")
        
    model_choice = input(f"Select model [1-{len(models)}]: ").strip()
    try:
        model = models[int(model_choice) - 1]
    except (ValueError, IndexError):
        print("Invalid model selection. Falling back to manual rule creation.")
        return None
        
    env_var_name = f"{provider.upper()}_API_KEY"
    api_key = os.environ.get(env_var_name)
    
    if api_key:
        print(f"Using {provider} API Key from environment variable '{env_var_name}'.")
    else:
        api_key = getpass.getpass(f"Enter your {provider} API Key (Hidden): ").strip()
    
    print("\nTesting connection...")
    if check_llm_connection(provider, model, api_key):
        print("✅ Connection successful!")
        return {"provider": provider, "model": model, "api_key": api_key}
    else:
        print("❌ Connection failed. Check your API key. Falling back to manual rule creation.")
        return None

def prompt_rule_creation(group_id: str, llm_config: dict | None = None) -> dict:
    print("\n--- Rule Management ---")
    
    # Check for existing rules in the group
    with httpx.Client() as client:
        try:
            resp = client.get(f"http://127.0.0.1:8001/v1/groups/{group_id}")
            group_data = resp.json() if resp.status_code == 200 else {}
            existing_rules = group_data.get("rules", [])
        except httpx.RequestError:
            existing_rules = []

    rule_id = None
    name = ""
    feature = ""
    existing_rule_obj = None
    
    if existing_rules:
        print("Existing Rules:")
        for idx, r in enumerate(existing_rules, 1):
            print(f"  {idx}. {r['name']} ({r['id']})")
        print("  C. Create a new rule")
        
        choice = input("Select a rule to UPDATE, or type 'CREATE': ").strip().upper()
        if choice != 'C' and choice != 'CREATE':
            try:
                idx = int(choice) - 1
                if 0 <= idx < len(existing_rules):
                    selected = existing_rules[idx]
                    rule_id = selected["id"]
                    name = selected["name"]
                    feature = selected["feature"]
                    existing_rule_obj = selected
                    print(f"\nUpdating Rule: {name}")
            except ValueError:
                pass
                
    if not rule_id:
        name = input("Rule Name: ").strip()
        feature = input("Feature (e.g. Fraud Check): ").strip()
    
    if llm_config:
        if existing_rule_obj:
            print(f"Current Logic: {existing_rule_obj.get('rule_logic')}")
            if existing_rule_obj.get('edge_cases'):
                print(f"Current Edge Cases: {', '.join(existing_rule_obj.get('edge_cases', []))}")
            
            skip_logic = input("\nDo you want to skip rewriting the main logic and just add an edge case? [y/N] ").strip().lower() == 'y'
            if skip_logic:
                base_nl = f"Keep the main logic exactly as: '{existing_rule_obj.get('rule_logic')}'. "
                if existing_rule_obj.get('edge_cases'):
                    base_nl += f"Keep these existing edge cases exactly: '{'; '.join(existing_rule_obj['edge_cases'])}'. "
                extra_ec = input("Describe the NEW edge case condition to add (e.g. Reject if originating in CA): ").strip()
                natural_language = base_nl + f"Add this NEW edge case constraint: {extra_ec}"
            else:
                natural_language = input("\nDescribe the entirely new rule logic: ").strip()
        else:
            natural_language = input("Describe the rule logic (e.g. if they owe more than 100 then ask them): ").strip()
            
        while True:
            print("\nTranslating using LLM Rule Wizard...")
            try:
                translation = translate_rule(
                    natural_language=natural_language,
                    feature=feature,
                    name=name,
                    provider=llm_config["provider"],
                    model=llm_config["model"],
                    api_key=llm_config["api_key"]
                )
                datapoints = translation["datapoints"]
                edge_cases = translation.get("edge_cases", [])
                edge_cases_json = translation.get("edge_cases_json", [])
                rule_logic = translation["rule_logic"]
                rule_logic_json = translation.get("rule_logic_json", {})
                print(f"\n✨ Extracted Datapoints: {', '.join(datapoints)}")
                if edge_cases:
                    print(f"✨ Edge Cases: {', '.join(edge_cases)}")
                print(f"✨ Structured Logic: {rule_logic}")
                if rule_logic_json:
                    print(f"✨ JSON Logic: {json.dumps(rule_logic_json)}")

                print("\nOptions:")
                print("  [A]ccept this rule")
                print("  [E]dditional edge case constraint")
                print("  [R]etry translation with a new description")
                print("  [M]anual creation fallback")
                choice = input("Select an option [A/e/r/m]: ").strip().upper() or 'A'
                
                if choice == 'E':
                    extra_ec = input("Describe the condition to catch (e.g. Reject if originating in CA): ").strip()
                    if extra_ec:
                        natural_language += f". Also, edge case constraint: {extra_ec}"
                    continue
                elif choice == 'R':
                    natural_language = input("\nDescribe the rule logic again: ").strip()
                    continue
                elif choice == 'M':
                    print("\nFalling back to manual creation.")
                    llm_config = None
                    break
                else:
                    break
            except Exception as e:
                print(f"❌ Translation failed: {e}")
                print("Falling back to manual creation.")
                llm_config = None
                break
            
    if not llm_config:
        dp_str = input("Datapoints (comma-separated): ").strip()
        datapoints = [d.strip() for d in dp_str.split(",") if d.strip()]
        ec_str = input("Edge Cases (comma-separated, optional): ").strip()
        edge_cases = [e.strip() for e in ec_str.split(",") if e.strip()]
        rule_logic = input("Rule Logic (e.g. IF amount > 500 THEN ASK_FOR_APPROVAL): ").strip()
        
        # Manual flow has no json logic engine attached yet
        rule_logic_json = {}
        edge_cases_json = []

    payload = {
        "name": name,
        "feature": feature,
        "datapoints": datapoints,
        "edge_cases": edge_cases,
        "edge_cases_json": edge_cases_json,
        "rule_logic": rule_logic,
        "rule_logic_json": rule_logic_json
    }

    with httpx.Client() as client:
        if rule_id:
            # Update existing
            resp = client.put(f"http://127.0.0.1:8001/v1/groups/{group_id}/rules/{rule_id}", json=payload)
            action = "Updated"
        else:
            # Create new
            resp = client.post(f"http://127.0.0.1:8001/v1/groups/{group_id}/rules", json=payload)
            action = "Created"
            
        resp.raise_for_status()
        rule = resp.json()
        print(f"\n✅ {action} rule '{rule['name']}' with ID: {rule['id']}")
        if rule.get("edge_cases"):
            print(f"      Edge Cases: {', '.join(rule['edge_cases'])}")
        print(f"      Rule Logic: {rule.get('rule_logic', '')}")
        if rule.get("rule_logic_json"):
            print(f"      JSON Logic: {json.dumps(rule.get('rule_logic_json'))}")
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
            
            details = data.get("matched_details", [])
            if details:
                print("Triggered Conditions:")
                for d in details:
                    print(f"  - [{d['hit_type'].upper()}] {d['rule_name']}: {d['trigger_expression']}")
            else:
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
    
    llm_config = prompt_llm_setup()
    group_id = prompt_group_selection()
    print(f"\nFinal Selected Group ID: {group_id}")
    
    while True:
        rule = prompt_rule_creation(group_id, llm_config)
        prompt_auto_test(group_id, rule)
        
        cont = input("\nDo you want to manage another rule in this group? [Y/n] ").strip().lower()
        if cont == 'n':
            print("Exiting Decision Center Wizard. Goodbye!")
            break

if __name__ == "__main__":
    main()
