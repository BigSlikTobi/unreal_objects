import React, { useCallback, useEffect, useRef, useState } from 'react';
import { Bot, User, Check, Plus, FlaskConical, Code2, X, Wand2, ChevronDown } from 'lucide-react';
import { translateRule, createRule, getGroup, updateDatapointDefinitions, updateRule, ConceptMismatchError, fetchSchemas } from '../api';
import type { SchemaEntry } from '../api';
import { DatapointConfigurator } from './DatapointConfigurator';
import type { DatapointDefinition, LlmConfig, ProposedField, Rule, RulePayload, RuleTranslation } from '../types';

interface Message {
  id: string;
  role: 'assistant' | 'user';
  content: string;
  isRuleProposal?: boolean;
  ruleData?: RuleTranslation;
  isDatapointConfig?: boolean;
  newDatapoints?: string[];
  isSchemaExtensionOffer?: boolean;
  proposedField?: ProposedField;
}

interface EdgeCaseRow {
  condition: string;
  outcome: string;
}

interface ChatInterfaceProps {
  groupId: string;
  llmConfig: LlmConfig | null;
  selectedRule?: Rule | null;
  selectedRuleToken?: number;
  systemNotice?: string | null;
  systemNoticeToken?: number;
  onRuleCreated: (rule: Rule) => void;
  onStartTest: (rule: Rule, datapointDefs: DatapointDefinition[]) => void;
  onStopEditing?: () => void;
}

const OUTCOMES = ['APPROVE', 'ASK_FOR_APPROVAL', 'REJECT'] as const;
const MAIN_RULE_PATTERN = /^\s*IF\s+(.+?)\s+THEN\s+(APPROVE|ASK_FOR_APPROVAL|REJECT)(?:\s+ELSE\s+(APPROVE|ASK_FOR_APPROVAL|REJECT))?\s*$/i;
const EDGE_CASE_PATTERN = /^\s*IF\s+(.+?)\s+THEN\s+(APPROVE|ASK_FOR_APPROVAL|REJECT)\s*$/i;
const QUOTED_LITERAL_PATTERN = /("[^"]+"|'[^']+')/;

type SchemaMap = Record<string, { label: string; schema: Record<string, string> }>;

const outcomeColor = (value: string) => {
  if (value === 'APPROVE') return 'text-green-700 dark:text-green-400';
  if (value === 'REJECT') return 'text-red-600 dark:text-red-400';
  return 'text-amber-600 dark:text-amber-400';
};

interface OutcomeSelectProps {
  value: string;
  onChange: (v: string) => void;
  includeEmpty?: boolean;
}

const OutcomeSelect: React.FC<OutcomeSelectProps> = ({ value, onChange, includeEmpty }) => (
  <select
    value={value}
    onChange={(e) => onChange(e.target.value)}
    className={`bg-gray-100 dark:bg-gray-800 border border-gray-300 dark:border-gray-600 rounded-lg px-2 py-2 text-sm font-medium focus:ring-2 focus:ring-blue-500 focus:outline-none ${outcomeColor(value)}`}
  >
    {includeEmpty && <option value="">— none —</option>}
    {OUTCOMES.map((o) => (
      <option key={o} value={o} className={outcomeColor(o)}>
        {o}
      </option>
    ))}
  </select>
);

