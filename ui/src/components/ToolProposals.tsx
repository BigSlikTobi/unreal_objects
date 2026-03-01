import { useCallback, useEffect, useState } from 'react';
import { CheckCircle, ChevronLeft, Clock, Code2, RefreshCw, User, X, XCircle } from 'lucide-react';
import { fetchProposals, reviewProposal } from '../api';
import type { ToolProposal } from '../api';

const TOOL_AGENT_BASE = 'http://127.0.0.1:8003/v1';

interface Props {
  onClose: () => void;
}

const STATUS_STYLES: Record<ToolProposal['status'], { label: string; className: string }> = {
  pending_review: { label: 'Pending Review', className: 'bg-amber-100 text-amber-800 dark:bg-amber-900/30 dark:text-amber-300' },
  approved:       { label: 'Approved',        className: 'bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-300' },
  rejected:       { label: 'Rejected',        className: 'bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-300' },
};

export function ToolProposals({ onClose }: Props) {
  const [proposals, setProposals] = useState<ToolProposal[]>([]);
  const [selected, setSelected] = useState<ToolProposal | null>(null);
  const [reviewer, setReviewer] = useState('');
  const [loading, setLoading] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);
  const [llmStatus, setLlmStatus] = useState<{ provider: string; model: string; configured: boolean } | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [data, cfg] = await Promise.all([
        fetchProposals(),
        fetch(`${TOOL_AGENT_BASE}/config`).then((r) => r.json()).catch(() => null),
      ]);
      setProposals(data.sort((a, b) => b.created_at.localeCompare(a.created_at)));
      if (cfg) setLlmStatus(cfg);
    } catch {
      setError('Could not reach the Tool Creation Agent (port 8003). Is it running?');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  // Keep selected in sync after refresh
  useEffect(() => {
    if (selected) {
      const updated = proposals.find((p) => p.id === selected.id);
      if (updated) setSelected(updated);
    }
  }, [proposals, selected]);

  const handleReview = async (approved: boolean) => {
    if (!selected || !reviewer.trim()) return;
    setSubmitting(true);
    setError(null);
    setSuccessMsg(null);
    try {
      const result = await reviewProposal(selected.id, approved, reviewer.trim()) as { message?: string };
      setSuccessMsg(
        approved
          ? (result.message ?? `Tool '${selected.tool_name}' approved and written to server.py. Restart the MCP server.`)
          : `Proposal '${selected.tool_name}' rejected.`
      );
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Review submission failed');
    } finally {
      setSubmitting(false);
    }
  };

  const pendingCount = proposals.filter((p) => p.status === 'pending_review').length;

  return (
    <div className="fixed inset-0 z-50 flex items-stretch justify-end bg-black/50 backdrop-blur-sm">
      <div className="flex h-full w-full max-w-3xl flex-col bg-white shadow-2xl dark:bg-gray-900">
        {/* Header */}
        <div className="flex items-center justify-between border-b border-gray-200 px-4 py-3 dark:border-gray-700">
          <div className="flex items-center gap-3">
            <Code2 size={18} className="text-purple-600 dark:text-purple-400" />
            <span className="font-semibold text-gray-800 dark:text-gray-100">Tool Proposals</span>
            {pendingCount > 0 && (
              <span className="rounded-full bg-amber-500 px-2 py-0.5 text-xs font-bold text-white">
                {pendingCount}
              </span>
            )}
          </div>
          <div className="flex items-center gap-2">
            {llmStatus && (
              <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${llmStatus.configured ? 'bg-purple-100 text-purple-700 dark:bg-purple-900/30 dark:text-purple-300' : 'bg-gray-100 text-gray-500 dark:bg-gray-800 dark:text-gray-400'}`}>
                {llmStatus.configured ? `${llmStatus.provider} / ${llmStatus.model}` : 'No LLM configured'}
              </span>
            )}
            <button
              onClick={load}
              disabled={loading}
              title="Refresh"
              className="rounded-lg p-1.5 text-gray-500 transition-colors hover:bg-gray-100 dark:hover:bg-gray-800"
            >
              <RefreshCw size={15} className={loading ? 'animate-spin' : ''} />
            </button>
            <button
              onClick={onClose}
              className="rounded-lg p-1.5 text-gray-500 transition-colors hover:bg-gray-100 dark:hover:bg-gray-800"
            >
              <X size={16} />
            </button>
          </div>
        </div>

        <div className="flex min-h-0 flex-1">
          {/* Proposal list */}
          <div className={`flex flex-col border-r border-gray-200 dark:border-gray-700 ${selected ? 'hidden sm:flex sm:w-64 sm:flex-shrink-0' : 'flex flex-1'}`}>
            {error && !selected && (
              <div className="m-3 rounded-lg bg-red-50 p-3 text-sm text-red-600 dark:bg-red-900/20 dark:text-red-400">
                {error}
              </div>
            )}
            {proposals.length === 0 && !loading && !error && (
              <div className="flex flex-1 items-center justify-center p-8 text-center text-sm text-gray-500 dark:text-gray-400">
                <div>
                  <Clock size={32} className="mx-auto mb-3 opacity-30" />
                  No tool proposals yet.
                  <br />
                  They appear when you create rules that require new action types.
                </div>
              </div>
            )}
            <div className="flex-1 overflow-y-auto">
              {proposals.map((p) => {
                const st = STATUS_STYLES[p.status];
                return (
                  <button
                    key={p.id}
                    onClick={() => { setSelected(p); setSuccessMsg(null); setError(null); }}
                    className={`w-full border-b border-gray-100 px-4 py-3 text-left transition-colors hover:bg-gray-50 dark:border-gray-800 dark:hover:bg-gray-800 ${selected?.id === p.id ? 'bg-purple-50 dark:bg-purple-900/20' : ''}`}
                  >
                    <div className="flex items-start justify-between gap-2">
                      <span className="truncate text-sm font-semibold text-gray-800 dark:text-gray-100">
                        {p.tool_name}
                      </span>
                      <span className={`shrink-0 rounded-full px-2 py-0.5 text-xs font-medium ${st.className}`}>
                        {st.label}
                      </span>
                    </div>
                    <p className="mt-0.5 truncate text-xs text-gray-500 dark:text-gray-400">
                      Triggered by: {p.trigger_rule}
                    </p>
                    <p className="mt-0.5 text-xs text-gray-400 dark:text-gray-500">
                      {new Date(p.created_at).toLocaleString()}
                    </p>
                  </button>
                );
              })}
            </div>
          </div>

          {/* Detail panel */}
          {selected && (
            <div className="flex min-h-0 flex-1 flex-col overflow-y-auto">
              <div className="border-b border-gray-200 px-4 py-3 dark:border-gray-700">
                <button
                  onClick={() => setSelected(null)}
                  className="mb-2 flex items-center gap-1 text-xs text-gray-500 hover:text-gray-700 dark:hover:text-gray-300 sm:hidden"
                >
                  <ChevronLeft size={14} /> Back
                </button>
                <div className="flex items-start justify-between gap-2">
                  <h2 className="font-semibold text-gray-800 dark:text-gray-100">{selected.tool_name}</h2>
                  <span className={`shrink-0 rounded-full px-2 py-0.5 text-xs font-medium ${STATUS_STYLES[selected.status].className}`}>
                    {STATUS_STYLES[selected.status].label}
                  </span>
                </div>
                <p className="mt-1 text-sm text-gray-600 dark:text-gray-400">{selected.action_description}</p>
              </div>

              <div className="flex-1 space-y-4 p-4">
                <div className="grid grid-cols-2 gap-3 text-sm">
                  <div>
                    <p className="text-xs font-medium uppercase tracking-wide text-gray-400 dark:text-gray-500">Triggered by rule</p>
                    <p className="mt-0.5 text-gray-700 dark:text-gray-300">{selected.trigger_rule}</p>
                  </div>
                  <div>
                    <p className="text-xs font-medium uppercase tracking-wide text-gray-400 dark:text-gray-500">In group</p>
                    <p className="mt-0.5 text-gray-700 dark:text-gray-300">{selected.trigger_group}</p>
                  </div>
                  <div className="col-span-2">
                    <p className="text-xs font-medium uppercase tracking-wide text-gray-400 dark:text-gray-500">Why a new tool?</p>
                    <p className="mt-0.5 text-gray-700 dark:text-gray-300">{selected.reason}</p>
                  </div>
                  {selected.reviewer && (
                    <div className="col-span-2 flex items-center gap-1.5 text-gray-500 dark:text-gray-400">
                      <User size={13} />
                      <span className="text-xs">Reviewed by {selected.reviewer}</span>
                    </div>
                  )}
                </div>

                {/* Generated code */}
                <div>
                  <p className="mb-2 text-xs font-medium uppercase tracking-wide text-gray-400 dark:text-gray-500">
                    Generated Code
                  </p>
                  <pre className="overflow-x-auto rounded-lg bg-gray-900 p-4 text-xs leading-relaxed text-green-300 dark:bg-black/50">
                    <code>{selected.generated_code}</code>
                  </pre>
                  <p className="mt-1.5 text-xs text-gray-400 dark:text-gray-500">
                    This code will be appended to <code className="font-mono">mcp_server/server.py</code>.
                    Look for <code className="font-mono">TODO</code> comments — you'll need to implement the actual execution logic.
                  </p>
                </div>

                {/* Review actions */}
                {selected.status === 'pending_review' && (
                  <div className="rounded-lg border border-amber-200 bg-amber-50 p-4 dark:border-amber-800/30 dark:bg-amber-900/10">
                    <p className="mb-3 text-sm font-medium text-amber-800 dark:text-amber-300">
                      Review this proposal
                    </p>
                    {successMsg && (
                      <div className="mb-3 rounded-lg bg-green-50 px-3 py-2 text-sm text-green-700 dark:bg-green-900/20 dark:text-green-300">
                        {successMsg}
                      </div>
                    )}
                    {error && (
                      <div className="mb-3 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-600 dark:bg-red-900/20 dark:text-red-400">
                        {error}
                      </div>
                    )}
                    <div className="mb-3">
                      <label className="mb-1 block text-xs font-medium text-gray-700 dark:text-gray-300">
                        Your name (reviewer)
                      </label>
                      <input
                        type="text"
                        value={reviewer}
                        onChange={(e) => setReviewer(e.target.value)}
                        placeholder="e.g. Alice"
                        className="w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm text-gray-900 placeholder-gray-400 dark:border-gray-600 dark:bg-gray-800 dark:text-gray-100"
                      />
                    </div>
                    <div className="flex gap-2">
                      <button
                        onClick={() => handleReview(true)}
                        disabled={submitting || !reviewer.trim()}
                        className="flex flex-1 items-center justify-center gap-2 rounded-lg bg-green-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-green-700 disabled:opacity-50"
                      >
                        <CheckCircle size={15} />
                        Approve &amp; Write to server.py
                      </button>
                      <button
                        onClick={() => handleReview(false)}
                        disabled={submitting || !reviewer.trim()}
                        className="flex items-center gap-2 rounded-lg border border-gray-300 px-4 py-2 text-sm font-medium text-gray-700 transition-colors hover:bg-gray-100 disabled:opacity-50 dark:border-gray-600 dark:text-gray-300 dark:hover:bg-gray-800"
                      >
                        <XCircle size={15} />
                        Reject
                      </button>
                    </div>
                  </div>
                )}

                {selected.status === 'approved' && successMsg && (
                  <div className="rounded-lg bg-green-50 px-3 py-2 text-sm text-green-700 dark:bg-green-900/20 dark:text-green-300">
                    {successMsg}
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
