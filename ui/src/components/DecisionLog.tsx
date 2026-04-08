import { useCallback, useEffect, useRef, useState } from 'react';
import { ChevronDown, ChevronRight, Download, RefreshCw, ScrollText } from 'lucide-react';
import { downloadDecisionLog, fetchAtomicLogs, fetchDecisionChain } from '../api';
import type { AtomicLogEntry, DecisionChain, DecisionState } from '../types';

const DECISION_COLORS: Record<DecisionState, { badge: string; dot: string }> = {
  APPROVED: {
    badge: 'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-300',
    dot: 'bg-emerald-500',
  },
  REJECTED: {
    badge: 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-300',
    dot: 'bg-red-500',
  },
  APPROVAL_REQUIRED: {
    badge: 'bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-300',
    dot: 'bg-amber-500',
  },
};

function formatTimestamp(ts: string) {
  const date = new Date(ts);
  if (Number.isNaN(date.getTime())) {
    return ts;
  }
  return date.toLocaleString();
}

function truncateId(id: string) {
  return id.length > 12 ? `${id.slice(0, 12)}...` : id;
}

export function DecisionLog() {
  const [logs, setLogs] = useState<AtomicLogEntry[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [chain, setChain] = useState<DecisionChain | null>(null);
  const [chainLoading, setChainLoading] = useState(false);
  const [isDownloading, setIsDownloading] = useState(false);
  const expandedIdRef = useRef<string | null>(null);

  useEffect(() => {
    expandedIdRef.current = expandedId;
  }, [expandedId]);

  const refresh = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const data = await fetchAtomicLogs();
      setLogs(data.slice().sort((a, b) =>
        new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime()
      ));
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load logs');
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const handleDownload = useCallback(async () => {
    setIsDownloading(true);
    setError(null);
    try {
      const blob = await downloadDecisionLog();
      const url = URL.createObjectURL(blob);
      const ts = new Date().toISOString().replace(/[:.]/g, '-');
      const a = document.createElement('a');
      a.href = url;
      a.download = `decision_log_${ts}.json`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      setTimeout(() => URL.revokeObjectURL(url), 0);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to download log');
    } finally {
      setIsDownloading(false);
    }
  }, []);

  const handleToggle = async (requestId: string) => {
    if (expandedId === requestId) {
      setExpandedId(null);
      setChain(null);
      return;
    }
    setExpandedId(requestId);
    setChain(null);
    setChainLoading(true);
    try {
      const data = await fetchDecisionChain(requestId);
      if (expandedIdRef.current !== requestId) {
        return;
      }
      setChain(data);
    } catch {
      if (expandedIdRef.current === requestId) {
        setChain(null);
      }
    } finally {
      if (expandedIdRef.current === requestId) {
        setChainLoading(false);
      }
    }
  };

  return (
    <section className="space-y-4" aria-labelledby="decision-log-heading">
      <div className="flex items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <ScrollText size={18} className="text-blue-500" />
          <h3 id="decision-log-heading" className="text-base font-semibold text-gray-800 dark:text-gray-100">
            Decision Log
          </h3>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={handleDownload}
            disabled={isDownloading}
            className="inline-flex items-center gap-2 rounded-lg border border-gray-300 px-3 py-1.5 text-sm font-medium text-gray-700 transition-colors hover:bg-gray-100 disabled:opacity-50 dark:border-gray-700 dark:text-gray-200 dark:hover:bg-gray-800"
          >
            <Download size={14} className={isDownloading ? 'animate-pulse' : ''} />
            Download JSON
          </button>
          <button
            onClick={refresh}
            disabled={isLoading}
            className="inline-flex items-center gap-2 rounded-lg border border-gray-300 px-3 py-1.5 text-sm font-medium text-gray-700 transition-colors hover:bg-gray-100 disabled:opacity-50 dark:border-gray-700 dark:text-gray-200 dark:hover:bg-gray-800"
          >
            <RefreshCw size={14} className={isLoading ? 'animate-spin' : ''} />
            Refresh
          </button>
        </div>
      </div>
      <p className="text-sm text-gray-500 dark:text-gray-400">
        Audit trail of all evaluated decisions. Click an entry to view its full event chain.
      </p>

      {error && (
        <div className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700 dark:border-red-900/40 dark:bg-red-950/20 dark:text-red-300">
          {error}
        </div>
      )}

      {logs.length === 0 && !isLoading && !error && (
        <div className="rounded-xl border border-dashed border-gray-300 bg-gray-50 p-8 text-center dark:border-gray-700 dark:bg-gray-900/40">
          <ScrollText size={32} className="mx-auto mb-3 text-gray-300 dark:text-gray-600" />
          <p className="text-sm text-gray-500 dark:text-gray-400">
            No decisions logged yet. Run a test in the Test Console to generate entries.
          </p>
        </div>
      )}

      <div className="space-y-2">
        {logs.map((entry) => {
          const colors = DECISION_COLORS[entry.decision];
          const isExpanded = expandedId === entry.request_id;

          return (
            <div
              key={entry.request_id}
              className="rounded-xl border border-gray-200 bg-white dark:border-gray-700 dark:bg-gray-900/60"
            >
              <button
                type="button"
                onClick={() => handleToggle(entry.request_id)}
                className="flex w-full items-start gap-3 px-4 py-3 text-left transition-colors hover:bg-gray-50 dark:hover:bg-gray-800/50 rounded-xl"
              >
                <div className="mt-1 flex-shrink-0">
                  {isExpanded ? (
                    <ChevronDown size={16} className="text-gray-400" />
                  ) : (
                    <ChevronRight size={16} className="text-gray-400" />
                  )}
                </div>
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-semibold ${colors.badge}`}>
                      <span className={`h-1.5 w-1.5 rounded-full ${colors.dot}`} />
                      {entry.decision}
                    </span>
                    <span className="text-sm font-medium text-gray-800 dark:text-gray-100 truncate">
                      {entry.request_description}
                    </span>
                  </div>
                  <div className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-gray-500 dark:text-gray-400">
                    <span>{formatTimestamp(entry.timestamp)}</span>
                    {entry.effective_group_id && (
                      <span>Group: {truncateId(entry.effective_group_id)}</span>
                    )}
                    {entry.agent_id && (
                      <span>Agent: {truncateId(entry.agent_id)}</span>
                    )}
                    <span className="font-mono">{truncateId(entry.request_id)}</span>
                  </div>
                </div>
              </button>

              {isExpanded && (
                <div className="border-t border-gray-200 px-4 py-3 dark:border-gray-700">
                  {chainLoading ? (
                    <div className="flex items-center gap-2 text-sm text-gray-500 dark:text-gray-400">
                      <RefreshCw size={14} className="animate-spin" />
                      Loading chain events...
                    </div>
                  ) : chain && chain.events.length > 0 ? (
                    <div className="relative ml-2 space-y-3 border-l-2 border-gray-200 pl-4 dark:border-gray-700">
                      {chain.events.map((event, idx) => (
                        <div key={idx} className="relative">
                          <div className="absolute -left-[21px] top-1 h-2.5 w-2.5 rounded-full border-2 border-white bg-blue-500 dark:border-gray-900" />
                          <div className="text-xs font-semibold text-gray-700 dark:text-gray-200">
                            {event.event_type}
                            <span className="ml-2 font-normal text-gray-400 dark:text-gray-500">
                              {formatTimestamp(event.timestamp)}
                            </span>
                          </div>
                          {Object.keys(event.details).length > 0 && (
                            <pre className="mt-1 max-h-48 overflow-auto rounded-lg bg-gray-50 p-2 text-xs text-gray-600 dark:bg-gray-800 dark:text-gray-300">
                              {JSON.stringify(event.details, null, 2)}
                            </pre>
                          )}
                        </div>
                      ))}
                    </div>
                  ) : (
                    <p className="text-sm text-gray-500 dark:text-gray-400">
                      No chain events found for this request.
                    </p>
                  )}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </section>
  );
}