const renderQuotedLiteralPreview = (text: string) =>
  text.split(QUOTED_LITERAL_PATTERN).map((part, index) => {
    const isLiteral = /^["'].*["']$/.test(part);
    return isLiteral ? (
      <span
        key={`${part}-${index}`}
        className="bg-amber-100 dark:bg-amber-900/40 text-amber-700 dark:text-amber-300 px-0.5 rounded"
        title="Verify this matches what your agent sends"
      >
        {part}
      </span>
    ) : (
      part
    );
  });

interface SchemaExtensionOfferProps {
  proposedField: ProposedField;
  onAddAndRetry: (name: string, description: string) => void;
}

const SchemaExtensionOffer: React.FC<SchemaExtensionOfferProps> = ({ proposedField, onAddAndRetry }) => {
  const [fieldName, setFieldName] = useState(proposedField.name);
  const [fieldType, setFieldType] = useState(proposedField.type || 'number');
  const [submitted, setSubmitted] = useState(false);

  const handleSubmit = () => {
    if (!fieldName.trim() || submitted) return;
    setSubmitted(true);
    onAddAndRetry(fieldName.trim(), fieldType);
  };

  return (
    <div className="mt-2 w-full max-w-2xl bg-white dark:bg-gray-800 border border-amber-200 dark:border-amber-700/50 rounded-xl overflow-hidden shadow-sm">
      <div className="p-3 bg-amber-50 dark:bg-amber-900/20 border-b border-amber-200 dark:border-amber-700/50 flex items-center gap-2">
        <Plus size={15} className="text-amber-600 dark:text-amber-400" />
        <span className="text-sm font-semibold text-amber-800 dark:text-amber-300">
          Add this concept to your schema and retry
        </span>
      </div>
      <div className="p-4 space-y-3">
        <p className="text-xs text-gray-500 dark:text-gray-400">
          The concept wasn't found in the selected schema. Define it as a new field and the
          translator will retry with it available.
        </p>
        <div className="flex gap-2 items-end">
          <div className="flex-1">
            <label className="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">Field name</label>
            <input
              type="text"
              value={fieldName}
              onChange={(e) => setFieldName(e.target.value)}
              disabled={submitted}
              className="w-full bg-gray-100 dark:bg-gray-700 border border-gray-300 dark:border-gray-600 rounded-lg px-3 py-2 text-sm font-mono focus:ring-2 focus:ring-amber-400 focus:outline-none text-gray-900 dark:text-white disabled:opacity-50"
            />
          </div>
          <div className="w-28">
            <label className="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">Type</label>
            <select
              value={fieldType}
              onChange={(e) => setFieldType(e.target.value)}
              disabled={submitted}
              className="w-full bg-gray-100 dark:bg-gray-700 border border-gray-300 dark:border-gray-600 rounded-lg px-3 py-2 text-sm text-gray-700 dark:text-gray-300 focus:ring-2 focus:ring-amber-400 focus:outline-none disabled:opacity-50"
            >
              <option value="number">number</option>
              <option value="text">text</option>
              <option value="boolean">boolean</option>
            </select>
          </div>
          <button
            onClick={handleSubmit}
            disabled={!fieldName.trim() || submitted}
            className="flex items-center gap-1.5 px-3 py-2 bg-amber-500 hover:bg-amber-600 disabled:opacity-50 text-white text-sm font-medium rounded-lg transition-colors whitespace-nowrap"
          >
            <Check size={14} /> Add &amp; Retry
          </button>
        </div>
      </div>
    </div>
  );
};

/* ── Variable swap helper (client-side mirror of backend swap_variable_in_result) ── */
import { swapVariableInResult } from '../utils/variableSwap';

/* ── DatapointChip: clickable badge with schema-field dropdown ── */

interface DatapointChipProps {
  dp: string;
  schemaFields: Record<string, string> | null; // null ⟹ no schema active
  onSwap: (oldVar: string, newVar: string) => void;
}

const DatapointChip: React.FC<DatapointChipProps> = ({ dp, schemaFields, onSwap }) => {
  const [open, setOpen] = useState(false);
  const [creating, setCreating] = useState(false);
  const [newName, setNewName] = useState('');
  const ref = useRef<HTMLDivElement>(null);

  // Close dropdown on outside click
  useEffect(() => {
    if (!open) return;
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, [open]);

  // Build ranked list: schema fields sorted by name, current field on top
  const options = schemaFields
    ? Object.keys(schemaFields).sort((a, b) => {
        if (a === dp) return -1;
        if (b === dp) return 1;
        return a.localeCompare(b);
      })
    : [];

  const handleSelect = (field: string) => {
    if (field !== dp) onSwap(dp, field);
    setOpen(false);
    setCreating(false);
  };

  const handleCreate = () => {
    const trimmed = newName.trim().replace(/\s+/g, '_').toLowerCase();
    if (trimmed && trimmed !== dp) onSwap(dp, trimmed);
    setOpen(false);
    setCreating(false);
    setNewName('');
  };

  return (
    <div className="relative inline-block" ref={ref}>
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className="flex items-center gap-1 bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-400 px-2 py-1 rounded text-xs font-mono hover:bg-blue-200 dark:hover:bg-blue-800/40 transition-colors cursor-pointer"
        title="Click to change this datapoint"
      >
        {dp}
        <ChevronDown size={12} />
      </button>

      {open && (
        <div className="absolute z-50 mt-1 left-0 w-64 max-h-56 overflow-y-auto bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg shadow-lg text-xs">
          {options.length > 0 && options.map((field) => (
            <button
              key={field}
              type="button"
              onClick={() => handleSelect(field)}
              className={`w-full text-left px-3 py-2 hover:bg-blue-50 dark:hover:bg-blue-900/30 transition-colors ${
                field === dp ? 'font-bold text-blue-600 dark:text-blue-400 bg-blue-50 dark:bg-blue-900/20' : 'text-gray-700 dark:text-gray-300'
              }`}
            >
              <span className="font-mono">{field}</span>
              {schemaFields && (
                <span className="ml-2 text-gray-400 dark:text-gray-500 text-[10px]">
                  {schemaFields[field]}
                </span>
              )}
            </button>
          ))}

          <div className="border-t border-gray-200 dark:border-gray-700">
            {!creating ? (
              <button
                type="button"
                onClick={() => setCreating(true)}
                className="w-full text-left px-3 py-2 text-amber-600 dark:text-amber-400 hover:bg-amber-50 dark:hover:bg-amber-900/20 flex items-center gap-1"
              >
                <Plus size={12} /> Create new field
              </button>
            ) : (
              <div className="p-2 flex gap-1">
                <input
                  type="text"
                  value={newName}
                  onChange={(e) => setNewName(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && handleCreate()}
                  placeholder="new_field_name"
                  className="flex-1 bg-gray-100 dark:bg-gray-700 border border-gray-300 dark:border-gray-600 rounded px-2 py-1 text-xs font-mono focus:ring-1 focus:ring-amber-400 focus:outline-none text-gray-900 dark:text-white"
                  autoFocus
                />
                <button
                  type="button"
                  onClick={handleCreate}
                  disabled={!newName.trim()}
                  className="px-2 py-1 bg-amber-500 text-white rounded text-xs disabled:opacity-50"
                >
                  <Check size={12} />
                </button>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
};

export const ChatInterface: React.FC<ChatInterfaceProps> = ({
  groupId,
  llmConfig,
  selectedRule = null,
  selectedRuleToken = 0,
  systemNotice = null,
  systemNoticeToken = 0,
  onRuleCreated,
  onStartTest,
  onStopEditing,
}) => {
  const [messages, setMessages] = useState<Message[]>([{
    id: 'init',
    role: 'assistant',
    content: "Fill in the builder — set your condition and outcome, add edge cases, then click Translate.\n\n💡 About the Schema dropdown: schemas lock the AI to a pre-approved set of variable names so all your rules speak the same language. Without one, the LLM invents its own names — the same concept might become \"amount\" in one rule and \"transaction_amount\" in another, causing evaluation mismatches.\n\n• E-Commerce — for rules about orders, payments, cart, shipping, and user accounts\n• Finance — for rules about withdrawals, balances, loans, KYC, and AML risk scores\n• No schema — freeform, AI picks its own variable names\n\nPick the one that matches your domain, or start with No schema and switch later."
  }]);

  const [ruleName, setRuleName] = useState('');
  const [feature, setFeature] = useState('');
  const [selectedSchema, setSelectedSchema] = useState('');
  const [condition, setCondition] = useState('');
  const [thenOutcome, setThenOutcome] = useState('ASK_FOR_APPROVAL');
  const [elseOutcome, setElseOutcome] = useState('');
  const [edgeCaseRows, setEdgeCaseRows] = useState<EdgeCaseRow[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [datapointDefs, setDatapointDefs] = useState<DatapointDefinition[]>([]);
  const [editingRule, setEditingRule] = useState<Rule | null>(null);
  const [schemaExtensions, setSchemaExtensions] = useState<Record<string, string>>({});
  const [schemas, setSchemas] = useState<SchemaMap>({});

  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, isLoading]);

  useEffect(() => {
    fetchSchemas()
      .then((entries: SchemaEntry[]) => {
        const map: SchemaMap = {};
        for (const e of entries) {
          map[e.key] = { label: e.name, schema: e.schema };
        }
        setSchemas(map);
      })
      .catch(() => {/* schemas endpoint unavailable — dropdown stays empty */});
  }, []);

  useEffect(() => {
    getGroup(groupId)
      .then((group) => {
        setDatapointDefs(group.datapoint_definitions || []);
      })
      .catch(() => {});
  }, [groupId]);

  const clearBuilder = () => {
    setRuleName('');
    setFeature('');
    setSelectedSchema('');
    setCondition('');
    setThenOutcome('ASK_FOR_APPROVAL');
    setElseOutcome('');
    setEdgeCaseRows([]);
    setEditingRule(null);
  };

  const parseRuleLogic = (ruleLogic: string) => {
    const match = ruleLogic.match(MAIN_RULE_PATTERN);
    if (!match) {
      return {
        condition: '',
        thenOutcome: 'ASK_FOR_APPROVAL',
        elseOutcome: '',
      };
    }

    return {
      condition: match[1] ?? '',
      thenOutcome: match[2] ?? 'ASK_FOR_APPROVAL',
      elseOutcome: match[3] ?? '',
    };
  };

  const parseEdgeCases = (edgeCases: string[]): EdgeCaseRow[] =>
    edgeCases
      .map((edgeCase) => {
        const match = edgeCase.match(EDGE_CASE_PATTERN);
        if (!match) return null;
        return {
          condition: match[1] ?? '',
          outcome: match[2] ?? 'REJECT',
        };
      })
      .filter((row): row is EdgeCaseRow => row !== null);

  const startEditingRule = useCallback((rule: Rule) => {
    const parsedRule = parseRuleLogic(rule.rule_logic ?? '');
    setEditingRule(rule);
    setRuleName(rule.name ?? '');
    setFeature(rule.feature ?? '');
    setSelectedSchema('');
    setCondition(parsedRule.condition);
    setThenOutcome(parsedRule.thenOutcome);
    setElseOutcome(parsedRule.elseOutcome);
    setEdgeCaseRows(parseEdgeCases(rule.edge_cases ?? []));
    setMessages(prev => [...prev, {
      id: Date.now().toString(),
      role: 'assistant',
      content: `Editing '${rule.name}'. Update the builder, then translate and save to update the existing rule.`,
    }]);
  }, []);

  useEffect(() => {
    if (selectedRule && selectedRule.id !== editingRule?.id) {
      startEditingRule(selectedRule);
    }
  }, [selectedRule, selectedRuleToken, startEditingRule, editingRule?.id]);

  useEffect(() => {
    if (!systemNotice) {
      return;
    }
    setMessages((prev) => [
      ...prev,
      {
        id: `notice-${systemNoticeToken}-${Date.now()}`,
        role: 'assistant',
        content: systemNotice,
      },
    ]);
  }, [systemNotice, systemNoticeToken]);

  const updateEdgeCaseRow = (i: number, field: keyof EdgeCaseRow, value: string) => {
    setEdgeCaseRows(prev => prev.map((row, idx) => idx === i ? { ...row, [field]: value } : row));
  };

  const removeEdgeCaseRow = (i: number) => {
    setEdgeCaseRows(prev => prev.filter((_, idx) => idx !== i));
  };

  const buildDisplayText = (): string => {
    const header = [
      ruleName && `"${ruleName}"`,
      feature && `[${feature}]`,
      selectedSchema && `{${schemas[selectedSchema]?.label}}`,
    ].filter(Boolean).join(' ');
    let text = header ? `${header}\n` : '';
    text += `IF ${condition || '…'} THEN ${thenOutcome}`;
    if (elseOutcome) text += ` ELSE ${elseOutcome}`;
    for (const ec of edgeCaseRows) {
      text += `\n↳ EDGE  IF ${ec.condition || '…'} THEN ${ec.outcome}`;
    }
    return text;
  };

  const buildPrompt = (): string => {
    let main = `IF ${condition} THEN ${thenOutcome}`;
    if (elseOutcome) main += ` ELSE ${elseOutcome}`;
    let prompt = `Translate this structured rule into JSON Logic format.\nMain rule: ${main}`;
    if (edgeCaseRows.length > 0) {
      prompt += `\nEdge cases (each a separate entry in edge_cases):`;
      for (const ec of edgeCaseRows) {
        prompt += `\n- IF ${ec.condition} THEN ${ec.outcome}`;
      }
    }
    return prompt;
  };

  const handleTranslate = async (extraSchema?: Record<string, string>) => {
    if (!condition.trim() || isLoading || !llmConfig) return;

    const displayText = buildDisplayText();
    const userMsg: Message = { id: Date.now().toString(), role: 'user', content: displayText };
    setMessages(prev => [...prev, userMsg]);
    setIsLoading(true);

    try {
      const res = await translateRule({
        natural_language: buildPrompt(),
        feature: feature.trim() || 'General',
        name: ruleName.trim() || `Rule ${Date.now()}`,
        provider: llmConfig.provider,
        model: llmConfig.model,
        api_key: llmConfig.api_key,
        context_schema: selectedSchema
          ? { ...schemas[selectedSchema].schema, ...schemaExtensions, ...extraSchema }
          : undefined,
        datapoint_definitions: datapointDefs
      });

      const assistantMsg: Message = {
        id: (Date.now() + 1).toString(),
        role: 'assistant',
        content: `Here is the translated rule:`,
        isRuleProposal: true,
        ruleData: res,
      };

      const newMessages: Message[] = [assistantMsg];

      // Compute datapoints not yet defined
      const newDatapoints = (res.datapoints || []).filter(
        (dp: string) => !datapointDefs.find(d => d.name === dp)
      );

      if (newDatapoints.length > 0) {
        newMessages.push({
          id: (Date.now() + 2).toString(),
          role: 'assistant',
          content: '',
          isDatapointConfig: true,
          newDatapoints,
        });
      } else {
        const stringLiterals = extractStringLiterals(res);
        if (stringLiterals.length > 0) {
          newMessages.push({
            id: (Date.now() + 2).toString(),
            role: 'assistant',
            content: `⚠️ String value check: this rule compares against ${stringLiterals.map(l => `"${l}"`).join(', ')}. Make sure your agent sends these exact values. If not, describe the correction.`,
          });
        }
      }

      setMessages(prev => [...prev, ...newMessages]);
    } catch (err: unknown) {
      if (err instanceof ConceptMismatchError && err.proposedField) {
        setMessages(prev => [...prev, {
          id: (Date.now() + 1).toString(),
          role: 'assistant',
          content: err.message,
          isSchemaExtensionOffer: true,
          proposedField: err.proposedField,
        }]);
      } else {
        setMessages(prev => [...prev, {
          id: (Date.now() + 1).toString(),
          role: 'assistant',
          content: `Error translating rule: ${err instanceof Error ? err.message : 'Unknown error'}`
        }]);
      }
    } finally {
      setIsLoading(false);
    }
  };

  const handleAddFieldAndRetry = (fieldName: string, fieldDesc: string) => {
    const extra = { [fieldName]: fieldDesc };
    setSchemaExtensions(prev => ({ ...prev, ...extra }));
    handleTranslate(extra);
  };

  const handleSwapVariable = (msgId: string, oldVar: string, newVar: string) => {
    setMessages(prev => prev.map(msg => {
      if (msg.id !== msgId || !msg.ruleData) return msg;
      return { ...msg, ruleData: swapVariableInResult(msg.ruleData, oldVar, newVar) };
    }));
  };

  const handleDatapointSave = async (newDefs: DatapointDefinition[]) => {
    try {
      await updateDatapointDefinitions(groupId, newDefs);
      setDatapointDefs(prev => {
        const existing = new Map(prev.map(d => [d.name, d]));
        newDefs.forEach(d => existing.set(d.name, d));
        return Array.from(existing.values());
      });
    } catch (err: unknown) {
      setMessages(prev => [...prev, {
        id: Date.now().toString(),
        role: 'assistant',
        content: `Error saving datapoint definitions: ${err instanceof Error ? err.message : 'Unknown error'}`
      }]);
    }
  };

  const handleAcceptRule = async (ruleData: RuleTranslation) => {
    try {
      setIsLoading(true);
      const payload: RulePayload = {
        name: ruleName.trim() || editingRule?.name || ruleData.name || `Rule ${Date.now()}`,
        feature: feature.trim() || editingRule?.feature || 'General',
        active: editingRule?.active ?? true,
        ...ruleData
      };
      const saved = editingRule
        ? await updateRule(groupId, editingRule.id, payload)
        : await createRule(groupId, payload);
      setEditingRule(saved);
      setRuleName(saved.name);
      setFeature(saved.feature);

      setMessages(prev => [...prev, {
        id: Date.now().toString(),
        role: 'assistant',
        content: editingRule
          ? `✅ Rule '${saved.name}' updated successfully! You are still editing it.`
          : `✅ Rule '${saved.name}' created and saved successfully! You are now editing the saved rule.`
      }]);
      onRuleCreated(saved);
    } catch (err: unknown) {
       setMessages(prev => [...prev, {
        id: Date.now().toString(),
        role: 'assistant',
        content: `Error saving rule: ${err instanceof Error ? err.message : 'Unknown error'}`
      }]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleSaveAndTest = async (ruleData: RuleTranslation) => {
    try {
      setIsLoading(true);
      const payload: RulePayload = {
        name: ruleName.trim() || editingRule?.name || ruleData.name || `Rule ${Date.now()}`,
        feature: feature.trim() || editingRule?.feature || 'General',
        active: editingRule?.active ?? true,
        ...ruleData,
      };
      const saved = editingRule
        ? await updateRule(groupId, editingRule.id, payload)
        : await createRule(groupId, payload);
      setEditingRule(saved);
      setRuleName(saved.name);
      setFeature(saved.feature);
      setMessages(prev => [...prev, {
        id: Date.now().toString(),
        role: 'assistant',
        content: editingRule
          ? `✅ Rule '${saved.name}' updated. Opening test console while you stay in edit mode.`
          : `✅ Rule '${saved.name}' saved. Opening test console while you stay in edit mode.`,
      }]);
      onRuleCreated(saved);
      onStartTest(saved, datapointDefs);
    } catch (err: unknown) {
      setMessages(prev => [...prev, {
        id: Date.now().toString(),
        role: 'assistant',
        content: `Error saving rule: ${err instanceof Error ? err.message : 'Unknown error'}`,
      }]);
    } finally {
      setIsLoading(false);
    }
  };

  const extractStringLiterals = (ruleData: RuleTranslation): string[] => {
    const outcomes = new Set(['APPROVE', 'REJECT', 'ASK_FOR_APPROVAL']);
    const text = [ruleData.rule_logic || '', ...(ruleData.edge_cases || [])].join(' ');
    const regex = /"([^"]+)"|'([^']+)'/g;
    const found = new Set<string>();
    let m;
    while ((m = regex.exec(text)) !== null) {
      const val = m[1] || m[2];
      if (!outcomes.has(val.toUpperCase())) found.add(val);
    }
    return [...found];
  };

  const handleAddEdgeCase = () => {
    setEdgeCaseRows(prev => [...prev, { condition: '', outcome: 'REJECT' }]);
    setTimeout(scrollToBottom, 50);
  };

  const handleOptimizeRule = () => {
    setMessages(prev => [...prev, {
      id: Date.now().toString(),
      role: 'assistant',
      content: "Update the condition or outcome in the builder and click Translate to regenerate."
    }]);
    setTimeout(scrollToBottom, 50);
  };

  const handleRefuseRule = () => {
    clearBuilder();
    setMessages(prev => [...prev, {
      id: Date.now().toString(),
      role: 'assistant',
      content: "Rule discarded. Fill in the builder to start fresh."
    }]);
  };

  const handleStopEditing = () => {
    clearBuilder();
    onStopEditing?.();
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleTranslate();
    }
  };

  return (
    <div className="flex flex-col h-full bg-white dark:bg-gray-900 transition-colors">
      <div className="border-b border-gray-200 bg-white px-4 py-4 dark:border-gray-800 dark:bg-gray-900 md:px-6">
        <div className="mx-auto max-w-5xl rounded-3xl border border-gray-200 bg-gray-50/70 p-5 shadow-sm dark:border-gray-800 dark:bg-gray-950/40">
          <div className="mb-4">
            <h2 className="text-lg font-semibold text-gray-900 dark:text-gray-100">Rule Builder</h2>
            <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
              Define the rule structure here, then use the chat to review translations and save updates.
            </p>
          </div>
          {!llmConfig ? (
            <div className="w-full p-3 text-center text-sm text-amber-600 dark:text-amber-400 bg-amber-50 dark:bg-amber-900/20 rounded-xl border border-amber-200 dark:border-amber-800/50">
              Please configure LLM Provider settings in the sidebar to start creating rules.
            </div>
          ) : (
            <div className="space-y-2">
              {editingRule && (
                <div className="flex items-center justify-between gap-3 rounded-xl border border-blue-200 bg-blue-50 px-3 py-2 text-sm text-blue-800 dark:border-blue-900/40 dark:bg-blue-900/20 dark:text-blue-200">
                  <span>Editing stored rule: <strong>{editingRule.name}</strong></span>
                  <button
                    onClick={handleStopEditing}
                    className="rounded-md px-2 py-1 text-xs font-medium text-blue-700 hover:bg-blue-100 dark:text-blue-300 dark:hover:bg-blue-900/30"
                  >
                    Stop Editing
                  </button>
                </div>
              )}

              {/* Metadata row: name, feature, schema */}
              <div className="flex items-center gap-2">
                <input
                  type="text"
                  value={ruleName}
                  onChange={(e) => setRuleName(e.target.value)}
                  onKeyDown={handleKeyDown}
                  placeholder="Rule name"
                  className="w-40 bg-gray-100 dark:bg-gray-800 border border-gray-300 dark:border-gray-600 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-blue-500 focus:outline-none text-gray-900 dark:text-white placeholder-gray-400"
                />
                <input
                  type="text"
                  value={feature}
                  onChange={(e) => setFeature(e.target.value)}
                  onKeyDown={handleKeyDown}
                  placeholder="Feature (e.g. Fraud Check)"
                  className="flex-1 bg-gray-100 dark:bg-gray-800 border border-gray-300 dark:border-gray-600 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-blue-500 focus:outline-none text-gray-900 dark:text-white placeholder-gray-400"
                />
                <select
                  value={selectedSchema}
                  onChange={(e) => setSelectedSchema(e.target.value)}
                  className="bg-gray-100 dark:bg-gray-800 border border-gray-300 dark:border-gray-600 rounded-lg px-3 py-2 text-sm text-gray-700 dark:text-gray-300 focus:ring-2 focus:ring-blue-500 focus:outline-none"
                >
                  <option value="">No schema</option>
                  {Object.entries(schemas).map(([key, s]) => (
                    <option key={key} value={key}>{s.label}</option>
                  ))}
                </select>
              </div>

              {/* Main rule row */}
              <div className="flex items-center gap-2">
                <span className="text-xs font-semibold text-gray-500 dark:text-gray-400 w-4 shrink-0">IF</span>
                <input
                  type="text"
                  value={condition}
                  onChange={(e) => setCondition(e.target.value)}
                  onKeyDown={handleKeyDown}
                  placeholder="e.g. amount > 500"
                  className="flex-1 bg-gray-100 dark:bg-gray-800 border border-gray-300 dark:border-gray-600 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-blue-500 focus:outline-none text-gray-900 dark:text-white placeholder-gray-400"
                />
                <span className="text-xs font-semibold text-gray-500 dark:text-gray-400 shrink-0">THEN</span>
                <OutcomeSelect value={thenOutcome} onChange={setThenOutcome} />
                <span className="text-xs font-semibold text-gray-500 dark:text-gray-400 shrink-0">ELSE</span>
                <OutcomeSelect value={elseOutcome} onChange={setElseOutcome} includeEmpty />
              </div>

              {/* Edge case rows */}
              {edgeCaseRows.map((row, i) => (
                <div key={i} className="flex items-center gap-2 pl-3 border-l-2 border-amber-400">
                  <span className="text-xs font-semibold text-gray-500 dark:text-gray-400 w-4 shrink-0">IF</span>
                  <input
                    type="text"
                    value={row.condition}
                    onChange={(e) => updateEdgeCaseRow(i, 'condition', e.target.value)}
                    onKeyDown={handleKeyDown}
                    placeholder="e.g. open_bills_count > 10"
                    className="flex-1 bg-gray-100 dark:bg-gray-800 border border-amber-300 dark:border-amber-700/60 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-amber-400 focus:outline-none text-gray-900 dark:text-white placeholder-gray-400"
                  />
                  <span className="text-xs font-semibold text-gray-500 dark:text-gray-400 shrink-0">THEN</span>
                  <OutcomeSelect value={row.outcome} onChange={(v) => updateEdgeCaseRow(i, 'outcome', v)} />
                  <button
                    onClick={() => removeEdgeCaseRow(i)}
                    className="p-1.5 rounded-md text-gray-400 hover:text-red-500 hover:bg-red-50 dark:hover:bg-red-900/20 transition-colors"
                    title="Remove edge case"
                  >
                    <X size={14} />
                  </button>
                </div>
              ))}

              {/* Bottom bar */}
              <div className="flex items-center justify-between pt-1">
                <button
                  onClick={handleAddEdgeCase}
                  className="flex items-center gap-1.5 px-3 py-1.5 text-sm text-gray-600 dark:text-gray-400 hover:text-blue-600 dark:hover:text-blue-400 hover:bg-blue-50 dark:hover:bg-blue-900/20 rounded-lg transition-colors"
                >
                  <Plus size={15} /> Add Edge Case
                </button>
                <button
                  onClick={() => handleTranslate()}
                  disabled={!condition.trim() || isLoading}
                  className="flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 disabled:opacity-50 disabled:hover:bg-blue-600 text-white text-sm font-medium rounded-lg transition-colors"
                >
                  <Wand2 size={15} /> Translate with AI
                </button>
              </div>
            </div>
          )}
          <div className="text-center mt-2 text-xs text-gray-400 dark:text-gray-500">
            Unreal Objects Rule Maker can make mistakes. Verify before applying.
          </div>
        </div>
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto p-4 md:p-6">
        <div className="mx-auto max-w-5xl space-y-4">
          <div>
            <h2 className="text-lg font-semibold text-gray-900 dark:text-gray-100">Chat Context</h2>
            <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
              Review assistant guidance, translated rule output, and save or test actions for the active rule.
            </p>
          </div>

          {messages.map((msg) => (
            <div key={msg.id} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
              <div className={`flex gap-4 max-w-3xl ${msg.role === 'user' ? 'flex-row-reverse' : 'flex-row'}`}>
                <div className={`w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0 ${
                  msg.role === 'user' ? 'bg-blue-600 text-white' : 'bg-emerald-500 text-white'
                }`}>
                  {msg.role === 'user' ? <User size={18} /> : <Bot size={18} />}
                </div>

                <div className={`flex flex-col gap-2 ${msg.role === 'user' ? 'items-end' : 'items-start'}`}>
                  {msg.content && (
                    <div className={`px-4 py-3 rounded-2xl ${
                      msg.role === 'user'
                        ? 'bg-blue-600 text-white rounded-tr-sm'
                        : 'bg-gray-100 dark:bg-gray-800 text-gray-800 dark:text-gray-200 rounded-tl-sm'
                    }`}>
                      <p className="whitespace-pre-wrap">{msg.content}</p>
                    </div>
                  )}

                  {msg.isDatapointConfig && msg.newDatapoints && (
                    <DatapointConfigurator
                      newDatapoints={msg.newDatapoints}
                      onSave={handleDatapointSave}
                    />
                  )}

                  {msg.isSchemaExtensionOffer && msg.proposedField && (
                    <SchemaExtensionOffer
                      proposedField={msg.proposedField}
                      onAddAndRetry={handleAddFieldAndRetry}
                    />
                  )}

                  {msg.isRuleProposal && msg.ruleData && (
                    <div className="mt-2 w-full max-w-2xl bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-xl overflow-hidden shadow-sm">
                      <div className="p-4 border-b border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-900/50 flex justify-between items-center">
                        <h4 className="font-semibold text-gray-800 dark:text-gray-200 flex items-center gap-2">
                          <Code2 size={16} className="text-blue-500" />
                          Proposed Logic
                        </h4>
                      </div>
                      <div className="p-4 space-y-4 text-sm text-gray-600 dark:text-gray-300">
                        <div>
                          <span className="font-semibold text-gray-800 dark:text-gray-200 block mb-1">Datapoints Extracted:</span>
                          <div className="flex flex-wrap gap-2">
                            {msg.ruleData.datapoints?.map((dp: string) => (
                              <DatapointChip
                                key={dp}
                                dp={dp}
                                schemaFields={
                                  selectedSchema
                                    ? { ...schemas[selectedSchema].schema, ...schemaExtensions }
                                    : null
                                }
                                onSwap={(oldVar, newVar) => handleSwapVariable(msg.id, oldVar, newVar)}
                              />
                            ))}
                          </div>
                        </div>

                        {msg.ruleData.edge_cases?.length > 0 && (
                          <div>
                            <span className="font-semibold text-gray-800 dark:text-gray-200 block mb-1">Edge Cases:</span>
                            <ul className="list-disc pl-4 space-y-1">
                              {msg.ruleData.edge_cases.map((ec: string, i: number) => (
                                <li key={i} className="font-mono text-xs">
                                  {renderQuotedLiteralPreview(ec)}
                                </li>
                              ))}
                            </ul>
                          </div>
                        )}

                        <div>
                          <span className="font-semibold text-gray-800 dark:text-gray-200 block mb-1">Main Rule Logic:</span>
                          <p className="font-mono bg-gray-50 dark:bg-gray-900 p-2 rounded text-xs overflow-x-auto">
                            {renderQuotedLiteralPreview(msg.ruleData.rule_logic)}
                          </p>
                        </div>
                      </div>

                      <div className="p-3 bg-gray-50 dark:bg-gray-900/50 border-t border-gray-200 dark:border-gray-700 flex flex-wrap gap-2">
                        <button
                          onClick={handleRefuseRule}
                          className="flex items-center gap-1.5 px-3 py-1.5 bg-red-50 hover:bg-red-100 dark:bg-red-900/20 dark:hover:bg-red-900/30 text-red-600 dark:text-red-400 rounded-md text-sm font-medium transition-colors border border-red-200 dark:border-red-800/50"
                        >
                          <X size={16} /> Refuse
                        </button>
                        <button
                          onClick={handleAddEdgeCase}
                          className="flex items-center gap-1.5 px-3 py-1.5 bg-gray-200 hover:bg-gray-300 dark:bg-gray-700 dark:hover:bg-gray-600 text-gray-800 dark:text-gray-200 rounded-md text-sm font-medium transition-colors"
                        >
                          <Plus size={16} /> Add Edge Case
                        </button>
                        <button
                          onClick={handleOptimizeRule}
                          className="flex items-center gap-1.5 px-3 py-1.5 bg-amber-50 hover:bg-amber-100 dark:bg-amber-900/20 dark:hover:bg-amber-900/30 text-amber-700 dark:text-amber-400 rounded-md text-sm font-medium transition-colors border border-amber-200 dark:border-amber-800/40"
                        >
                          <Wand2 size={16} /> Optimize
                        </button>
                        <button
                          onClick={() => handleAcceptRule(msg.ruleData!)}
                          className="flex items-center gap-1.5 px-3 py-1.5 bg-green-600 hover:bg-green-700 text-white rounded-md text-sm font-medium transition-colors ml-auto"
                        >
                          <Check size={16} /> Accept & Save
                        </button>
                        <button
                          onClick={() => handleSaveAndTest(msg.ruleData!)}
                          className="flex items-center gap-1.5 px-3 py-1.5 bg-purple-100 hover:bg-purple-200 dark:bg-purple-900/30 dark:hover:bg-purple-800/40 text-purple-700 dark:text-purple-300 rounded-md text-sm font-medium transition-colors"
                        >
                          <FlaskConical size={16} /> Save & Test
                        </button>
                      </div>
                    </div>
                  )}
                </div>
              </div>
            </div>
          ))}

          {isLoading && (
            <div className="flex justify-start">
              <div className="flex gap-4 max-w-3xl flex-row">
                <div className="w-8 h-8 rounded-full bg-emerald-500 text-white flex items-center justify-center flex-shrink-0">
                  <Bot size={18} />
                </div>
                <div className="px-4 py-3 rounded-2xl bg-gray-100 dark:bg-gray-800 text-gray-800 dark:text-gray-200 rounded-tl-sm flex gap-2 items-center">
                  <div className="w-2 h-2 bg-gray-400 dark:bg-gray-500 rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
                  <div className="w-2 h-2 bg-gray-400 dark:bg-gray-500 rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
                  <div className="w-2 h-2 bg-gray-400 dark:bg-gray-500 rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
                </div>
              </div>
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>
      </div>
    </div>
  );
};
