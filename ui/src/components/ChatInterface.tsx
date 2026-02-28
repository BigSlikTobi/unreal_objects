import React, { useState, useRef, useEffect } from 'react';
import { Bot, User, Check, Plus, FlaskConical, Code2, X, Wand2 } from 'lucide-react';
import { translateRule, createRule, getGroup, updateDatapointDefinitions } from '../api';
import { DatapointConfigurator } from './DatapointConfigurator';
import type { DatapointDefinition } from './DatapointConfigurator';

interface Message {
  id: string;
  role: 'assistant' | 'user';
  content: string;
  isRuleProposal?: boolean;
  ruleData?: any;
  isDatapointConfig?: boolean;
  newDatapoints?: string[];
}

interface EdgeCaseRow {
  condition: string;
  outcome: string;
}

interface ChatInterfaceProps {
  groupId: string;
  llmConfig: any;
  onRuleCreated: (rule: any) => void;
  onStartTest: (rule: any, datapointDefs: DatapointDefinition[]) => void;
}

const OUTCOMES = ['APPROVE', 'ASK_FOR_APPROVAL', 'REJECT'] as const;

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

export const ChatInterface: React.FC<ChatInterfaceProps> = ({
  groupId,
  llmConfig,
  onRuleCreated,
  onStartTest
}) => {
  const [messages, setMessages] = useState<Message[]>([{
    id: 'init',
    role: 'assistant',
    content: "Fill in the builder below — set your condition and outcome, add edge cases, then click Translate."
  }]);

  const [condition, setCondition] = useState('');
  const [thenOutcome, setThenOutcome] = useState('ASK_FOR_APPROVAL');
  const [elseOutcome, setElseOutcome] = useState('');
  const [edgeCaseRows, setEdgeCaseRows] = useState<EdgeCaseRow[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [datapointDefs, setDatapointDefs] = useState<DatapointDefinition[]>([]);

  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, isLoading]);

  // Hydrate datapoint definitions when group changes
  useEffect(() => {
    getGroup(groupId)
      .then((group) => {
        setDatapointDefs(group.datapoint_definitions || []);
      })
      .catch(() => {});
  }, [groupId]);

  const clearBuilder = () => {
    setCondition('');
    setThenOutcome('ASK_FOR_APPROVAL');
    setElseOutcome('');
    setEdgeCaseRows([]);
  };

  const updateEdgeCaseRow = (i: number, field: keyof EdgeCaseRow, value: string) => {
    setEdgeCaseRows(prev => prev.map((row, idx) => idx === i ? { ...row, [field]: value } : row));
  };

  const removeEdgeCaseRow = (i: number) => {
    setEdgeCaseRows(prev => prev.filter((_, idx) => idx !== i));
  };

  const buildDisplayText = (): string => {
    let text = `IF ${condition || '…'} THEN ${thenOutcome}`;
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

  const handleTranslate = async () => {
    if (!condition.trim() || isLoading) return;

    const displayText = buildDisplayText();
    const userMsg: Message = { id: Date.now().toString(), role: 'user', content: displayText };
    setMessages(prev => [...prev, userMsg]);
    setIsLoading(true);

    try {
      const res = await translateRule({
        natural_language: buildPrompt(),
        feature: "General",
        name: `Rule ${Date.now()}`,
        provider: llmConfig.provider,
        model: llmConfig.model,
        api_key: llmConfig.api_key,
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
            content: `⚠️ String value check: this rule compares against ${stringLiterals.map(l => `"${l}"`).join(', ')}. Make sure your agent sends these exact values. If not, describe the correction below.`,
          });
        }
      }

      setMessages(prev => [...prev, ...newMessages]);
    } catch (err: any) {
      setMessages(prev => [...prev, {
        id: (Date.now() + 1).toString(),
        role: 'assistant',
        content: `Error translating rule: ${err.message}`
      }]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleDatapointSave = async (newDefs: DatapointDefinition[]) => {
    try {
      await updateDatapointDefinitions(groupId, newDefs);
      setDatapointDefs(prev => {
        const existing = new Map(prev.map(d => [d.name, d]));
        newDefs.forEach(d => existing.set(d.name, d));
        return Array.from(existing.values());
      });
    } catch (err: any) {
      setMessages(prev => [...prev, {
        id: Date.now().toString(),
        role: 'assistant',
        content: `Error saving datapoint definitions: ${err.message}`
      }]);
    }
  };

  const handleAcceptRule = async (ruleData: any) => {
    try {
      setIsLoading(true);
      const created = await createRule(groupId, {
          name: ruleData.name || `Rule ${Date.now()}`,
          feature: "General",
          ...ruleData
      });

      setMessages(prev => [...prev, {
        id: Date.now().toString(),
        role: 'assistant',
        content: `✅ Rule '${created.name}' created and saved successfully!`
      }]);
      clearBuilder();
      onRuleCreated(created);
    } catch (err: any) {
       setMessages(prev => [...prev, {
        id: Date.now().toString(),
        role: 'assistant',
        content: `Error saving rule: ${err.message}`
      }]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleSaveAndTest = async (ruleData: any) => {
    try {
      setIsLoading(true);
      const created = await createRule(groupId, {
        name: ruleData.name || `Rule ${Date.now()}`,
        feature: 'General',
        ...ruleData,
      });
      setMessages(prev => [...prev, {
        id: Date.now().toString(),
        role: 'assistant',
        content: `✅ Rule '${created.name}' saved. Opening test console...`,
      }]);
      clearBuilder();
      onRuleCreated(created);
      onStartTest(created, datapointDefs);
    } catch (err: any) {
      setMessages(prev => [...prev, {
        id: Date.now().toString(),
        role: 'assistant',
        content: `Error saving rule: ${err.message}`,
      }]);
    } finally {
      setIsLoading(false);
    }
  };

  const extractStringLiterals = (ruleData: any): string[] => {
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
      content: "Update the condition or outcome in the builder below and click Translate to regenerate."
    }]);
    setTimeout(scrollToBottom, 50);
  };

  const handleRefuseRule = () => {
    clearBuilder();
    setMessages(prev => [...prev, {
      id: Date.now().toString(),
      role: 'assistant',
      content: "Rule discarded. Fill in the builder below to start fresh."
    }]);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleTranslate();
    }
  };

  return (
    <div className="flex flex-col h-full bg-white dark:bg-gray-900 transition-colors">
      <div className="flex-1 overflow-y-auto p-4 md:p-6 space-y-6">
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
                            <span key={dp} className="bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-400 px-2 py-1 rounded text-xs font-mono">
                              {dp}
                            </span>
                          ))}
                        </div>
                      </div>

                      {msg.ruleData.edge_cases?.length > 0 && (
                        <div>
                          <span className="font-semibold text-gray-800 dark:text-gray-200 block mb-1">Edge Cases:</span>
                          <ul className="list-disc pl-4 space-y-1">
                            {msg.ruleData.edge_cases.map((ec: string, i: number) => (
                              <li key={i} className="font-mono text-xs">
                                {ec.split(/("([^"]+)"|'([^']+)')/).map((part, j) => {
                                  const isLiteral = /^["'].*["']$/.test(part);
                                  return isLiteral ? (
                                    <span key={j} className="bg-amber-100 dark:bg-amber-900/40 text-amber-700 dark:text-amber-300 px-0.5 rounded" title="Verify this matches what your agent sends">
                                      {part}
                                    </span>
                                  ) : part;
                                })}
                              </li>
                            ))}
                          </ul>
                        </div>
                      )}

                      <div>
                        <span className="font-semibold text-gray-800 dark:text-gray-200 block mb-1">Main Rule Logic:</span>
                        <p className="font-mono bg-gray-50 dark:bg-gray-900 p-2 rounded text-xs overflow-x-auto">
                          {msg.ruleData.rule_logic.split(/("([^"]+)"|'([^']+)')/).map((part: string, j: number) => {
                            const isLiteral = /^["'].*["']$/.test(part);
                            return isLiteral ? (
                              <span key={j} className="bg-amber-100 dark:bg-amber-900/40 text-amber-700 dark:text-amber-300 px-0.5 rounded" title="Verify this matches what your agent sends">
                                {part}
                              </span>
                            ) : part;
                          })}
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
                        onClick={() => handleAcceptRule(msg.ruleData)}
                        className="flex items-center gap-1.5 px-3 py-1.5 bg-green-600 hover:bg-green-700 text-white rounded-md text-sm font-medium transition-colors ml-auto"
                      >
                        <Check size={16} /> Accept & Save
                      </button>
                      <button
                        onClick={() => handleSaveAndTest(msg.ruleData)}
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

      <div className="p-4 border-t border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900">
        <div className="max-w-4xl mx-auto">
          {!llmConfig ? (
            <div className="w-full p-3 text-center text-sm text-amber-600 dark:text-amber-400 bg-amber-50 dark:bg-amber-900/20 rounded-xl border border-amber-200 dark:border-amber-800/50">
              Please configure LLM Provider settings in the sidebar to start creating rules.
            </div>
          ) : (
            <div className="space-y-2">
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
                  onClick={handleTranslate}
                  disabled={!condition.trim() || isLoading}
                  className="flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 disabled:opacity-50 disabled:hover:bg-blue-600 text-white text-sm font-medium rounded-lg transition-colors"
                >
                  <Wand2 size={15} /> Translate with AI
                </button>
              </div>
            </div>
          )}
        </div>
        <div className="text-center mt-2 text-xs text-gray-400 dark:text-gray-500">
          Unreal Objects Rule Maker can make mistakes. Verify before applying.
        </div>
      </div>
    </div>
  );
};
