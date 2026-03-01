import React, { useEffect, useState } from 'react';

import { getGroup, updateRule } from '../api';
import type { Rule, RulePayload } from '../types';

interface RuleLibraryProps {
  groupId: string;
  selectedRuleId?: string | null;
  onSelectRule: (rule: Rule) => void;
  onRuleUpdated?: (rule: Rule) => void;
  onRuleStatusChanged?: (rule: Rule) => void;
  refreshKey?: number;
  className?: string;
}

export const RuleLibrary: React.FC<RuleLibraryProps> = ({
  groupId,
  selectedRuleId = null,
  onSelectRule,
  onRuleUpdated,
  onRuleStatusChanged,
  refreshKey = 0,
  className = '',
}) => {
  const [rules, setRules] = useState<Rule[]>([]);

  useEffect(() => {
    getGroup(groupId)
      .then((group) => {
        setRules(group.rules || []);
      })
      .catch(() => {
        setRules([]);
      });
  }, [groupId, refreshKey]);

  const upsertRule = (rule: Rule) => {
    setRules((prev) => prev.map((item) => (item.id === rule.id ? rule : item)));
  };

  const toRulePayload = (rule: Rule, overrides?: Partial<RulePayload>): RulePayload => ({
    name: rule.name,
    feature: rule.feature,
    active: rule.active ?? true,
    datapoints: rule.datapoints ?? [],
    edge_cases: rule.edge_cases ?? [],
    edge_cases_json: rule.edge_cases_json ?? [],
    rule_logic: rule.rule_logic ?? '',
    rule_logic_json: rule.rule_logic_json ?? {},
    ...overrides,
  });

  const handleToggleRule = async (rule: Rule) => {
    const nextActive = !(rule.active ?? true);
    const updated = await updateRule(groupId, rule.id, toRulePayload(rule, { active: nextActive }));
    const normalizedRule = {
      ...rule,
      ...updated,
      active: typeof updated?.active === 'boolean' ? updated.active : nextActive,
    };
    upsertRule(normalizedRule);
    onRuleUpdated?.(normalizedRule);
    onRuleStatusChanged?.(normalizedRule);
  };

  return (
    <aside className={`flex h-full min-h-0 flex-col border-l border-gray-200 bg-gray-50/80 dark:border-gray-800 dark:bg-gray-900/60 ${className}`}>
      <div className="sticky top-0 z-10 border-b border-gray-200 px-4 py-4 dark:border-gray-800 bg-gray-50/95 dark:bg-gray-900/95 backdrop-blur">
        <h2 className="text-sm font-semibold text-gray-900 dark:text-gray-100">Rule Library</h2>
        <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">
          Review saved rules, deactivate them without deleting the record, or load one into the builder.
        </p>
      </div>

      <div className="flex-1 space-y-3 overflow-y-auto p-4">
        {rules.length === 0 && (
          <div className="rounded-2xl border border-dashed border-gray-300 bg-white/80 p-4 text-sm text-gray-500 dark:border-gray-700 dark:bg-gray-950/40 dark:text-gray-400">
            No saved rules in this group yet.
          </div>
        )}

        {rules.map((rule) => (
          <article
            key={rule.id}
            className={`rounded-2xl border p-4 transition-colors ${
              selectedRuleId === rule.id
                ? 'border-blue-300 bg-blue-50 dark:border-blue-700 dark:bg-blue-950/30'
                : rule.active !== false
                  ? 'border-emerald-200 bg-white dark:border-emerald-900/40 dark:bg-gray-950/60'
                  : 'border-amber-200 bg-amber-50/80 dark:border-amber-900/40 dark:bg-amber-950/10'
            }`}
          >
            <div className="flex items-start justify-between gap-3">
              <div className="min-w-0">
                <div className="flex flex-wrap items-center gap-2">
                  <h3 className="text-sm font-semibold text-gray-900 dark:text-gray-100">{rule.name}</h3>
                  <span
                    className={`rounded-full px-2 py-0.5 text-[11px] font-semibold uppercase tracking-wide ${
                      rule.active !== false
                        ? 'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-300'
                        : 'bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-300'
                    }`}
                  >
                    {rule.active !== false ? 'Active' : 'Inactive'}
                  </span>
                </div>
                {rule.feature && (
                  <p className="mt-1 text-xs font-medium text-blue-700 dark:text-blue-300">{rule.feature}</p>
                )}
                <p className="mt-3 text-xs font-mono text-gray-600 dark:text-gray-300">{rule.rule_logic}</p>
                {rule.edge_cases?.length > 0 && (
                  <ul className="mt-3 space-y-1 text-xs text-gray-500 dark:text-gray-400">
                    {rule.edge_cases.map((edgeCase: string) => (
                      <li key={edgeCase}>↳ {edgeCase}</li>
                    ))}
                  </ul>
                )}
              </div>
            </div>

            <div className="mt-4 flex flex-wrap gap-2">
              <button
                onClick={() => onSelectRule(rule)}
                className="rounded-lg border border-blue-200 bg-blue-50 px-3 py-1.5 text-sm font-medium text-blue-700 transition-colors hover:bg-blue-100 dark:border-blue-900/40 dark:bg-blue-900/20 dark:text-blue-300 dark:hover:bg-blue-900/30"
              >
                Use in Builder
              </button>
              <button
                onClick={() => handleToggleRule(rule)}
                className={`rounded-lg border px-3 py-1.5 text-sm font-medium transition-colors ${
                  rule.active !== false
                    ? 'border-amber-200 bg-amber-50 text-amber-700 hover:bg-amber-100 dark:border-amber-900/40 dark:bg-amber-900/20 dark:text-amber-300 dark:hover:bg-amber-900/30'
                    : 'border-emerald-200 bg-emerald-50 text-emerald-700 hover:bg-emerald-100 dark:border-emerald-900/40 dark:bg-emerald-900/20 dark:text-emerald-300 dark:hover:bg-emerald-900/30'
                }`}
              >
                {rule.active !== false ? 'Deactivate' : 'Reactivate'}
              </button>
            </div>
          </article>
        ))}
      </div>
    </aside>
  );
};
