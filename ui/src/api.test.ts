import { beforeEach, describe, expect, it, vi } from 'vitest';

import { createAgentRecord, deleteGroup, executeTest, fetchGroups, fetchProposals, getGroup, issueEnrollmentToken, reviewProposal, revokeCredential } from './api';

describe('api caching behavior', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it('fetchGroups bypasses browser cache', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue({
      ok: true,
      json: async () => [],
    } as Response);

    await fetchGroups();

    expect(fetchMock).toHaveBeenCalledWith(
      'http://127.0.0.1:8001/v1/groups',
      expect.objectContaining({ cache: 'no-store' })
    );
  });

  it('getGroup bypasses browser cache', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue({
      ok: true,
      json: async () => ({
        id: 'group_123',
        name: 'Payments',
        description: '',
        rules: [],
        datapoint_definitions: [],
      }),
    } as Response);

    await getGroup('group_123');

    expect(fetchMock).toHaveBeenCalledWith(
      'http://127.0.0.1:8001/v1/groups/group_123',
      expect.objectContaining({ cache: 'no-store' })
    );
  });

  it('deleteGroup sends the admin token header when provided', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue({
      ok: true,
    } as Response);

    await deleteGroup('group_123', 'sudo-secret');

    expect(fetchMock).toHaveBeenCalledWith(
      'http://127.0.0.1:8001/v1/groups/group_123',
      expect.objectContaining({
        method: 'DELETE',
        headers: expect.objectContaining({
          'X-Admin-Token': 'sudo-secret',
        }),
      })
    );
  });

  it('executeTest can scope evaluation to a selected rule', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue({
      ok: true,
      json: async () => ({
        outcome: 'APPROVE',
        request_id: 'req_123',
        matched_rules: [],
        matched_details: [],
      }),
    } as Response);

    await executeTest('group_123', 'Test', { amount: 100 }, 'rule_456');

    expect(fetchMock).toHaveBeenCalledWith(
      'http://127.0.0.1:8002/v1/decide?request_description=Test&context=%7B%22amount%22%3A100%7D&group_id=group_123&rule_id=rule_456'
    );
  });

  it('fetchProposals uses the shared tool agent base URL', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue({
      ok: true,
      json: async () => [],
    } as Response);

    await fetchProposals();

    expect(fetchMock).toHaveBeenCalledWith(
      'http://127.0.0.1:8003/v1/proposals',
      expect.objectContaining({ cache: 'no-store' })
    );
  });

  it('reviewProposal posts to the shared tool agent base URL', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue({
      ok: true,
      json: async () => ({ status: 'approved' }),
    } as Response);

    await reviewProposal('proposal_123', true, 'tobias');

    expect(fetchMock).toHaveBeenCalledWith(
      'http://127.0.0.1:8003/v1/proposals/proposal_123/review',
      expect.objectContaining({
        method: 'POST',
        headers: expect.objectContaining({
          'Content-Type': 'application/json',
        }),
      })
    );
  });

  it('createAgentRecord posts to the MCP admin API with the admin key header', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue({
      ok: true,
      json: async () => ({
        agent_id: 'agt_ops_01',
        name: 'Ops Agent',
        description: 'Shared runtime',
        status: 'active',
      }),
    } as Response);

    await createAgentRecord('http://127.0.0.1:8000', 'admin-secret', {
      name: 'Ops Agent',
      description: 'Shared runtime',
    });

    expect(fetchMock).toHaveBeenCalledWith(
      'http://127.0.0.1:8000/v1/admin/agents',
      expect.objectContaining({
        method: 'POST',
        headers: expect.objectContaining({
          'Content-Type': 'application/json',
          'X-Admin-Key': 'admin-secret',
        }),
      })
    );
  });

  it('issueEnrollmentToken posts the selected agent configuration', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue({
      ok: true,
      json: async () => ({
        enrollment_token: 'enroll_123',
      }),
    } as Response);

    await issueEnrollmentToken('http://127.0.0.1:8000', 'admin-secret', 'agt_ops_01', {
      credential_name: 'finance',
      scopes: ['finance:execute'],
      default_group_id: 'grp_finance',
      allowed_group_ids: ['grp_finance'],
    });

    expect(fetchMock).toHaveBeenCalledWith(
      'http://127.0.0.1:8000/v1/admin/agents/agt_ops_01/enrollment-tokens',
      expect.objectContaining({
        method: 'POST',
        headers: expect.objectContaining({
          'X-Admin-Key': 'admin-secret',
        }),
      })
    );
  });

  it('revokeCredential posts to the revoke endpoint with the admin key header', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue({
      ok: true,
      json: async () => ({
        credential_id: 'cred_finance_a',
        status: 'revoked',
      }),
    } as Response);

    await revokeCredential('http://127.0.0.1:8000', 'admin-secret', 'cred_finance_a');

    expect(fetchMock).toHaveBeenCalledWith(
      'http://127.0.0.1:8000/v1/admin/credentials/cred_finance_a/revoke',
      expect.objectContaining({
        method: 'POST',
        headers: expect.objectContaining({
          'X-Admin-Key': 'admin-secret',
        }),
      })
    );
  });
});
