import React, { useEffect, useState } from 'react';
import { Plus } from 'lucide-react';

import { getGroup, updateRule } from '../api';
import type { Rule, RulePayload } from '../types';

interface RuleLibraryProps {
  groupId: string;
  selectedRuleId?: string | null;
  onSelectRule: (rule: Rule) => void;
  onCreateRule?: () => void;
  onRuleUpdated?: (rule: Rule) => void;
  onRuleStatusChanged?: (rule: Rule) => void;
  refreshKey?: number;
  className?: string;
}

export const RuleLibrary: React.FC<RuleLibraryProps> = ({
  groupId,
  selectedRuleId = null,
  onSelectRule,
  onCreateRule,
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
    <section className={`flex h-full min-h-0 flex-col bg-white dark:bg-gray-900 ${className}`}>
      <div className="border-b border-gray-200 bg-white/95 px-6 py-5 backdrop-blur dark:border-gray-800 dark:bg-gray-900/95">
        <h2 className="text-sm font-semibold text-gray-900 dark:text-gray-100">Rule Library</h2>
        <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">
          Scan the saved rules for this group, start a fresh rule, or open a stored rule to revise it.
        </p>
      </div>

      <div className="flex-1 overflow-y-auto p-6">
        <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
          {onCreateRule && (
            <button
              type="button"
              onClick={onCreateRule}
              className="group flex min-h-56 flex-col justify-between rounded-3xl border border-dashed border-blue-300 bg-blue-50/80 p-5 text-left transition-colors hover:bg-blue-100 dark:border-blue-800/70 dark:bg-blue-950/20 dark:hover:bg-blue-950/35"
            >
              <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-blue-600 text-white">
                <Plus size={22} />
              </div>
              <div>
                <h3 className="text-lg font-semibold text-blue-900 dark:text-blue-100">Create New Rule</h3>
                <p className="mt-2 text-sm text-blue-700 dark:text-blue-300">
                  Open the builder chat to translate a fresh policy into a stored rule.
                </p>
              </div>
            </button>
          )}

        {rules.length === 0 && (
          <div className="rounded-3xl border border-dashed border-gray-300 bg-gray-50 p-5 text-sm text-gray-500 dark:border-gray-700 dark:bg-gray-950/40 dark:text-gray-400">
            No saved rules in this group yet.
          </div>
        )}

        {rules.map((rule) => (
          <article
            key={rule.id}
            className={`rounded-3xl border p-5 transition-colors ${
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
                Open Rule
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
      </div>
    </section>
  );
};
