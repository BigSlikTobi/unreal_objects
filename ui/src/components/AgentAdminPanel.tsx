import { type ChangeEvent, useEffect, useMemo, useState } from 'react';
import { KeyRound, RefreshCw, ShieldCheck, UserPlus, X } from 'lucide-react';

import {
  createAgentRecord,
  fetchGroups,
  issueEnrollmentToken,
  listAgents,
  listCredentials,
  revokeCredential,
} from '../api';
import type { AgentRecord, CredentialRecord, EnrollmentTokenIssue, RuleGroup } from '../types';

const DEFAULT_BASE_URL = 'http://127.0.0.1:8000';
const LATEST_TOKENS_STORAGE_KEY = 'mcp_admin_latest_enrollment_tokens';
const ENROLLMENT_DRAFTS_STORAGE_KEY = 'mcp_admin_enrollment_drafts';

type PersistedEnrollmentTokens = Record<string, EnrollmentTokenIssue>;
type EnrollmentDraft = {
  credentialName: string;
  scopes: string;
  defaultGroupId: string;
  allowedGroupIds: string[];
};
type PersistedEnrollmentDrafts = Record<string, EnrollmentDraft>;

const splitCsv = (value: string) => value
  .split(',')
  .map((entry) => entry.trim())
  .filter(Boolean);

const formatTokenMeta = (token: EnrollmentTokenIssue | undefined) => {
  if (!token) {
    return 'No enrollment token issued';
  }
  return `Latest token: ${token.credential_name}`;
};

