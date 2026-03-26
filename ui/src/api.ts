import type {
  AgentRecord,
  AtomicLogEntry,
  CredentialRecord,
  DatapointDefinition,
  DecisionChain,
  DecisionResult,
  EnrollmentTokenIssue,
  GenerateSchemaRequest,
  LlmConfig,
  ProposedField,
  Rule,
  RuleGroup,
  RulePayload,
  RuleTranslation,
  SchemaField,
  SchemaProposal,
} from './types';

export interface TranslateRuleRequest extends LlmConfig {
  natural_language: string;
  feature: string;
  name: string;
  context_schema?: Record<string, string>;
  datapoint_definitions?: DatapointDefinition[];
}

export class ConceptMismatchError extends Error {
  proposedField?: ProposedField;
  constructor(message: string, proposedField?: ProposedField) {
    super(message);
    this.name = 'ConceptMismatchError';
    this.proposedField = proposedField;
  }
}

const API_BASE = 'http://127.0.0.1:8001/v1';
const DECISION_BASE = 'http://127.0.0.1:8002/v1';

const buildAdminHeaders = (adminApiKey: string) => ({
  'Content-Type': 'application/json',
  'X-Admin-Key': adminApiKey,
});

export const fetchGroups = async (): Promise<RuleGroup[]> => {
  const res = await fetch(`${API_BASE}/groups`, {
    cache: 'no-store',
  });
  if (!res.ok) throw new Error('Failed to fetch groups');
  return res.json();
};

export const createGroup = async (name: string, description: string): Promise<RuleGroup> => {
  const res = await fetch(`${API_BASE}/groups`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name, description }),
  });
  if (!res.ok) throw new Error('Failed to create group');
  return res.json();
};

export const deleteGroup = async (id: string, adminToken?: string): Promise<void> => {
  const headers: Record<string, string> = {};
  if (adminToken?.trim()) {
    headers['X-Admin-Token'] = adminToken.trim();
  }
  const res = await fetch(`${API_BASE}/groups/${id}`, {
    method: 'DELETE',
    headers,
  });
  if (!res.ok) {
    let body: Record<string, unknown> | null = null;
    try { body = await res.json(); } catch { /* ignore */ }
    throw new Error((body?.detail as string) || 'Failed to delete group');
  }
};

export const getGroup = async (id: string): Promise<RuleGroup> => {
  const res = await fetch(`${API_BASE}/groups/${id}`, {
    cache: 'no-store',
  });
  if (!res.ok) throw new Error('Failed to get group');
  return res.json();
};

export const checkLLMConnection = async (provider: string, model: string, apiKey: string): Promise<unknown> => {
  const res = await fetch(`${DECISION_BASE}/llm/connection`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ provider, model, api_key: apiKey }),
  });
  if (!res.ok) throw new Error('LLM Connection failed');
  return res.json();
};

