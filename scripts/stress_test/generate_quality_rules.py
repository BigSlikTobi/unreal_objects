import json
import random

DOMAINS = ["FINANCE", "ECOMMERCE", "HEALTHCARE", "INFRASTRUCTURE", "CUSTOMER_SUPPORT"]
OUTCOMES = ["APPROVE", "REJECT", "ASK_FOR_APPROVAL"]

def generate_500_complex_rules():
    rules = []
    
    # We deliberately create overlapping rules on the same datapoints to force conflicts
    common_datapoints = ["transaction_amount", "user_risk_score", "ip_reputation"]
    
    for i in range(500):
        domain = random.choice(DOMAINS)
        feature = f"{domain.lower()}_governance"
        name = f"Rule_{i+1}_Complex_{domain}"
        
        # Pick 1-2 datapoints to evaluate
        num_dps = random.randint(1, 2)
        datapoints = random.sample(common_datapoints, num_dps)
        
        # Main Logic Outcome (Weighted: 50% Approve, 30% Ask, 20% Reject)
        main_outcome = random.choices(OUTCOMES, weights=[50, 30, 20])[0]
        
        # Create a complex JSON Logic condition
        if len(datapoints) == 1:
            dp = datapoints[0]
            op = random.choice([">", "<", "=="])
            val = random.randint(10, 1000)
            rule_logic_json = {"if": [{op: [{"var": dp}, val]}, main_outcome, None]}
            rule_logic_str = f"IF {dp} {op} {val} THEN {main_outcome}"
        else:
            dp1, dp2 = datapoints
            op1, op2 = random.choice([">", "<"]), random.choice([">", "<"])
            val1, val2 = random.randint(10, 1000), random.randint(10, 100)
            logic_op = random.choice(["and", "or"])
            
            rule_logic_json = {
                "if": [
                    {logic_op: [
                        {op1: [{"var": dp1}, val1]},
                        {op2: [{"var": dp2}, val2]}
                    ]},
                    main_outcome,
                    None
                ]
            }
            rule_logic_str = f"IF {dp1} {op1} {val1} {logic_op.upper()} {dp2} {op2} {val2} THEN {main_outcome}"
            
        # Add Edge Cases 40% of the time, often highly restrictive
        edge_cases = []
        edge_cases_json = []
        if random.random() < 0.4:
            ec_outcome = random.choices(["REJECT", "ASK_FOR_APPROVAL"], weights=[70, 30])[0]
            ec_dp = random.choice(common_datapoints)
            ec_val = random.randint(800, 5000) # Extreme value
            
            edge_cases.append(f"IF {ec_dp} > {ec_val} THEN {ec_outcome}")
            edge_cases_json.append({
                "if": [{">": [{"var": ec_dp}, ec_val]}, ec_outcome, None]
            })
            
        rules.append({
            "name": name,
            "feature": feature,
            "datapoints": datapoints,
            "edge_cases": edge_cases,
            "edge_cases_json": edge_cases_json,
            "rule_logic": rule_logic_str,
            "rule_logic_json": rule_logic_json
        })
        
    return rules

if __name__ == "__main__":
    generated_rules = generate_500_complex_rules()
    with open("scripts/stress_test/quality_rules_data.json", "w") as f:
        json.dump(generated_rules, f, indent=2)
    print(f"✅ Generated 500 complex/conflicting rules in scripts/stress_test/quality_rules_data.json")
