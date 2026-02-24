from fastapi import FastAPI, HTTPException
from typing import List

from .models import BusinessRule, BusinessRuleGroup, CreateRule, CreateRuleGroup
from .store import RuleStore

app = FastAPI(title="Unreal Objects Rule Engine API")
store = RuleStore()

@app.post("/v1/groups", response_model=BusinessRuleGroup, status_code=201)
async def create_group(group: CreateRuleGroup):
    return store.create_group(group)

@app.get("/v1/groups", response_model=List[BusinessRuleGroup])
async def list_groups():
    return store.list_groups()

@app.get("/v1/groups/{group_id}", response_model=BusinessRuleGroup)
async def get_group(group_id: str):
    group = store.get_group(group_id)
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")
    return group

@app.delete("/v1/groups/{group_id}", status_code=204)
async def delete_group(group_id: str):
    if not store.delete_group(group_id):
        raise HTTPException(status_code=404, detail="Group not found")

@app.post("/v1/groups/{group_id}/rules", response_model=BusinessRule, status_code=201)
async def add_rule(group_id: str, rule: CreateRule):
    created = store.add_rule(group_id, rule)
    if not created:
        raise HTTPException(status_code=404, detail="Group not found")
    return created

@app.get("/v1/groups/{group_id}/rules/{rule_id}", response_model=BusinessRule)
async def get_rule(group_id: str, rule_id: str):
    rule = store.get_rule(group_id, rule_id)
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    return rule

@app.delete("/v1/groups/{group_id}/rules/{rule_id}", status_code=204)
async def delete_rule(group_id: str, rule_id: str):
    if not store.delete_rule(group_id, rule_id):
        raise HTTPException(status_code=404, detail="Rule not found")

@app.put("/v1/groups/{group_id}/rules/{rule_id}", response_model=BusinessRule)
async def update_rule(group_id: str, rule_id: str, rule: CreateRule):
    updated = store.update_rule(group_id, rule_id, rule)
    if not updated:
        raise HTTPException(status_code=404, detail="Rule or Group not found")
    return updated

