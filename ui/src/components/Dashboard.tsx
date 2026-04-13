import React, { useCallback, useEffect, useState } from 'react';
import {
  Activity,
  CheckCircle2,
  Clock,
  LayoutDashboard,
  RefreshCw,
  ShieldCheck,
  XCircle,
} from 'lucide-react';
import {
  fetchAtomicLogs,
  fetchDecisionCenterHealth,
  fetchGroups,
  fetchPendingApprovals,
  fetchRuleEngineHealth,
  submitApprovalDecision,
} from '../api';
import type { AtomicLogEntry, DecisionState, RuleGroup } from '../types';
import type { PendingApproval } from '../api';

interface DashboardProps {
  onNavigateToDecisionLog: () => void;
}

function timeAgo(ts: string): string {
  const diff = Date.now() - new Date(ts).getTime();
  const sec = Math.floor(diff / 1000);
  if (sec < 60) return `${sec}s ago`;
  const min = Math.floor(sec / 60);
  if (min < 60) return `${min}m ago`;
  const hr = Math.floor(min / 60);
  if (hr < 24) return `${hr}h ago`;
  return new Date(ts).toLocaleDateString();
}

function isToday(ts: string): boolean {
  const d = new Date(ts);
  const now = new Date();
  return (
    d.getFullYear() === now.getFullYear() &&
    d.getMonth() === now.getMonth() &&
    d.getDate() === now.getDate()
  );
}

function DecisionBadge({ decision }: { decision: DecisionState }) {
  if (decision === 'APPROVED')
    return (
      <span className="inline-flex items-center gap-1 rounded-full bg-green-100 px-2 py-0.5 text-xs font-medium text-green-700 dark:bg-green-900/30 dark:text-green-400">
        ✓ Approved
      </span>
    );
  if (decision === 'REJECTED')
    return (
      <span className="inline-flex items-center gap-1 rounded-full bg-red-100 px-2 py-0.5 text-xs font-medium text-red-700 dark:bg-red-900/30 dark:text-red-400">
        ✗ Rejected
      </span>
    );
  return (
    <span className="inline-flex items-center gap-1 rounded-full bg-amber-100 px-2 py-0.5 text-xs font-medium text-amber-700 dark:bg-amber-900/30 dark:text-amber-400">
      ⏳ Awaiting
    </span>
  );
}

function ServiceBadge({ label, online }: { label: string; online: boolean | null }) {
  const isLoading = online === null;
  const isOnline = online === true;
  return (
    <div className="flex items-center gap-2 rounded-full border border-gray-200 bg-white px-3 py-1.5 shadow-sm dark:border-gray-700 dark:bg-gray-800">
      <span
        className={`h-2 w-2 rounded-full ${
          isLoading
            ? 'animate-pulse bg-gray-300'
            : isOnline
              ? 'bg-green-500'
              : 'bg-red-500'
        }`}
      />
      <span className="text-xs font-medium text-gray-600 dark:text-gray-300">{label}</span>
      <span
        className={`text-xs ${
          isLoading
            ? 'text-gray-400'
            : isOnline
              ? 'text-green-600 dark:text-green-400'
              : 'text-red-600 dark:text-red-400'
        }`}
      >
        {isLoading ? '…' : isOnline ? 'Online' : 'Offline'}
      </span>
    </div>
  );
}

function StatCard({
  label,
  value,
  sublabel,
  icon,
  iconBg,
  highlight = false,
}: {
  label: string;
  value: number;
  sublabel?: string;
  icon: React.ReactNode;
  iconBg: string;
  highlight?: boolean;
}) {
  return (
    <div
      className={`rounded-xl border bg-white p-4 dark:bg-gray-900 ${
        highlight
          ? 'border-amber-200 dark:border-amber-800/50'
          : 'border-gray-200 dark:border-gray-800'
      }`}
    >
      <div
        className={`mb-3 inline-flex h-9 w-9 items-center justify-center rounded-lg ${iconBg}`}
      >
        {icon}
      </div>
      <div className="text-2xl font-bold text-gray-900 dark:text-gray-100">{value}</div>
      <div className="mt-0.5 text-sm text-gray-500 dark:text-gray-400">{label}</div>
      {sublabel && <div className="mt-0.5 text-xs text-gray-400 dark:text-gray-500">{sublabel}</div>}
    </div>
  );
}

