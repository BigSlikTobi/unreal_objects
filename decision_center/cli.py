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

OUTCOMES = ["APPROVE", "ASK_FOR_APPROVAL", "REJECT"]

def _prompt_outcome(label: str, include_none: bool = False) -> str:
    """Numbered outcome picker. Returns the selected outcome string, or '' if none chosen."""
    print(f"\n  {label}")
    for i, o in enumerate(OUTCOMES, 1):
        print(f"    {i}. {o}")
    if include_none:
        print(f"    {len(OUTCOMES) + 1}. (none — skip ELSE branch)")
    while True:
        raw = input(f"  Select [1-{len(OUTCOMES) + (1 if include_none else 0)}]: ").strip()
        try:
            idx = int(raw) - 1
            if 0 <= idx < len(OUTCOMES):
                return OUTCOMES[idx]
            if include_none and idx == len(OUTCOMES):
                return ""
        except ValueError:
            pass
        print("  Invalid choice, try again.")


def _prompt_structured_builder(existing_rule: dict | None = None) -> tuple[str, str, str, list[dict]]:
    """Fill-in-the-blank rule builder. Returns (condition, then_outcome, else_outcome, edge_cases).
    If existing_rule is provided, shows the current values as context before prompting afresh.
    """
    print("\n--- Rule Builder ---")
    if existing_rule:
        print(f"  Current logic : {existing_rule.get('rule_logic', '')}")
        if existing_rule.get("edge_cases"):
            for ec in existing_rule["edge_cases"]:
                print(f"  ↳ Edge case   : {ec}")
        print("")

    condition = input("  IF   : ").strip()
    then_outcome = _prompt_outcome("THEN :")
    else_outcome = _prompt_outcome("ELSE : (optional)", include_none=True)

    edge_cases: list[dict] = []
    while True:
        add = input("\n  Add an edge case? [y/N]: ").strip().lower()
        if add != "y":
            break
        ec_condition = input("    IF   : ").strip()
        ec_outcome = _prompt_outcome("    THEN :")
        edge_cases.append({"condition": ec_condition, "outcome": ec_outcome})

    return condition, then_outcome, else_outcome, edge_cases


def _build_structured_prompt(condition: str, then_outcome: str, else_outcome: str, edge_cases: list[dict]) -> str:
    """Mirrors buildPrompt() in the React UI — produces a precise structured prompt for the LLM."""
    main = f"IF {condition} THEN {then_outcome}"
    if else_outcome:
        main += f" ELSE {else_outcome}"
    prompt = f"Translate this structured rule into JSON Logic format.\nMain rule: {main}"
    if edge_cases:
        prompt += "\nEdge cases (each a separate entry in edge_cases):"
        for ec in edge_cases:
            prompt += f"\n- IF {ec['condition']} THEN {ec['outcome']}"
    return prompt


def _prompt_datapoint_type(dp_name: str) -> dict:
    """Interactively prompt the user for the type of a new datapoint."""
    print(f"\n  New datapoint detected: '{dp_name}'")
    print("  Types: 1. text  2. number  3. boolean  4. enum")
    type_choice = input("  Select type [1-4, default=1]: ").strip()
    type_map = {"1": "text", "2": "number", "3": "boolean", "4": "enum"}
    dp_type = type_map.get(type_choice, "text")
    values = []
    if dp_type == "enum":
        vals_str = input(f"  Allowed values for '{dp_name}' (comma-separated, e.g. EUR,USD,GBP): ").strip()
        values = [v.strip() for v in vals_str.split(",") if v.strip()]
    return {"name": dp_name, "type": dp_type, "values": values}


