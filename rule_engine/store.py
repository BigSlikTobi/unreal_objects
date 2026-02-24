from .models import BusinessRule, BusinessRuleGroup, CreateRule, CreateRuleGroup

class RuleStore:
    def __init__(self):
        self.groups: dict[str, BusinessRuleGroup] = {}

    def create_group(self, group_create: CreateRuleGroup) -> BusinessRuleGroup:
        group = BusinessRuleGroup(
            name=group_create.name,
            description=group_create.description
        )
        self.groups[group.id] = group
        return group

    def list_groups(self) -> list[BusinessRuleGroup]:
        return list(self.groups.values())

    def get_group(self, group_id: str) -> BusinessRuleGroup | None:
        return self.groups.get(group_id)

    def delete_group(self, group_id: str) -> bool:
        if group_id in self.groups:
            del self.groups[group_id]
            return True
        return False

    def add_rule(self, group_id: str, rule_create: CreateRule) -> BusinessRule | None:
        group = self.get_group(group_id)
        if not group:
            return None
        rule = BusinessRule(
            name=rule_create.name,
            feature=rule_create.feature,
            datapoints=rule_create.datapoints,
            edge_cases=rule_create.edge_cases,
            rule_logic=rule_create.rule_logic
        )
        group.rules.append(rule)
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
                return True
        return False