function OutcomeRow({
  label,
  count,
  pct,
  barColor,
  icon,
}: {
  label: string;
  count: number;
  pct: number;
  barColor: string;
  icon: React.ReactNode;
}) {
  return (
    <div className="space-y-1.5">
      <div className="flex items-center justify-between text-sm">
        <div className="flex items-center gap-2">
          {icon}
          <span className="text-gray-700 dark:text-gray-300">{label}</span>
        </div>
        <div className="flex items-center gap-2">
          <span className="font-semibold text-gray-900 dark:text-gray-100">{count}</span>
          <span className="w-8 text-right text-xs text-gray-400">{pct}%</span>
        </div>
      </div>
      <div className="h-1.5 w-full overflow-hidden rounded-full bg-gray-100 dark:bg-gray-800">
        <div
          className={`h-full rounded-full ${barColor} transition-all duration-700`}
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  );
}

export const Dashboard: React.FC<DashboardProps> = ({ onNavigateToDecisionLog }) => {
  const [ruleEngineOnline, setRuleEngineOnline] = useState<boolean | null>(null);
  const [decisionCenterOnline, setDecisionCenterOnline] = useState<boolean | null>(null);
  const [groups, setGroups] = useState<RuleGroup[]>([]);
  const [logs, setLogs] = useState<AtomicLogEntry[]>([]);
  const [pending, setPending] = useState<PendingApproval[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [lastRefresh, setLastRefresh] = useState<Date>(new Date());
  const [approvingId, setApprovingId] = useState<string | null>(null);

  const load = useCallback(async () => {
    const [reHealth, dcHealth, groupsData, logsData, pendingData] = await Promise.allSettled([
      fetchRuleEngineHealth(),
      fetchDecisionCenterHealth(),
      fetchGroups(),
      fetchAtomicLogs(),
      fetchPendingApprovals(),
    ]);

    setRuleEngineOnline(reHealth.status === 'fulfilled' ? reHealth.value : false);
    setDecisionCenterOnline(dcHealth.status === 'fulfilled' ? dcHealth.value : false);
    if (groupsData.status === 'fulfilled') setGroups(groupsData.value);
    if (logsData.status === 'fulfilled') setLogs(logsData.value);
    setPending(pendingData.status === 'fulfilled' ? pendingData.value : []);

    setLastRefresh(new Date());
    setIsLoading(false);
  }, []);

  useEffect(() => {
    load();
    const interval = setInterval(load, 30_000);
    return () => clearInterval(interval);
  }, [load]);

  const handleApprove = async (requestId: string, approved: boolean) => {
    setApprovingId(requestId);
    try {
      await submitApprovalDecision(requestId, approved, 'Dashboard');
      setPending((prev) => prev.filter((p) => p.request_id !== requestId));
    } catch {
      // next refresh will correct state
    } finally {
      setApprovingId(null);
    }
  };

  const totalRules = groups.reduce((sum, g) => sum + g.rules.length, 0);
  const activeRules = groups.reduce((sum, g) => sum + g.rules.filter((r) => r.active).length, 0);
  const todayCount = logs.filter((l) => isToday(l.timestamp)).length;

  const approvedCount = logs.filter((l) => l.decision === 'APPROVED').length;
  const rejectedCount = logs.filter((l) => l.decision === 'REJECTED').length;
  const awaitingCount = logs.filter((l) => l.decision === 'APPROVAL_REQUIRED').length;
  const total = approvedCount + rejectedCount + awaitingCount || 1;

  const recentLogs = [...logs]
    .sort((a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime())
    .slice(0, 10);

  if (isLoading) {
    return (
      <div className="flex h-full items-center justify-center">
        <RefreshCw size={24} className="animate-spin text-gray-400" />
      </div>
    );
  }

  return (
    <div className="h-full overflow-y-auto">
      <div className="mx-auto max-w-5xl space-y-6 px-4 py-6 sm:px-6">

        {/* Header row */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <LayoutDashboard size={20} className="text-blue-500" />
            <h1 className="text-lg font-bold text-gray-900 dark:text-gray-100">Dashboard</h1>
          </div>
          <button
            onClick={load}
            className="flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-sm text-gray-500 transition-colors hover:bg-gray-100 hover:text-gray-700 dark:text-gray-400 dark:hover:bg-gray-800 dark:hover:text-gray-200"
          >
            <RefreshCw size={13} />
            <span className="hidden sm:inline">Refresh</span>
          </button>
        </div>

        {/* Service health */}
        <div className="flex flex-wrap items-center gap-3">
          <ServiceBadge label="Rule Engine" online={ruleEngineOnline} />
          <ServiceBadge label="Decision Center" online={decisionCenterOnline} />
          <span className="ml-auto text-xs text-gray-400">
            Updated {lastRefresh.toLocaleTimeString()}
          </span>
        </div>

        {/* Stat cards */}
        <div className="grid grid-cols-2 gap-3 sm:gap-4 lg:grid-cols-4">
          <StatCard
            label="Rule Groups"
            value={groups.length}
            icon={<ShieldCheck size={18} className="text-blue-500" />}
            iconBg="bg-blue-50 dark:bg-blue-950/30"
          />
          <StatCard
            label="Total Rules"
            value={totalRules}
            sublabel={`${activeRules} active`}
            icon={<Activity size={18} className="text-indigo-500" />}
            iconBg="bg-indigo-50 dark:bg-indigo-950/30"
          />
          <StatCard
            label="Pending"
            value={pending.length}
            icon={
              <Clock
                size={18}
                className={pending.length > 0 ? 'text-amber-500' : 'text-gray-400'}
              />
            }
            iconBg={
              pending.length > 0
                ? 'bg-amber-50 dark:bg-amber-950/30'
                : 'bg-gray-50 dark:bg-gray-800/40'
            }
            highlight={pending.length > 0}
          />
          <StatCard
            label="Decisions Today"
            value={todayCount}
            icon={<CheckCircle2 size={18} className="text-green-500" />}
            iconBg="bg-green-50 dark:bg-green-950/30"
          />
        </div>

        {/* Middle row: outcomes + pending approvals */}
        <div className="grid grid-cols-1 gap-5 lg:grid-cols-2">

          {/* Decision outcomes */}
          <div className="rounded-xl border border-gray-200 bg-white p-5 dark:border-gray-800 dark:bg-gray-900">
            <h2 className="mb-4 text-sm font-semibold text-gray-700 dark:text-gray-300">
              Decision Outcomes
            </h2>
            {logs.length === 0 ? (
              <p className="py-4 text-center text-sm text-gray-400">No decisions recorded yet.</p>
            ) : (
              <div className="space-y-4">
                <OutcomeRow
                  label="Approved"
                  count={approvedCount}
                  pct={Math.round((approvedCount / total) * 100)}
                  barColor="bg-green-500"
                  icon={<CheckCircle2 size={15} className="text-green-500" />}
                />
                <OutcomeRow
                  label="Rejected"
                  count={rejectedCount}
                  pct={Math.round((rejectedCount / total) * 100)}
                  barColor="bg-red-500"
                  icon={<XCircle size={15} className="text-red-500" />}
                />
                <OutcomeRow
                  label="Awaiting"
                  count={awaitingCount}
                  pct={Math.round((awaitingCount / total) * 100)}
                  barColor="bg-amber-400"
                  icon={<Clock size={15} className="text-amber-500" />}
                />
              </div>
            )}
          </div>

          {/* Pending approvals */}
          <div className="rounded-xl border border-gray-200 bg-white p-5 dark:border-gray-800 dark:bg-gray-900">
            <h2 className="mb-4 flex items-center gap-2 text-sm font-semibold text-gray-700 dark:text-gray-300">
              Pending Approvals
              {pending.length > 0 && (
                <span className="inline-flex h-5 w-5 items-center justify-center rounded-full bg-amber-500 text-xs font-bold text-white">
                  {pending.length}
                </span>
              )}
            </h2>
            {pending.length === 0 ? (
              <div className="flex flex-col items-center justify-center py-6 text-center">
                <CheckCircle2 size={30} className="mb-2 text-green-400" />
                <p className="text-sm text-gray-400">All clear — no pending approvals</p>
              </div>
            ) : (
              <div className="max-h-52 space-y-2 overflow-y-auto">
                {pending.map((p) => (
                  <div
                    key={p.request_id}
                    className="flex items-start gap-2 rounded-lg border border-amber-100 bg-amber-50/60 p-3 dark:border-amber-900/30 dark:bg-amber-950/10"
                  >
                    <div className="min-w-0 flex-1">
                      <div className="truncate text-sm font-medium text-gray-800 dark:text-gray-200">
                        {p.request_description}
                      </div>
                      {p.agent_id && (
                        <div className="mt-0.5 truncate text-xs text-gray-500 dark:text-gray-400">
                          Agent: {p.agent_id}
                        </div>
                      )}
                    </div>
                    <div className="flex flex-shrink-0 gap-1">
                      <button
                        disabled={approvingId === p.request_id}
                        onClick={() => handleApprove(p.request_id, true)}
                        className="rounded-md bg-green-100 px-2 py-1 text-xs font-semibold text-green-700 transition-colors hover:bg-green-200 disabled:opacity-50 dark:bg-green-900/30 dark:text-green-400 dark:hover:bg-green-900/50"
                        title="Approve"
                      >
                        ✓
                      </button>
                      <button
                        disabled={approvingId === p.request_id}
                        onClick={() => handleApprove(p.request_id, false)}
                        className="rounded-md bg-red-100 px-2 py-1 text-xs font-semibold text-red-700 transition-colors hover:bg-red-200 disabled:opacity-50 dark:bg-red-900/30 dark:text-red-400 dark:hover:bg-red-900/50"
                        title="Reject"
                      >
                        ✗
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Recent decisions */}
        <div className="rounded-xl border border-gray-200 bg-white dark:border-gray-800 dark:bg-gray-900">
          <div className="flex items-center justify-between border-b border-gray-100 px-5 py-4 dark:border-gray-800">
            <h2 className="text-sm font-semibold text-gray-700 dark:text-gray-300">
              Recent Decisions
            </h2>
            <button
              onClick={onNavigateToDecisionLog}
              className="text-xs text-blue-500 transition-colors hover:text-blue-600 dark:text-blue-400 dark:hover:text-blue-300"
            >
              View all →
            </button>
          </div>

          {recentLogs.length === 0 ? (
            <div className="px-5 py-8 text-center text-sm text-gray-400">
              No decisions recorded yet.
            </div>
          ) : (
            <>
              {/* Desktop table */}
              <div className="hidden sm:block">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-gray-100 text-xs text-gray-400 dark:border-gray-800">
                      <th className="px-5 py-3 text-left font-medium">Time</th>
                      <th className="px-5 py-3 text-left font-medium">Description</th>
                      <th className="px-5 py-3 text-left font-medium">Agent</th>
                      <th className="px-5 py-3 text-left font-medium">Decision</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-50 dark:divide-gray-800/50">
                    {recentLogs.map((log) => (
                      <tr
                        key={log.request_id}
                        className="cursor-pointer transition-colors hover:bg-gray-50 dark:hover:bg-gray-800/30"
                        onClick={onNavigateToDecisionLog}
                      >
                        <td className="whitespace-nowrap px-5 py-3 text-xs text-gray-400">
                          {timeAgo(log.timestamp)}
                        </td>
                        <td className="max-w-xs truncate px-5 py-3 text-gray-700 dark:text-gray-300">
                          {log.request_description}
                        </td>
                        <td className="px-5 py-3 text-xs text-gray-500 dark:text-gray-400">
                          {log.agent_id ?? '—'}
                        </td>
                        <td className="px-5 py-3">
                          <DecisionBadge decision={log.decision} />
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              {/* Mobile card list */}
              <div className="space-y-2 p-4 sm:hidden">
                {recentLogs.map((log) => (
                  <div
                    key={log.request_id}
                    className="flex cursor-pointer items-center justify-between gap-2 rounded-lg border border-gray-100 p-3 transition-colors hover:bg-gray-50 dark:border-gray-800 dark:hover:bg-gray-800/30"
                    onClick={onNavigateToDecisionLog}
                  >
                    <div className="min-w-0">
                      <div className="truncate text-sm text-gray-800 dark:text-gray-200">
                        {log.request_description}
                      </div>
                      <div className="mt-0.5 text-xs text-gray-400">{timeAgo(log.timestamp)}</div>
                    </div>
                    <DecisionBadge decision={log.decision} />
                  </div>
                ))}
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
};
