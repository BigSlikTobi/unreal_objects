const API_BASE = 'http://127.0.0.1:8001/v1';
const DECISION_BASE = 'http://127.0.0.1:8002/v1';

export const fetchGroups = async () => {
  const res = await fetch(`${API_BASE}/groups`);
  if (!res.ok) throw new Error('Failed to fetch groups');
  return res.json();
};

export const createGroup = async (name: string, description: string) => {
  const res = await fetch(`${API_BASE}/groups`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name, description }),
  });
  if (!res.ok) throw new Error('Failed to create group');
  return res.json();
};

export const getGroup = async (id: string) => {
  const res = await fetch(`${API_BASE}/groups/${id}`);
  if (!res.ok) throw new Error('Failed to get group');
  return res.json();
};

export const checkLLMConnection = async (provider: string, model: string, apiKey: string) => {
  const res = await fetch(`${DECISION_BASE}/llm/connection`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ provider, model, api_key: apiKey }),
  });
  if (!res.ok) throw new Error('LLM Connection failed');
  return res.json();
};

export const translateRule = async (data: any) => {
  const res = await fetch(`${DECISION_BASE}/llm/translate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
  if (!res.ok) throw new Error('Translation failed');
  return res.json();
};

export const updateDatapointDefinitions = async (groupId: string, defs: any[]) => {
  const res = await fetch(`${API_BASE}/groups/${groupId}/datapoints`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(defs),
  });
  if (!res.ok) throw new Error('Failed to update datapoint definitions');
  return res.json();
};

export const createRule = async (groupId: string, data: any) => {
  const res = await fetch(`${API_BASE}/groups/${groupId}/rules`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
  if (!res.ok) throw new Error('Failed to create rule');
  return res.json();
};

export const executeTest = async (groupId: string, description: string, context: Record<string, any>) => {
  const ctxStr = encodeURIComponent(JSON.stringify(context));
  const descStr = encodeURIComponent(description);
  const res = await fetch(`${DECISION_BASE}/decide?request_description=${descStr}&context=${ctxStr}&group_id=${groupId}`);
  if (!res.ok) throw new Error('Test evaluation failed');
  return res.json();
};
