import type { RuleTranslation } from '../types';

function swapVarInJsonLogic(logic: unknown, oldVar: string, newVar: string): unknown {
  if (typeof logic === 'object' && logic !== null && !Array.isArray(logic)) {
    const obj = logic as Record<string, unknown>;
    if ('var' in obj && Object.keys(obj).length === 1 && obj['var'] === oldVar) {
      return { var: newVar };
    }
    const out: Record<string, unknown> = {};
    for (const [k, v] of Object.entries(obj)) out[k] = swapVarInJsonLogic(v, oldVar, newVar);
    return out;
  }
  if (Array.isArray(logic)) return logic.map((item) => swapVarInJsonLogic(item, oldVar, newVar));
  return logic;
}

/**
 * Replace all occurrences of *oldVar* with *newVar* in *text* using
 * word-boundary matching to avoid replacing substrings inside other variable
 * names.
 *
 * Example: replacing "amount" in "transaction_amount > 100" leaves it unchanged,
 * but "amount > 100 AND amount < 500" becomes "price > 100 AND price < 500".
 */
export function replaceVariableToken(text: string, oldVar: string, newVar: string): string {
  // Escape special regex chars in variable names
  const escapedOld = oldVar.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  // Use word boundaries (\b) to match only complete tokens
  const pattern = new RegExp(`\\b${escapedOld}\\b`, 'g');
  return text.replace(pattern, newVar);
}

export function swapVariableInResult(data: RuleTranslation, oldVar: string, newVar: string): RuleTranslation {
  return {
    ...data,
    datapoints: data.datapoints.map((dp) => (dp === oldVar ? newVar : dp)),
    rule_logic: replaceVariableToken(data.rule_logic, oldVar, newVar),
    rule_logic_json: swapVarInJsonLogic(data.rule_logic_json, oldVar, newVar) as Record<string, unknown>,
    edge_cases: data.edge_cases.map((ec) => replaceVariableToken(ec, oldVar, newVar)),
    edge_cases_json: (data.edge_cases_json ?? []).map((ec) => swapVarInJsonLogic(ec, oldVar, newVar) as Record<string, unknown>),
  };
}