export function AgentAdminPanel() {
  const [baseUrl, setBaseUrl] = useState(() => sessionStorage.getItem('mcp_admin_base_url') || DEFAULT_BASE_URL);
  const [adminApiKey, setAdminApiKey] = useState(() => sessionStorage.getItem('mcp_admin_api_key') || '');
  const [agents, setAgents] = useState<AgentRecord[]>([]);
  const [credentials, setCredentials] = useState<CredentialRecord[]>([]);
  const [ruleGroups, setRuleGroups] = useState<RuleGroup[]>([]);
  const [selectedAgentId, setSelectedAgentId] = useState('');
  const [isConnected, setIsConnected] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [createName, setCreateName] = useState('');
  const [createDescription, setCreateDescription] = useState('');
  const [credentialName, setCredentialName] = useState('');
  const [scopes, setScopes] = useState('');
  const [defaultGroupId, setDefaultGroupId] = useState('');
  const [allowedGroupIds, setAllowedGroupIds] = useState<string[]>([]);
  const [issuedToken, setIssuedToken] = useState<EnrollmentTokenIssue | null>(null);
  const [persistedTokens, setPersistedTokens] = useState<PersistedEnrollmentTokens>({});
  const [persistedDrafts, setPersistedDrafts] = useState<PersistedEnrollmentDrafts>({});

  const activeCredentials = useMemo(
    () => credentials.slice().sort((a, b) => a.name.localeCompare(b.name)),
    [credentials]
  );
  const agentCards = useMemo(() => agents, [agents]);
  const selectedAgent = useMemo(
    () => agentCards.find((agent) => agent.agent_id === selectedAgentId) ?? null,
    [agentCards, selectedAgentId]
  );
  const selectedAgentCredentials = useMemo(
    () => activeCredentials.filter((credential) => credential.agent_id === selectedAgentId),
    [activeCredentials, selectedAgentId]
  );
  const credentialCountByAgent = useMemo(() => {
    const counts: Record<string, number> = {};
    activeCredentials.forEach((credential) => {
      counts[credential.agent_id] = (counts[credential.agent_id] || 0) + 1;
    });
    return counts;
  }, [activeCredentials]);
  const effectiveAllowedGroupIds = useMemo(() => {
    if (!defaultGroupId) {
      return allowedGroupIds;
    }
    return allowedGroupIds.includes(defaultGroupId)
      ? allowedGroupIds
      : [defaultGroupId, ...allowedGroupIds];
  }, [allowedGroupIds, defaultGroupId]);

  useEffect(() => {
    const savedTokens = sessionStorage.getItem(LATEST_TOKENS_STORAGE_KEY);
    if (!savedTokens) {
      return;
    }
    try {
      setPersistedTokens(JSON.parse(savedTokens) as PersistedEnrollmentTokens);
    } catch {
      sessionStorage.removeItem(LATEST_TOKENS_STORAGE_KEY);
    }
  }, []);

  useEffect(() => {
    const savedDrafts = sessionStorage.getItem(ENROLLMENT_DRAFTS_STORAGE_KEY);
    if (!savedDrafts) {
      return;
    }
    try {
      setPersistedDrafts(JSON.parse(savedDrafts) as PersistedEnrollmentDrafts);
    } catch {
      sessionStorage.removeItem(ENROLLMENT_DRAFTS_STORAGE_KEY);
    }
  }, []);

  useEffect(() => {
    setIssuedToken(selectedAgentId ? persistedTokens[selectedAgentId] ?? null : null);
  }, [persistedTokens, selectedAgentId]);

  useEffect(() => {
    if (!selectedAgentId) {
      setCredentialName('');
      setScopes('');
      setDefaultGroupId('');
      setAllowedGroupIds([]);
      return;
    }
    const draft = persistedDrafts[selectedAgentId];
    setCredentialName(draft?.credentialName ?? '');
    setScopes(draft?.scopes ?? '');
    setDefaultGroupId(draft?.defaultGroupId ?? '');
    setAllowedGroupIds(draft?.allowedGroupIds ?? []);
  }, [selectedAgentId]);

  useEffect(() => {
    if (!selectedAgentId) {
      return;
    }
    setPersistedDrafts((current) => {
      const currentDraft = current[selectedAgentId];
      if (
        currentDraft
        && currentDraft.credentialName === credentialName
        && currentDraft.scopes === scopes
        && currentDraft.defaultGroupId === defaultGroupId
        && currentDraft.allowedGroupIds.length === allowedGroupIds.length
        && currentDraft.allowedGroupIds.every((value, index) => value === allowedGroupIds[index])
      ) {
        return current;
      }
      const nextDrafts = {
        ...current,
        [selectedAgentId]: {
          credentialName,
          scopes,
          defaultGroupId,
          allowedGroupIds,
        },
      };
      sessionStorage.setItem(ENROLLMENT_DRAFTS_STORAGE_KEY, JSON.stringify(nextDrafts));
      return nextDrafts;
    });
  }, [allowedGroupIds, credentialName, defaultGroupId, scopes, selectedAgentId]);

  useEffect(() => {
    if (adminApiKey.trim()) {
      refresh(baseUrl, adminApiKey);
    }
  }, []);

  const refresh = async (nextBaseUrl = baseUrl, nextAdminApiKey = adminApiKey) => {
    setIsLoading(true);
    setError(null);
    try {
      const [agentRows, credentialRows, groupRows] = await Promise.all([
        listAgents(nextBaseUrl, nextAdminApiKey),
        listCredentials(nextBaseUrl, nextAdminApiKey),
        fetchGroups(),
      ]);
      const safeAgents = agentRows ?? [];
      const safeCredentials = credentialRows ?? [];
      const safeGroups = groupRows ?? [];
      setAgents(safeAgents);
      setCredentials(safeCredentials);
      setRuleGroups(safeGroups);
      setPersistedTokens((current) => {
        const liveAgentIds = new Set(safeAgents.map((agent) => agent.agent_id));
        const nextTokens = Object.fromEntries(
          Object.entries(current).filter(([agentId]) => liveAgentIds.has(agentId))
        ) as PersistedEnrollmentTokens;
        if (Object.keys(nextTokens).length === 0) {
          sessionStorage.removeItem(LATEST_TOKENS_STORAGE_KEY);
        } else {
          sessionStorage.setItem(LATEST_TOKENS_STORAGE_KEY, JSON.stringify(nextTokens));
        }
        return nextTokens;
      });
      setSelectedAgentId((current) => (
        current && safeAgents.some((agent) => agent.agent_id === current) ? current : ''
      ));
      setIsConnected(true);
      setNotice('Connected to the admin API.');
      sessionStorage.setItem('mcp_admin_base_url', nextBaseUrl);
      sessionStorage.setItem('mcp_admin_api_key', nextAdminApiKey);
    } catch (err) {
      setRuleGroups([]);
      setError(err instanceof Error ? err.message : 'Failed to connect to the MCP admin API.');
      setIsConnected(false);
    } finally {
      setIsLoading(false);
    }
  };

  const handleCreateAgent = async () => {
    if (!createName.trim() || !adminApiKey.trim()) return;
    setIsLoading(true);
    setError(null);
    try {
      const created = await createAgentRecord(baseUrl, adminApiKey, {
        name: createName.trim(),
        description: createDescription.trim(),
      });
      setCreateName('');
      setCreateDescription('');
      await refresh(baseUrl, adminApiKey);
      setSelectedAgentId(created.agent_id);
      setNotice(`Created agent '${created.name}'.`);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to create agent.');
    } finally {
      setIsLoading(false);
    }
  };

  const handleAllowedGroupIdsChange = (groupId: string) => {
    setAllowedGroupIds((current) => (
      current.includes(groupId)
        ? current.filter((value) => value !== groupId)
        : [...current, groupId]
    ));
  };

  const handleIssueToken = async () => {
    if (!selectedAgentId || !credentialName.trim()) return;
    setIsLoading(true);
    setError(null);
    try {
      const issued = await issueEnrollmentToken(baseUrl, adminApiKey, selectedAgentId, {
        credential_name: credentialName.trim(),
        scopes: splitCsv(scopes),
        default_group_id: defaultGroupId.trim() || undefined,
        allowed_group_ids: effectiveAllowedGroupIds,
      });
      setPersistedTokens((current) => {
        const nextTokens = {
          ...current,
          [issued.agent_id]: issued,
        };
        sessionStorage.setItem(LATEST_TOKENS_STORAGE_KEY, JSON.stringify(nextTokens));
        return nextTokens;
      });
      setCredentialName('');
      setScopes('');
      setDefaultGroupId('');
      setAllowedGroupIds([]);
      setPersistedDrafts((current) => {
        if (!selectedAgentId) {
          return current;
        }
        const nextDrafts = { ...current };
        delete nextDrafts[selectedAgentId];
        if (Object.keys(nextDrafts).length === 0) {
          sessionStorage.removeItem(ENROLLMENT_DRAFTS_STORAGE_KEY);
        } else {
          sessionStorage.setItem(ENROLLMENT_DRAFTS_STORAGE_KEY, JSON.stringify(nextDrafts));
        }
        return nextDrafts;
      });
      await refresh(baseUrl, adminApiKey);
      setNotice(`Issued a new enrollment token for '${issued.credential_name}'.`);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to issue enrollment token.');
    } finally {
      setIsLoading(false);
    }
  };

  const handleRevokeCredential = async (credentialId: string) => {
    setIsLoading(true);
    setError(null);
    try {
      const revoked = await revokeCredential(baseUrl, adminApiKey, credentialId);
      setCredentials((current) => current.map((credential) => (
        credential.credential_id === revoked.credential_id ? revoked : credential
      )));
      setNotice(`Revoked credential '${revoked.name}'.`);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to revoke credential.');
    } finally {
      setIsLoading(false);
    }
  };

  const canIssueToken = (
    isConnected
    && !isLoading
    && !!selectedAgentId
    && !!credentialName.trim()
  );

  return (
    <section className="space-y-4" aria-labelledby="agent-admin-heading">
      <div className="flex items-center gap-2">
        <ShieldCheck size={18} className="text-emerald-500" />
        <h3 id="agent-admin-heading" className="text-base font-semibold text-gray-800 dark:text-gray-100">
          Agent Admin
        </h3>
      </div>
      <p className="text-sm text-gray-500 dark:text-gray-400">
        Manage agent identities, enrollment tokens, and credential revocation in one persistent workspace.
      </p>

      <div className="grid gap-3 md:grid-cols-[minmax(0,2fr)_minmax(0,1fr)]">
        <div>
          <label htmlFor="mcp-base-url" className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
            MCP Base URL
          </label>
          <input
            id="mcp-base-url"
            aria-label="MCP Base URL"
            type="text"
            value={baseUrl}
            onChange={(e) => setBaseUrl(e.target.value)}
            placeholder="http://127.0.0.1:8000"
            className="w-full bg-gray-50 dark:bg-gray-900 border border-gray-300 dark:border-gray-700 rounded-lg px-3 py-2 text-sm text-gray-900 dark:text-gray-100 placeholder-gray-400"
          />
        </div>
        <div>
          <label htmlFor="admin-api-key" className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
            Admin API Key
          </label>
          <input
            id="admin-api-key"
            aria-label="Admin API Key"
            type="password"
            value={adminApiKey}
            onChange={(e) => setAdminApiKey(e.target.value)}
            placeholder="admin-secret"
            className="w-full bg-gray-50 dark:bg-gray-900 border border-gray-300 dark:border-gray-700 rounded-lg px-3 py-2 text-sm text-gray-900 dark:text-gray-100 placeholder-gray-400"
          />
        </div>
      </div>

      <div className="flex items-center gap-3">
        <button
          onClick={() => refresh()}
          disabled={isLoading || !baseUrl.trim() || !adminApiKey.trim()}
          className="inline-flex items-center gap-2 rounded-lg bg-emerald-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-emerald-700 disabled:opacity-50"
        >
          {isLoading ? <RefreshCw size={15} className="animate-spin" /> : <ShieldCheck size={15} />}
          Connect Admin API
        </button>
        {isConnected && (
          <span className="text-sm font-medium text-emerald-600 dark:text-emerald-400">
            Connected
          </span>
        )}
      </div>

      {error && (
        <div className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700 dark:border-red-900/40 dark:bg-red-950/20 dark:text-red-300">
          {error}
        </div>
      )}

      {notice && (
        <div className="rounded-lg border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-700 dark:border-emerald-900/40 dark:bg-emerald-950/20 dark:text-emerald-300">
          {notice}
        </div>
      )}

      <div className="rounded-3xl border border-gray-200 bg-gray-50 p-5 dark:border-gray-700 dark:bg-gray-900/40">
        <div className="mb-4 flex items-center justify-between gap-3">
          <div>
            <h4 className="text-sm font-semibold text-gray-900 dark:text-gray-100">Agents</h4>
            <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">
              Open an agent card to manage its credentials and enrollment flow.
            </p>
          </div>
        </div>

        <div className="grid grid-cols-1 gap-4 xl:grid-cols-3">
          <div className="rounded-3xl border border-dashed border-blue-300 bg-blue-50/80 p-5 dark:border-blue-800/70 dark:bg-blue-950/20">
            <div className="mb-3 flex items-center gap-2 text-sm font-semibold text-blue-900 dark:text-blue-100">
              <UserPlus size={16} />
              Create Agent
            </div>
            <div className="space-y-3">
              <div>
                <label htmlFor="agent-name" className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                  Agent Name
                </label>
                <input
                  id="agent-name"
                  aria-label="Agent Name"
                  type="text"
                  value={createName}
                  onChange={(e) => setCreateName(e.target.value)}
                  className="w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm text-gray-900 dark:border-gray-700 dark:bg-gray-900 dark:text-gray-100"
                />
              </div>
              <div>
                <label htmlFor="agent-description" className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                  Agent Description
                </label>
                <input
                  id="agent-description"
                  aria-label="Agent Description"
                  type="text"
                  value={createDescription}
                  onChange={(e) => setCreateDescription(e.target.value)}
                  className="w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm text-gray-900 dark:border-gray-700 dark:bg-gray-900 dark:text-gray-100"
                />
              </div>
              <button
                onClick={handleCreateAgent}
                disabled={isLoading || !createName.trim() || !adminApiKey.trim()}
                className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-blue-700 disabled:opacity-50"
              >
                Create Agent
              </button>
            </div>
          </div>

          {agentCards.length === 0 ? (
            <div className="rounded-3xl border border-dashed border-gray-300 bg-white p-5 text-sm text-gray-500 dark:border-gray-700 dark:bg-gray-950/40 dark:text-gray-400">
              No agents loaded yet.
            </div>
          ) : (
            agentCards.map((agent) => (
              <article
                key={agent.agent_id}
                className={`rounded-3xl border p-5 transition-colors ${
                  selectedAgentId === agent.agent_id
                    ? 'border-blue-300 bg-blue-50 dark:border-blue-700 dark:bg-blue-950/30'
                    : 'border-emerald-200 bg-white dark:border-emerald-900/40 dark:bg-gray-950/60'
                }`}
              >
                <div>
                  <div className="flex flex-wrap items-center gap-2">
                    <h4 className="text-base font-semibold text-gray-900 dark:text-gray-100">{agent.name}</h4>
                    <span className={`rounded-full px-2 py-0.5 text-[11px] font-semibold uppercase tracking-wide ${
                      agent.status === 'active'
                        ? 'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-300'
                        : 'bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-300'
                    }`}>
                      {agent.status}
                    </span>
                  </div>
                  <p className="mt-2 text-sm text-gray-600 dark:text-gray-300">
                    {agent.description || 'No description provided.'}
                  </p>
                  <div className="mt-4 grid grid-cols-2 gap-3 text-xs text-gray-600 dark:text-gray-300">
                    <div className="rounded-2xl bg-gray-100 px-3 py-2 dark:bg-gray-800">
                      <div className="font-semibold text-gray-800 dark:text-gray-100">
                        {credentialCountByAgent[agent.agent_id] ?? 0} credentials
                      </div>
                      <div className="mt-1 text-gray-500 dark:text-gray-400">
                        Active access records for this agent
                      </div>
                    </div>
                    <div className="rounded-2xl bg-gray-100 px-3 py-2 dark:bg-gray-800">
                      <div className="font-semibold text-gray-800 dark:text-gray-100">
                        {formatTokenMeta(persistedTokens[agent.agent_id])}
                      </div>
                      <div className="mt-1 text-gray-500 dark:text-gray-400">
                        {persistedTokens[agent.agent_id]
                          ? new Date(persistedTokens[agent.agent_id].expires_at).toLocaleString()
                          : 'Issue a token to bootstrap enrollment'}
                      </div>
                    </div>
                  </div>
                  <p className="mt-3 text-xs font-mono text-gray-500 dark:text-gray-400">{agent.agent_id}</p>
                </div>

                <div className="mt-4">
                  <button
                    type="button"
                    onClick={() => setSelectedAgentId(agent.agent_id)}
                    className="rounded-lg border border-blue-200 bg-blue-50 px-3 py-1.5 text-sm font-medium text-blue-700 transition-colors hover:bg-blue-100 dark:border-blue-900/40 dark:bg-blue-900/20 dark:text-blue-300 dark:hover:bg-blue-900/30"
                    aria-label={`Open Agent ${agent.name}`}
                  >
                    Open Agent
                  </button>
                </div>
              </article>
            ))
          )}
        </div>
      </div>

      {selectedAgent && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4 backdrop-blur-sm">
          <div
            role="dialog"
            aria-modal="true"
            aria-label={`Agent Context for ${selectedAgent.name}`}
            className="flex max-h-[90vh] w-full max-w-6xl flex-col overflow-hidden rounded-3xl bg-white shadow-2xl dark:bg-gray-900"
          >
            <div className="flex items-start justify-between gap-4 border-b border-gray-200 px-6 py-5 dark:border-gray-800">
              <div>
                <h4 className="text-lg font-semibold text-gray-900 dark:text-gray-100">Agent Context</h4>
                <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
                  Managing <span className="font-medium text-gray-700 dark:text-gray-200">{selectedAgent.name}</span>.
                  Issue credentials, review the latest enrollment token, and revoke active access below.
                </p>
              </div>
              <button
                type="button"
                onClick={() => setSelectedAgentId('')}
                aria-label="Close Agent Context"
                className="rounded-lg p-2 text-gray-500 transition-colors hover:bg-gray-100 hover:text-gray-700 dark:text-gray-400 dark:hover:bg-gray-800 dark:hover:text-gray-200"
              >
                <X size={18} />
              </button>
            </div>

            <div className="overflow-y-auto p-6">
              <div className="grid gap-4 xl:grid-cols-2">
                <div className="rounded-xl border border-gray-200 bg-gray-50 p-4 dark:border-gray-700 dark:bg-gray-900/40">
                  <div className="mb-3 flex items-center gap-2 text-sm font-semibold text-gray-800 dark:text-gray-100">
                    <UserPlus size={16} />
                    Issue Enrollment Token
                  </div>
                  <div className="space-y-3">
                    <div>
                      <label htmlFor="selected-agent-name" className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                        Agent
                      </label>
                      <input
                        id="selected-agent-name"
                        aria-label="Agent"
                        type="text"
                        value={selectedAgent.name}
                        readOnly
                        className="w-full rounded-lg border border-gray-300 bg-gray-100 px-3 py-2 text-sm text-gray-900 dark:border-gray-700 dark:bg-gray-800 dark:text-gray-100"
                      />
                    </div>
                    <div>
                      <label htmlFor="credential-name" className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                        Credential Name
                      </label>
                      <input
                        id="credential-name"
                        aria-label="Credential Name"
                        type="text"
                        value={credentialName}
                        onChange={(e) => setCredentialName(e.target.value)}
                        className="w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm text-gray-900 dark:border-gray-700 dark:bg-gray-900 dark:text-gray-100"
                      />
                    </div>
                    <div>
                      <label htmlFor="scopes" className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                        Scopes (optional)
                      </label>
                      <input
                        id="scopes"
                        aria-label="Scopes"
                        type="text"
                        value={scopes}
                        onChange={(e) => setScopes(e.target.value)}
                        placeholder="finance:execute, audit:read"
                        className="w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm text-gray-900 dark:border-gray-700 dark:bg-gray-900 dark:text-gray-100"
                      />
                      <div className="mt-1 text-xs text-gray-500 dark:text-gray-400">
                        Scopes are documented and stored, but rule-group bindings are the active enforcement layer right now.
                      </div>
                    </div>
                    <div>
                      <label htmlFor="default-group-id" className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                        Default Group
                      </label>
                      <select
                        id="default-group-id"
                        aria-label="Default Group"
                        value={defaultGroupId}
                        onChange={(e) => setDefaultGroupId(e.target.value)}
                        className="w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm text-gray-900 dark:border-gray-700 dark:bg-gray-900 dark:text-gray-100"
                      >
                        <option value="">No default group</option>
                        {ruleGroups.map((group) => (
                          <option key={group.id} value={group.id}>
                            {group.name} ({group.id})
                          </option>
                        ))}
                      </select>
                    </div>
                    <div>
                      <span className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                        Allowed Groups
                      </span>
                      <div
                        aria-label="Allowed Groups"
                        className="space-y-2 rounded-lg border border-gray-300 bg-white px-3 py-2 dark:border-gray-700 dark:bg-gray-900"
                      >
                        {ruleGroups.length === 0 ? (
                          <div className="text-sm text-gray-500 dark:text-gray-400">
                            No rule groups available.
                          </div>
                        ) : (
                          ruleGroups.map((group) => (
                            <label
                              key={group.id}
                              className="flex items-start gap-3 rounded-md px-2 py-1 text-sm text-gray-900 hover:bg-gray-50 dark:text-gray-100 dark:hover:bg-gray-800"
                            >
                              <input
                                type="checkbox"
                                checked={effectiveAllowedGroupIds.includes(group.id)}
                                disabled={group.id === defaultGroupId}
                                onChange={() => handleAllowedGroupIdsChange(group.id)}
                                className="mt-0.5 h-4 w-4 rounded border-gray-300 text-violet-600 focus:ring-violet-500 disabled:cursor-not-allowed disabled:opacity-50 dark:border-gray-600 dark:bg-gray-900"
                              />
                              <span className={group.id === defaultGroupId ? 'text-gray-400 dark:text-gray-500' : ''}>
                                {group.name} ({group.id})
                                {group.id === defaultGroupId ? ' default' : ''}
                              </span>
                            </label>
                          ))
                        )}
                      </div>
                      <div className="mt-1 text-xs text-gray-500 dark:text-gray-400">
                        Choose exactly which rule groups this enrollment token may use.
                      </div>
                    </div>
                    <button
                      onClick={handleIssueToken}
                      type="button"
                      disabled={!canIssueToken}
                      className="rounded-lg bg-violet-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-violet-700 disabled:opacity-50"
                    >
                      Issue Enrollment Token
                    </button>
                    {!isConnected && (
                      <div className="text-xs text-amber-600 dark:text-amber-400">
                        Connect to the admin API before issuing credentials.
                      </div>
                    )}
                  </div>
                </div>
                <div className="rounded-xl border border-gray-200 bg-gray-50 p-4 dark:border-gray-700 dark:bg-gray-900/40">
                  <div className="mb-3 flex items-center justify-between gap-2">
                    <div className="text-sm font-semibold text-gray-800 dark:text-gray-100">Credentials</div>
                    <button
                      onClick={() => refresh()}
                      disabled={isLoading || !adminApiKey.trim()}
                      className="inline-flex items-center gap-2 rounded-lg border border-gray-300 px-3 py-1.5 text-sm font-medium text-gray-700 transition-colors hover:bg-gray-100 disabled:opacity-50 dark:border-gray-700 dark:text-gray-200 dark:hover:bg-gray-800"
                    >
                      <RefreshCw size={14} className={isLoading ? 'animate-spin' : ''} />
                      Refresh
                    </button>
                  </div>
                  <div className="space-y-2">
                    {issuedToken && (
                      <div className="rounded-lg border border-emerald-200 bg-emerald-50 p-3 text-sm text-emerald-900 dark:border-emerald-900/40 dark:bg-emerald-950/20 dark:text-emerald-100">
                        <div className="font-semibold">One-time enrollment token</div>
                        <div className="mt-1 text-xs">
                          Agent: {agents.find((agent) => agent.agent_id === issuedToken.agent_id)?.name ?? issuedToken.agent_id}
                        </div>
                        <div className="mt-1 break-all font-mono text-xs">{issuedToken.enrollment_token}</div>
                        <div className="mt-2 text-xs">
                          Expires at {new Date(issuedToken.expires_at).toLocaleString()}
                        </div>
                        <div className="mt-2 text-xs text-emerald-800 dark:text-emerald-200">
                          This token stays visible in this workspace until you issue another one or clear session storage.
                        </div>
                      </div>
                    )}
                    {selectedAgentCredentials.length === 0 ? (
                      <div className="text-sm text-gray-500 dark:text-gray-400">No credentials loaded for this agent yet.</div>
                    ) : (
                      selectedAgentCredentials.map((credential) => (
                        <div
                          key={credential.credential_id}
                          className="flex flex-col gap-3 rounded-lg border border-gray-200 bg-white p-3 dark:border-gray-700 dark:bg-gray-900 md:flex-row md:items-center md:justify-between"
                        >
                          <div className="min-w-0">
                            <div className="font-medium text-gray-800 dark:text-gray-100">
                              {credential.name}
                            </div>
                            <div className="text-xs text-gray-500 dark:text-gray-400">
                              {credential.credential_id}
                              {credential.scopes.length > 0 ? ` · ${credential.scopes.join(', ')}` : ' · no scopes assigned'}
                            </div>
                            <div className="mt-1 text-xs font-medium uppercase tracking-wide text-gray-500 dark:text-gray-400">
                              {credential.status}
                            </div>
                          </div>
                          <button
                            onClick={() => handleRevokeCredential(credential.credential_id)}
                            disabled={isLoading || credential.status !== 'active'}
                            className="rounded-lg border border-red-200 px-3 py-2 text-sm font-medium text-red-700 transition-colors hover:bg-red-50 disabled:opacity-50 dark:border-red-900/40 dark:text-red-300 dark:hover:bg-red-950/20"
                            aria-label={`Revoke ${credential.name}`}
                          >
                            Revoke {credential.name}
                          </button>
                        </div>
                      ))
                    )}
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}
    </section>
  );
}
