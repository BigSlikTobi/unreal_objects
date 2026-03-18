import React, { useState, useEffect, useRef } from 'react';
import { Send, Pencil, Check, X, Save, AlertTriangle } from 'lucide-react';
import { generateSchema, saveSchema } from '../api';
import type { LlmConfig, SchemaField, SchemaProposal } from '../types';

interface Message {
  role: 'user' | 'assistant' | 'system';
  content: string;
}

interface SchemaWorkshopProps {
  llmConfig: LlmConfig | null;
  onOpenSettings: () => void;
}

export const SchemaWorkshop: React.FC<SchemaWorkshopProps> = ({ llmConfig, onOpenSettings }) => {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [currentProposal, setCurrentProposal] = useState<SchemaProposal | null>(null);
  const [conversationHistory, setConversationHistory] = useState<{ role: string; content: string }[]>([]);
  const [isSaving, setIsSaving] = useState(false);
  const [savedPath, setSavedPath] = useState<string | null>(null);
  const [editingIndex, setEditingIndex] = useState<number | null>(null);
  const [editValues, setEditValues] = useState<SchemaField>({ name: '', type: 'string', description: '' });
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    setMessages([{
      role: 'assistant',
      content: 'Welcome to Schema Workshop. Describe your business domain and I\'ll propose a field schema. For example: "healthcare patient intake", "logistics fleet tracking", or "trading platform orders".',
    }]);
  }, []);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const currentSchemaFlat = (): Record<string, string> | undefined => {
    if (!currentProposal?.fields.length) return undefined;
    return Object.fromEntries(
      currentProposal.fields.map((f) => [f.name, `${f.type} (${f.description})`])
    );
  };

  const handleSend = async () => {
    const text = input.trim();
    if (!text || isLoading || !llmConfig) return;

    const userMsg: Message = { role: 'user', content: text };
    setMessages((prev) => [...prev, userMsg]);
    setInput('');
    setIsLoading(true);
    setSavedPath(null);

    const newHistory = [...conversationHistory, { role: 'user', content: text }];

    try {
      const proposal = await generateSchema({
        provider: llmConfig.provider,
        model: llmConfig.model,
        api_key: llmConfig.api_key,
        user_message: text,
        conversation_history: newHistory,
        current_schema: currentSchemaFlat(),
      });

      const assistantContent = proposal.message || `Proposed schema "${proposal.name}" with ${proposal.fields.length} fields.`;
      const updatedHistory = [...newHistory, { role: 'assistant', content: assistantContent }];

      setConversationHistory(updatedHistory);
      setCurrentProposal(proposal);
      setMessages((prev) => [...prev, { role: 'assistant', content: assistantContent }]);
    } catch (err) {
      setMessages((prev) => [...prev, {
        role: 'assistant',
        content: `Error: ${err instanceof Error ? err.message : 'Failed to generate schema. Check your LLM settings.'}`,
      }]);
      setConversationHistory(newHistory);
    } finally {
      setIsLoading(false);
      inputRef.current?.focus();
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const startEdit = (index: number, field: SchemaField) => {
    setEditingIndex(index);
    setEditValues({ ...field });
  };

  const cancelEdit = () => {
    setEditingIndex(null);
  };

  const applyEdit = (index: number) => {
    if (!currentProposal) return;
    const oldField = currentProposal.fields[index];
    const newFields = [...currentProposal.fields];
    newFields[index] = { ...editValues };
    setCurrentProposal({ ...currentProposal, fields: newFields });

    // Synthesize history entry so LLM stays consistent
    const note = oldField.name !== editValues.name
      ? `User renamed field "${oldField.name}" to "${editValues.name}" (type: ${editValues.type}, description: ${editValues.description})`
      : `User updated field "${editValues.name}": type=${editValues.type}, description="${editValues.description}"`;
    setConversationHistory((prev) => [...prev, { role: 'user', content: note }]);
    setEditingIndex(null);
  };

  const handleSave = async () => {
    if (!currentProposal) return;
    setIsSaving(true);
    setSavedPath(null);
    try {
      const result = await saveSchema({
        name: currentProposal.name,
        description: currentProposal.description,
        fields: currentProposal.fields,
      });
      setSavedPath(result.path);
    } catch (err) {
      setMessages((prev) => [...prev, {
        role: 'assistant',
        content: `Save failed: ${err instanceof Error ? err.message : 'Unknown error'}`,
      }]);
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <div className="flex h-full min-h-0 flex-col lg:flex-row">
      {/* Left: Chat pane */}
      <div className="flex flex-col border-b border-gray-200 dark:border-gray-800 lg:w-1/2 lg:border-b-0 lg:border-r" style={{ minHeight: 0, flex: '1 1 0' }}>
        <div className="border-b border-gray-200 px-5 py-4 dark:border-gray-800">
          <h2 className="text-base font-semibold text-gray-900 dark:text-gray-100">Schema Workshop</h2>
          <p className="mt-0.5 text-xs text-gray-500 dark:text-gray-400">
            Describe a domain to generate a reusable field schema for rule translation.
          </p>
        </div>

        {!llmConfig && (
          <div className="mx-4 mt-4 flex items-start gap-3 rounded-xl border border-amber-200 bg-amber-50 p-4 dark:border-amber-800/50 dark:bg-amber-950/20">
            <AlertTriangle size={16} className="mt-0.5 flex-shrink-0 text-amber-600 dark:text-amber-400" />
            <div className="min-w-0 flex-1">
              <p className="text-sm text-amber-800 dark:text-amber-300">
                LLM not configured.{' '}
                <button
                  onClick={onOpenSettings}
                  className="font-semibold underline hover:no-underline"
                >
                  Configure LLM
                </button>{' '}
                to use Schema Workshop.
              </p>
            </div>
          </div>
        )}

        <div className="flex-1 overflow-y-auto p-4 space-y-3" style={{ minHeight: 0 }}>
          {messages.map((msg, i) => (
            <div
              key={i}
              className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
            >
              <div
                className={`max-w-[85%] rounded-2xl px-4 py-2.5 text-sm leading-relaxed ${
                  msg.role === 'user'
                    ? 'bg-blue-600 text-white'
                    : 'bg-gray-100 text-gray-800 dark:bg-gray-800 dark:text-gray-200'
                }`}
              >
                {msg.content}
              </div>
            </div>
          ))}
          {isLoading && (
            <div className="flex justify-start">
              <div className="rounded-2xl bg-gray-100 px-4 py-2.5 text-sm text-gray-500 dark:bg-gray-800 dark:text-gray-400">
                Generating schema…
              </div>
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>

        <div className="border-t border-gray-200 p-4 dark:border-gray-800">
          <div className="flex items-end gap-2">
            <textarea
              ref={inputRef}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              disabled={!llmConfig || isLoading}
              placeholder={llmConfig ? 'Describe a domain or refine the schema…' : 'Configure LLM first'}
              rows={2}
              className="flex-1 resize-none rounded-xl border border-gray-300 bg-gray-50 px-3 py-2 text-sm text-gray-900 placeholder-gray-400 outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500 disabled:opacity-50 dark:border-gray-700 dark:bg-gray-900 dark:text-gray-100"
            />
            <button
              onClick={handleSend}
              disabled={!input.trim() || isLoading || !llmConfig}
              className="flex-shrink-0 rounded-xl bg-blue-600 p-2.5 text-white transition-colors hover:bg-blue-700 disabled:opacity-50"
            >
              <Send size={16} />
            </button>
          </div>
        </div>
      </div>

      {/* Right: Schema preview */}
      <div className="flex flex-col lg:w-1/2" style={{ minHeight: 0, flex: '1 1 0' }}>
        <div className="border-b border-gray-200 px-5 py-4 dark:border-gray-800">
          {currentProposal ? (
            <>
              <h3 className="text-sm font-semibold text-gray-900 dark:text-gray-100">
                {currentProposal.name}
              </h3>
              {currentProposal.description && (
                <p className="mt-0.5 text-xs text-gray-500 dark:text-gray-400">
                  {currentProposal.description}
                </p>
              )}
            </>
          ) : (
            <p className="text-sm text-gray-400 dark:text-gray-500">
              Schema preview will appear here after your first message.
            </p>
          )}
        </div>

        <div className="flex-1 overflow-y-auto" style={{ minHeight: 0 }}>
          {currentProposal && currentProposal.fields.length > 0 ? (
            <table className="w-full text-sm">
              <thead className="sticky top-0 bg-gray-50 dark:bg-gray-900">
                <tr className="border-b border-gray-200 dark:border-gray-800">
                  <th className="px-4 py-2 text-left text-xs font-semibold uppercase tracking-wider text-gray-500 dark:text-gray-400">Field</th>
                  <th className="px-4 py-2 text-left text-xs font-semibold uppercase tracking-wider text-gray-500 dark:text-gray-400">Type</th>
                  <th className="px-4 py-2 text-left text-xs font-semibold uppercase tracking-wider text-gray-500 dark:text-gray-400">Description</th>
                  <th className="w-10 px-2 py-2" />
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100 dark:divide-gray-800">
                {currentProposal.fields.map((field, index) => (
                  <tr key={index} className="group hover:bg-gray-50 dark:hover:bg-gray-800/50">
                    {editingIndex === index ? (
                      <>
                        <td className="px-4 py-1.5">
                          <input
                            value={editValues.name}
                            onChange={(e) => setEditValues((v) => ({ ...v, name: e.target.value }))}
                            className="w-full rounded border border-blue-400 bg-white px-2 py-1 text-xs text-gray-900 outline-none dark:bg-gray-800 dark:text-gray-100"
                            autoFocus
                          />
                        </td>
                        <td className="px-4 py-1.5">
                          <select
                            value={editValues.type}
                            onChange={(e) => setEditValues((v) => ({ ...v, type: e.target.value }))}
                            className="rounded border border-blue-400 bg-white px-2 py-1 text-xs text-gray-900 outline-none dark:bg-gray-800 dark:text-gray-100"
                          >
                            <option value="number">number</option>
                            <option value="string">string</option>
                            <option value="boolean">boolean</option>
                          </select>
                        </td>
                        <td className="px-4 py-1.5">
                          <input
                            value={editValues.description}
                            onChange={(e) => setEditValues((v) => ({ ...v, description: e.target.value }))}
                            className="w-full rounded border border-blue-400 bg-white px-2 py-1 text-xs text-gray-900 outline-none dark:bg-gray-800 dark:text-gray-100"
                          />
                        </td>
                        <td className="px-2 py-1.5">
                          <div className="flex gap-1">
                            <button onClick={() => applyEdit(index)} className="rounded p-1 text-green-600 hover:bg-green-100 dark:hover:bg-green-900/30">
                              <Check size={12} />
                            </button>
                            <button onClick={cancelEdit} className="rounded p-1 text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-700">
                              <X size={12} />
                            </button>
                          </div>
                        </td>
                      </>
                    ) : (
                      <>
                        <td className="px-4 py-2 font-mono text-xs text-gray-800 dark:text-gray-200">{field.name}</td>
                        <td className="px-4 py-2">
                          <span className={`inline-block rounded px-1.5 py-0.5 text-xs font-medium ${
                            field.type === 'number' ? 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-300'
                            : field.type === 'boolean' ? 'bg-purple-100 text-purple-700 dark:bg-purple-900/30 dark:text-purple-300'
                            : 'bg-gray-100 text-gray-700 dark:bg-gray-700 dark:text-gray-300'
                          }`}>
                            {field.type}
                          </span>
                        </td>
                        <td className="px-4 py-2 text-xs text-gray-500 dark:text-gray-400">{field.description}</td>
                        <td className="px-2 py-2">
                          <button
                            onClick={() => startEdit(index, field)}
                            className="rounded p-1 text-gray-300 opacity-0 transition-opacity hover:bg-gray-100 hover:text-gray-600 group-hover:opacity-100 dark:hover:bg-gray-700 dark:hover:text-gray-300"
                          >
                            <Pencil size={12} />
                          </button>
                        </td>
                      </>
                    )}
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <div className="flex h-full items-center justify-center p-8 text-sm text-gray-400 dark:text-gray-500">
              No fields yet. Describe your domain in the chat.
            </div>
          )}
        </div>

        <div className="border-t border-gray-200 p-4 dark:border-gray-800">
          {savedPath && (
            <div className="mb-3 rounded-lg bg-green-50 px-3 py-2 text-xs text-green-700 dark:bg-green-950/30 dark:text-green-400">
              Saved to: <span className="font-mono">{savedPath}</span>
            </div>
          )}
          <button
            onClick={handleSave}
            disabled={!currentProposal || currentProposal.fields.length === 0 || isSaving}
            className="flex w-full items-center justify-center gap-2 rounded-xl bg-green-600 px-4 py-2.5 text-sm font-medium text-white transition-colors hover:bg-green-700 disabled:opacity-50"
          >
            <Save size={16} />
            {isSaving ? 'Saving…' : 'Save Schema'}
          </button>
        </div>
      </div>
    </div>
  );
};