def prompt_rule_creation(group_id: str, llm_config: dict | None = None) -> dict:
    print("\n--- Rule Management ---")
    
    # Fetch existing rules AND datapoint definitions from the group
    with httpx.Client() as client:
        try:
            resp = client.get(f"http://127.0.0.1:8001/v1/groups/{group_id}")
            group_data = resp.json() if resp.status_code == 200 else {}
            existing_rules = group_data.get("rules", [])
            datapoint_definitions = group_data.get("datapoint_definitions", [])
        except httpx.RequestError:
            existing_rules = []
            datapoint_definitions = []

    if datapoint_definitions:
        dp_summary = []
        for d in datapoint_definitions:
            desc = f"{d['name']} ({d['type']})"
            if d.get("values"):
                desc += f" [{', '.join(d['values'])}]"
            dp_summary.append(desc)
        print(f"\nKnown datapoint types: {', '.join(dp_summary)}")

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
        context_schema = None
        print("\n--- Optional Schema Enforcement ---")
        print("  Schemas lock the AI to a pre-approved set of variable names so all your rules")
        print("  speak the same language. Without one, the LLM invents its own names and the same")
        print("  concept might become 'amount' in one rule and 'transaction_amount' in another —")
        print("  causing evaluation mismatches. Pick the schema that matches your domain.")
        print("")
        print("  1. None (Freeform) — AI picks its own variable names")
        print("  2. E-Commerce Blueprint — orders, payments, cart, shipping, user accounts")
        print("  3. Finance Blueprint   — withdrawals, balances, loans, KYC, AML risk scores")
        print("  4. Custom Schema Path  — point to your own JSON schema file")
        schema_choice = input("Select an option [1-4, Default: 1]: ").strip()
        
        if schema_choice == "2":
            schema_path = "schemas/ecommerce.json"
        elif schema_choice == "3":
            schema_path = "schemas/finance.json"
        elif schema_choice == "4":
            schema_path = input("Enter path to your JSON schema relative to project root: ").strip()
        else:
            schema_path = None
            
        if schema_path and os.path.exists(schema_path):
            with open(schema_path, "r") as f:
                try:
                    schema_data = json.load(f)
                    context_schema = schema_data.get("schema", schema_data)
                    print(f"Loaded schema from {schema_path}")
                except json.JSONDecodeError:
                    print("Invalid JSON, skipping schema enforcement")
        elif schema_path:
             print(f"File {schema_path} not found, skipping schema enforcement")

        condition, then_outcome, else_outcome, builder_edge_cases = _prompt_structured_builder(existing_rule_obj)
        natural_language = _build_structured_prompt(condition, then_outcome, else_outcome, builder_edge_cases)

        while True:
            print("\nTranslating using LLM Rule Wizard...")
            try:
                translation = translate_rule(
                    natural_language=natural_language,
                    feature=feature,
                    name=name,
                    provider=llm_config["provider"],
                    model=llm_config["model"],
                    api_key=llm_config["api_key"],
                    context_schema=context_schema,
                    datapoint_definitions=datapoint_definitions,
                )
                datapoints = translation["datapoints"]
                edge_cases = translation.get("edge_cases", [])
                edge_cases_json = translation.get("edge_cases_json", [])
                rule_logic = translation["rule_logic"]
                rule_logic_json = translation.get("rule_logic_json", {})
                print(f"\n✨ Extracted Datapoints: {', '.join(datapoints)}")
                if edge_cases:
                    print(f"✨ Edge Cases:")
                    for ec in edge_cases:
                        print(f"   ↳ {ec}")
                print(f"✨ Structured Logic: {rule_logic}")
                if rule_logic_json:
                    print(f"✨ JSON Logic: {json.dumps(rule_logic_json)}")

                print("\nOptions:")
                print("  [A]ccept this rule")
                print("  [E]dit — update the builder and re-translate")
                print("  [M]anual creation fallback")
                choice = input("Select an option [A/e/m]: ").strip().upper() or 'A'

                if choice == 'E':
                    condition, then_outcome, else_outcome, builder_edge_cases = _prompt_structured_builder()
                    natural_language = _build_structured_prompt(condition, then_outcome, else_outcome, builder_edge_cases)
                    continue
                elif choice == 'M':
                    print("\nFalling back to manual creation.")
                    llm_config = None
                    break
                else:
                    # Prompt for types of any NEW datapoints not yet defined
                    known_names = {d["name"] for d in datapoint_definitions}
                    new_defs = []
                    for dp in datapoints:
                        if dp not in known_names:
                            new_def = _prompt_datapoint_type(dp)
                            new_defs.append(new_def)
                            datapoint_definitions.append(new_def)
                            known_names.add(dp)
                    if new_defs:
                        print(f"\nSaving {len(new_defs)} new datapoint definition(s)...")
                        with httpx.Client() as client:
                            patch_resp = client.patch(
                                f"http://127.0.0.1:8001/v1/groups/{group_id}/datapoints",
                                json=new_defs
                            )
                            if patch_resp.status_code == 200:
                                print("✅ Datapoint definitions saved.")
                            else:
                                print(f"⚠️  Could not save datapoint definitions: {patch_resp.status_code}")
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

    # Fetch datapoint definitions for type-aware coercion
    dp_defs: dict[str, dict] = {}
    with httpx.Client() as client:
        try:
            resp = client.get(f"http://127.0.0.1:8001/v1/groups/{group_id}")
            if resp.status_code == 200:
                for d in resp.json().get("datapoint_definitions", []):
                    dp_defs[d["name"]] = d
        except httpx.RequestError:
            pass
    
    context = {}
    for dp in rule.get("datapoints", []):
        defn = dp_defs.get(dp, {})
        dp_type = defn.get("type", "text")
        allowed_values = defn.get("values", [])

        if dp_type == "enum" and allowed_values:
            print(f"  '{dp}' allowed values: {', '.join(allowed_values)}")
            val = input(f"Provide a value for datapoint '{dp}': ").strip()
            context[dp] = val  # keep as string
        elif dp_type == "boolean":
            raw = input(f"Provide a value for datapoint '{dp}' [true/false]: ").strip().lower()
            context[dp] = raw == "true"
        elif dp_type == "number":
            raw = input(f"Provide a value for datapoint '{dp}' (number): ").strip()
            try:
                context[dp] = float(raw) if '.' in raw else int(raw)
            except ValueError:
                context[dp] = raw
        else:
            # text or unknown — keep as string
            context[dp] = input(f"Provide a value for datapoint '{dp}': ").strip()
        
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
