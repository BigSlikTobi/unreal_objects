from __future__ import annotations

import json
from pathlib import Path

from .models import BusinessRule, BusinessRuleGroup, CreateRule, CreateRuleGroup


class RuleStore:
    def __init__(self, persistence_path: str | Path | None = None):
        self.groups: dict[str, BusinessRuleGroup] = {}
        self.persistence_path = Path(persistence_path) if persistence_path else None
        self._load()

    def _load(self) -> None:
        if self.persistence_path is None or not self.persistence_path.exists():
            return
        try:
            payload = json.loads(self.persistence_path.read_text())
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"Failed to parse rule store at {self.persistence_path}: {exc}") from exc

        raw_groups = payload.get("groups", [])
        try:
            groups = [BusinessRuleGroup.model_validate(group) for group in raw_groups]
        except Exception as exc:
            raise RuntimeError(f"Failed to validate rule store at {self.persistence_path}: {exc}") from exc
        self.groups = {group.id: group for group in groups}

    def _save(self) -> None:
        if self.persistence_path is None:
            return
        self.persistence_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "groups": [group.model_dump(mode="json") for group in self.groups.values()],
        }
        self.persistence_path.write_text(json.dumps(payload, indent=2))

    def create_group(self, group_create: CreateRuleGroup) -> BusinessRuleGroup:
        group = BusinessRuleGroup(
            name=group_create.name,
            description=group_create.description
        )
        self.groups[group.id] = group
        self._save()
        return group

    def list_groups(self) -> list[BusinessRuleGroup]:
        return list(self.groups.values())

    def get_group(self, group_id: str) -> BusinessRuleGroup | None:
        return self.groups.get(group_id)

    def delete_group(self, group_id: str) -> bool:
        if group_id in self.groups:
            del self.groups[group_id]
            self._save()
            return True
        return False

    def add_rule(self, group_id: str, rule_create: CreateRule) -> BusinessRule | None:
        group = self.get_group(group_id)
        if not group:
            return None
        rule = BusinessRule(
            name=rule_create.name,
            feature=rule_create.feature,
            active=rule_create.active,
            datapoints=rule_create.datapoints,
            edge_cases=rule_create.edge_cases,
            edge_cases_json=rule_create.edge_cases_json,
            rule_logic=rule_create.rule_logic,
            rule_logic_json=rule_create.rule_logic_json,
        )
        group.rules.append(rule)
        self._save()
        return rule

    def get_rule(self, group_id: str, rule_id: str) -> BusinessRule | None:
        group = self.get_group(group_id)
        if not group:
            return None
        for rule in group.rules:
            if rule.id == rule_id:
                return rule
        return None

    def delete_rule(self, group_id: str, rule_id: str) -> bool:
        group = self.get_group(group_id)
        if not group:
            return False
        for i, rule in enumerate(group.rules):
            if rule.id == rule_id:
                del group.rules[i]
                self._save()
                return True
        return False

    def update_rule(self, group_id: str, rule_id: str, rule_update: CreateRule) -> BusinessRule | None:
        group = self.get_group(group_id)
        if not group:
            return None
        
        for i, rule in enumerate(group.rules):
            if rule.id == rule_id:
                # Update attributes while preserving id and created_at
                group.rules[i].name = rule_update.name
                group.rules[i].feature = rule_update.feature
                group.rules[i].active = rule_update.active
                group.rules[i].datapoints = rule_update.datapoints
                group.rules[i].edge_cases = rule_update.edge_cases
                group.rules[i].edge_cases_json = rule_update.edge_cases_json
                group.rules[i].rule_logic = rule_update.rule_logic
                group.rules[i].rule_logic_json = rule_update.rule_logic_json
                self._save()
                return group.rules[i]
        
        return None

    def update_datapoints(self, group_id: str, definitions) -> BusinessRuleGroup | None:
        group = self.get_group(group_id)
        if not group:
            return None
        existing = {definition.name: definition for definition in group.datapoint_definitions}
        for definition in definitions:
            existing[definition.name] = definition
        group.datapoint_definitions = list(existing.values())
        self._save()
        return group