export const translateRule = async (data: TranslateRuleRequest): Promise<RuleTranslation> => {
  const res = await fetch(`${DECISION_BASE}/llm/translate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
  if (!res.ok) {
    let body: Record<string, unknown> | null = null;
    try { body = await res.json(); } catch { /* ignore */ }
    if (res.status === 422) {
      throw new ConceptMismatchError(
        (body?.detail as string) || 'Concept not in schema',
        body?.proposed_field as ProposedField | undefined,
      );
    }
    throw new Error((body?.detail as string) || 'Translation failed');
  }
  return res.json();
};

export const updateDatapointDefinitions = async (groupId: string, defs: DatapointDefinition[]): Promise<RuleGroup> => {
  const res = await fetch(`${API_BASE}/groups/${groupId}/datapoints`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(defs),
  });
  if (!res.ok) throw new Error('Failed to update datapoint definitions');
  return res.json();
};

export const createRule = async (groupId: string, data: RulePayload): Promise<Rule> => {
  const res = await fetch(`${API_BASE}/groups/${groupId}/rules`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
  if (!res.ok) throw new Error('Failed to create rule');
  return res.json();
};

export const updateRule = async (groupId: string, ruleId: string, data: RulePayload): Promise<Rule> => {
  const res = await fetch(`${API_BASE}/groups/${groupId}/rules/${ruleId}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
  if (!res.ok) throw new Error('Failed to update rule');
  return res.json();
};

export const executeTest = async (
  groupId: string,
  description: string,
  context: Record<string, string | number | boolean>,
  ruleId?: string
): Promise<DecisionResult> => {
  const ctxStr = encodeURIComponent(JSON.stringify(context));
  const descStr = encodeURIComponent(description);
  const ruleStr = ruleId ? `&rule_id=${encodeURIComponent(ruleId)}` : '';
  const res = await fetch(
    `${DECISION_BASE}/decide?request_description=${descStr}&context=${ctxStr}&group_id=${groupId}${ruleStr}`
  );
  if (!res.ok) throw new Error('Test evaluation failed');
  return res.json();
};

export const listAgents = async (baseUrl: string, adminApiKey: string): Promise<AgentRecord[]> => {
  const res = await fetch(`${baseUrl}/v1/admin/agents`, {
    headers: { 'X-Admin-Key': adminApiKey },
    cache: 'no-store',
  });
  if (!res.ok) throw new Error('Failed to fetch agents');
  return res.json();
};

export const createAgentRecord = async (
  baseUrl: string,
  adminApiKey: string,
  payload: { name: string; description: string }
): Promise<AgentRecord> => {
  const res = await fetch(`${baseUrl}/v1/admin/agents`, {
    method: 'POST',
    headers: buildAdminHeaders(adminApiKey),
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error('Failed to create agent');
  return res.json();
};

export const listCredentials = async (baseUrl: string, adminApiKey: string): Promise<CredentialRecord[]> => {
  const res = await fetch(`${baseUrl}/v1/admin/credentials`, {
    headers: { 'X-Admin-Key': adminApiKey },
    cache: 'no-store',
  });
  if (!res.ok) throw new Error('Failed to fetch credentials');
  return res.json();
};

export const issueEnrollmentToken = async (
  baseUrl: string,
  adminApiKey: string,
  agentId: string,
  payload: {
    credential_name: string;
    scopes: string[];
    default_group_id?: string;
    allowed_group_ids: string[];
  }
): Promise<EnrollmentTokenIssue> => {
  const res = await fetch(`${baseUrl}/v1/admin/agents/${agentId}/enrollment-tokens`, {
    method: 'POST',
    headers: buildAdminHeaders(adminApiKey),
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error('Failed to issue enrollment token');
  return res.json();
};

export interface SchemaEntry {
  key: string;
  name: string;
  description: string;
  schema: Record<string, string>;
}

export interface ToolProposal {
  id: string;
  tool_name: string;
  action_description: string;
  trigger_rule: string;
  trigger_group: string;
  reason: string;
  generated_code: string;
  created_at: string;
  reviewer?: string | null;
  status: 'pending_review' | 'approved' | 'rejected';
}

export const fetchSchemas = async (): Promise<SchemaEntry[]> => {
  const res = await fetch(`${DECISION_BASE}/schemas`, { cache: 'no-store' });
  if (!res.ok) throw new Error('Failed to fetch schemas');
  return res.json();
};

export const fetchProposals = async (): Promise<ToolProposal[]> => {
  const res = await fetch('http://127.0.0.1:8003/v1/proposals', { cache: 'no-store' });
  if (!res.ok) throw new Error('Failed to fetch tool proposals');
  return res.json();
};

export const reviewProposal = async (
  proposalId: string,
  approved: boolean,
  reviewer: string,
): Promise<{ status?: string; proposal_id?: string; message?: string }> => {
  const res = await fetch(`http://127.0.0.1:8003/v1/proposals/${proposalId}/review`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ approved, reviewer }),
  });
  if (!res.ok) {
    let body: Record<string, unknown> | null = null;
    try { body = await res.json(); } catch { /* ignore */ }
    throw new Error((body?.detail as string) || 'Failed to review tool proposal');
  }
  return res.json();
};

export const generateSchema = async (data: GenerateSchemaRequest): Promise<SchemaProposal> => {
  const res = await fetch(`${DECISION_BASE}/llm/schema`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
  if (!res.ok) {
    let body: Record<string, unknown> | null = null;
    try { body = await res.json(); } catch { /* ignore */ }
    throw new Error((body?.detail as string) || 'Schema generation failed');
  }
  return res.json();
};

export const saveSchema = async (proposal: Omit<SchemaProposal, 'message'> & { fields: SchemaField[] }, adminApiKey?: string): Promise<{ path: string; name: string }> => {
  const headers: Record<string, string> = { 'Content-Type': 'application/json' };
  if (adminApiKey) {
    headers['X-Admin-Key'] = adminApiKey;
  }
  const res = await fetch(`${DECISION_BASE}/schemas/save`, {
    method: 'POST',
    headers,
    body: JSON.stringify(proposal),
  });
  if (!res.ok) {
    let body: Record<string, unknown> | null = null;
    try { body = await res.json(); } catch { /* ignore */ }
    throw new Error((body?.detail as string) || 'Save schema failed');
  }
  return res.json();
};

export const fetchAtomicLogs = async (): Promise<AtomicLogEntry[]> => {
  const res = await fetch(`${DECISION_BASE}/logs/atomic`, { cache: 'no-store' });
  if (!res.ok) throw new Error('Failed to fetch decision logs');
  return res.json();
};

export const fetchDecisionChain = async (requestId: string): Promise<DecisionChain> => {
  const res = await fetch(`${DECISION_BASE}/logs/chains/${encodeURIComponent(requestId)}`, { cache: 'no-store' });
  if (!res.ok) throw new Error('Failed to fetch decision chain');
  return res.json();
};

export const revokeCredential = async (
  baseUrl: string,
  adminApiKey: string,
  credentialId: string
): Promise<CredentialRecord> => {
  const res = await fetch(`${baseUrl}/v1/admin/credentials/${credentialId}/revoke`, {
    method: 'POST',
    headers: { 'X-Admin-Key': adminApiKey },
  });
  if (!res.ok) throw new Error('Failed to revoke credential');
  return res.json();
};
