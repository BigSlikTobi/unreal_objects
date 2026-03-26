import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { AgentAdminPanel } from './AgentAdminPanel';
import {
  createAgentRecord,
  fetchGroups,
  issueEnrollmentToken,
  listAgents,
  listCredentials,
  revokeCredential,
} from '../api';

vi.mock('../api', () => ({
  listAgents: vi.fn(),
  createAgentRecord: vi.fn(),
  listCredentials: vi.fn(),
  issueEnrollmentToken: vi.fn(),
  revokeCredential: vi.fn(),
  fetchGroups: vi.fn(),
}));

describe('AgentAdminPanel', () => {
  beforeEach(() => {
    sessionStorage.clear();
    vi.clearAllMocks();
    vi.mocked(fetchGroups).mockResolvedValue([
      {
        id: 'grp_finance',
        name: 'Finance',
        description: 'Finance rules',
        rules: [],
        datapoint_definitions: [],
      },
      {
        id: 'grp_support',
        name: 'Support',
        description: 'Support rules',
        rules: [],
        datapoint_definitions: [],
      },
    ]);
    vi.mocked(listAgents)
      .mockResolvedValueOnce([])
      .mockResolvedValueOnce([
        {
          agent_id: 'agt_ops_01',
          name: 'Ops Agent',
          description: 'Shared runtime',
          status: 'active',
        },
      ])
      .mockResolvedValueOnce([
        {
          agent_id: 'agt_ops_01',
          name: 'Ops Agent',
          description: 'Shared runtime',
          status: 'active',
        },
      ]);
    vi.mocked(listCredentials)
      .mockResolvedValueOnce([
        {
          credential_id: 'cred_finance_a',
          agent_id: 'agt_ops_01',
          name: 'finance',
          client_id: 'uo_client_finance_a',
          scopes: ['finance:execute'],
          default_group_id: 'grp_finance',
          allowed_group_ids: ['grp_finance'],
          status: 'active',
        },
      ])
      .mockResolvedValueOnce([
        {
          credential_id: 'cred_finance_a',
          agent_id: 'agt_ops_01',
          name: 'finance',
          client_id: 'uo_client_finance_a',
          scopes: ['finance:execute'],
          default_group_id: 'grp_finance',
          allowed_group_ids: ['grp_finance'],
          status: 'active',
        },
      ])
      .mockResolvedValueOnce([
        {
          credential_id: 'cred_finance_a',
          agent_id: 'agt_ops_01',
          name: 'finance',
          client_id: 'uo_client_finance_a',
          scopes: ['finance:execute'],
          default_group_id: 'grp_finance',
          allowed_group_ids: ['grp_finance'],
          status: 'active',
        },
      ]);
    vi.mocked(createAgentRecord).mockResolvedValue({
      agent_id: 'agt_ops_01',
      name: 'Ops Agent',
      description: 'Shared runtime',
      status: 'active',
    });
    vi.mocked(issueEnrollmentToken).mockResolvedValue({
      enrollment_token: 'enroll_123',
      enrollment_token_id: 'enrollment_row_1',
      agent_id: 'agt_ops_01',
      credential_name: 'finance',
      scopes: [],
      default_group_id: 'grp_finance',
      allowed_group_ids: ['grp_finance'],
      expires_at: '2026-03-03T12:00:00Z',
    });
    vi.mocked(revokeCredential).mockResolvedValue({
      credential_id: 'cred_finance_a',
      agent_id: 'agt_ops_01',
      name: 'finance',
      client_id: 'uo_client_finance_a',
      scopes: ['finance:execute'],
      default_group_id: 'grp_finance',
      allowed_group_ids: ['grp_finance'],
      status: 'revoked',
    });
  });

  it('creates agents, issues enrollment tokens, and revokes credentials', async () => {
    const user = userEvent.setup();
    render(<AgentAdminPanel />);

    await user.clear(screen.getByLabelText(/mcp base url/i));
    await user.type(screen.getByLabelText(/mcp base url/i), 'http://127.0.0.1:8000');
    await user.type(screen.getByLabelText(/admin api key/i), 'admin-secret');
    await user.click(screen.getByRole('button', { name: /connect admin api/i }));

    await waitFor(() => {
      expect(listAgents).toHaveBeenCalledWith('http://127.0.0.1:8000', 'admin-secret');
      expect(listCredentials).toHaveBeenCalledWith('http://127.0.0.1:8000', 'admin-secret');
    });

    await user.type(screen.getByLabelText(/agent name/i), 'Ops Agent');
    await user.type(screen.getByLabelText(/agent description/i), 'Shared runtime');
    await user.click(screen.getByRole('button', { name: /create agent/i }));

    await waitFor(() => {
      expect(createAgentRecord).toHaveBeenCalledWith('http://127.0.0.1:8000', 'admin-secret', {
        name: 'Ops Agent',
        description: 'Shared runtime',
      });
    });

    await screen.findAllByText('Ops Agent');
    await user.click(screen.getByRole('button', { name: /open agent ops agent/i }));
    expect(await screen.findByRole('dialog', { name: /agent context for ops agent/i })).toBeTruthy();

    await user.type(screen.getByLabelText(/credential name/i), 'finance');
    await user.selectOptions(screen.getByLabelText(/default group/i), 'grp_finance');
    await user.click(screen.getByRole('checkbox', { name: /finance \(grp_finance\)/i }));
    await user.click(screen.getByRole('checkbox', { name: /support \(grp_support\)/i }));
    await user.click(screen.getByRole('button', { name: /issue enrollment token/i }));

    await waitFor(() => {
      expect(issueEnrollmentToken).toHaveBeenCalledWith('http://127.0.0.1:8000', 'admin-secret', 'agt_ops_01', {
        credential_name: 'finance',
        scopes: [],
        default_group_id: 'grp_finance',
        allowed_group_ids: ['grp_finance', 'grp_support'],
      });
    });

    await waitFor(() => {
      expect(screen.getAllByText(/enroll_123/i).length).toBeGreaterThan(0);
    });

    await user.click(screen.getByRole('button', { name: /revoke finance/i }));

    await waitFor(() => {
      expect(revokeCredential).toHaveBeenCalledWith('http://127.0.0.1:8000', 'admin-secret', 'cred_finance_a');
    });

    await screen.findByText(/revoked credential 'finance'/i);
  });

  it('auto-reconnects from saved admin settings on remount', async () => {
    sessionStorage.setItem('mcp_admin_base_url', 'http://127.0.0.1:8000');
    sessionStorage.setItem('mcp_admin_api_key', 'admin-secret');

    render(<AgentAdminPanel />);

    await waitFor(() => {
      expect(listAgents).toHaveBeenCalledWith('http://127.0.0.1:8000', 'admin-secret');
      expect(listCredentials).toHaveBeenCalledWith('http://127.0.0.1:8000', 'admin-secret');
    });

    await screen.findByText(/connected to the admin api/i);
  });

  it('restores the last issued enrollment token from session storage', async () => {
    sessionStorage.setItem('mcp_admin_base_url', 'http://127.0.0.1:8000');
    sessionStorage.setItem('mcp_admin_api_key', 'admin-secret');
    sessionStorage.setItem('mcp_admin_latest_enrollment_tokens', JSON.stringify({
      agt_ops_01: {
        enrollment_token: 'persisted_token_123',
        enrollment_token_id: 'enrollment_row_saved',
        agent_id: 'agt_ops_01',
        credential_name: 'finance',
        scopes: [],
        default_group_id: 'grp_finance',
        allowed_group_ids: ['grp_finance'],
        expires_at: '2026-03-03T12:00:00Z',
      },
    }));
    vi.mocked(listAgents).mockReset();
    vi.mocked(listAgents).mockResolvedValue([
      {
        agent_id: 'agt_ops_01',
        name: 'Ops Agent',
        description: 'Shared runtime',
        status: 'active',
      },
    ]);
    vi.mocked(listCredentials).mockReset();
    vi.mocked(listCredentials).mockResolvedValue([
      {
        credential_id: 'cred_finance_a',
        agent_id: 'agt_ops_01',
        name: 'finance',
        client_id: 'uo_client_finance_a',
        scopes: [],
        default_group_id: 'grp_finance',
        allowed_group_ids: ['grp_finance'],
        status: 'active',
      },
    ]);

    render(<AgentAdminPanel />);

    await waitFor(() => {
      expect(listAgents).toHaveBeenCalledWith('http://127.0.0.1:8000', 'admin-secret');
    });
    await userEvent.setup().click(await screen.findByRole('button', { name: /open agent ops agent/i }));
    await screen.findByRole('dialog', { name: /agent context for ops agent/i });
    await waitFor(() => {
      expect(screen.getAllByText(/persisted_token_123/i).length).toBeGreaterThan(0);
    });
  });

  it('shows the persisted token for the selected agent instead of reusing one global token', async () => {
    const user = userEvent.setup();
    sessionStorage.setItem('mcp_admin_base_url', 'http://127.0.0.1:8000');
    sessionStorage.setItem('mcp_admin_api_key', 'admin-secret');
    sessionStorage.setItem('mcp_admin_latest_enrollment_tokens', JSON.stringify({
      agt_ops_01: {
        enrollment_token: 'token_for_ops',
        enrollment_token_id: 'enrollment_ops',
        agent_id: 'agt_ops_01',
        credential_name: 'finance',
        scopes: [],
        default_group_id: 'grp_finance',
        allowed_group_ids: ['grp_finance'],
        expires_at: '2026-03-03T12:00:00Z',
      },
      agt_support_01: {
        enrollment_token: 'token_for_support',
        enrollment_token_id: 'enrollment_support',
        agent_id: 'agt_support_01',
        credential_name: 'support',
        scopes: [],
        default_group_id: 'grp_support',
        allowed_group_ids: ['grp_support'],
        expires_at: '2026-03-03T12:00:00Z',
      },
    }));
    vi.mocked(listAgents).mockReset();
    vi.mocked(listAgents).mockResolvedValue([
      {
        agent_id: 'agt_ops_01',
        name: 'Ops Agent',
        description: 'Shared runtime',
        status: 'active',
      },
      {
        agent_id: 'agt_support_01',
        name: 'Support Agent',
        description: 'Support runtime',
        status: 'active',
      },
    ]);
    vi.mocked(listCredentials).mockReset();
    vi.mocked(listCredentials).mockResolvedValue([]);

    render(<AgentAdminPanel />);

    await user.click(await screen.findByRole('button', { name: /open agent ops agent/i }));
    await screen.findByRole('dialog', { name: /agent context for ops agent/i });
    await waitFor(() => {
      expect(screen.getAllByText(/token_for_ops/i).length).toBeGreaterThan(0);
    });
    await waitFor(() => {
      expect(listAgents).toHaveBeenCalledWith('http://127.0.0.1:8000', 'admin-secret');
    });
    await user.click(screen.getByRole('button', { name: /open agent support agent/i }));
    await screen.findByRole('dialog', { name: /agent context for support agent/i });
    await waitFor(() => {
      expect(screen.getAllByText(/token_for_support/i).length).toBeGreaterThan(0);
    });
    expect(screen.queryByRole('dialog', { name: /agent context for ops agent/i })).toBeNull();
  });

  it('does not show stale persisted-only agents after backend restart and prunes their token cache', async () => {
    sessionStorage.setItem('mcp_admin_base_url', 'http://127.0.0.1:8000');
    sessionStorage.setItem('mcp_admin_api_key', 'admin-secret');
    sessionStorage.setItem('mcp_admin_latest_enrollment_tokens', JSON.stringify({
      agt_stale_01: {
        enrollment_token: 'stale_token',
        enrollment_token_id: 'enrollment_stale',
        agent_id: 'agt_stale_01',
        credential_name: 'finance',
        scopes: [],
        default_group_id: 'grp_finance',
        allowed_group_ids: ['grp_finance'],
        expires_at: '2026-03-03T12:00:00Z',
      },
      agt_ops_01: {
        enrollment_token: 'token_for_ops',
        enrollment_token_id: 'enrollment_ops',
        agent_id: 'agt_ops_01',
        credential_name: 'finance',
        scopes: [],
        default_group_id: 'grp_finance',
        allowed_group_ids: ['grp_finance'],
        expires_at: '2026-03-03T12:00:00Z',
      },
    }));
    vi.mocked(listAgents).mockReset();
    vi.mocked(listAgents).mockResolvedValue([
      {
        agent_id: 'agt_ops_01',
        name: 'Ops Agent',
        description: 'Shared runtime',
        status: 'active',
      },
    ]);
    vi.mocked(listCredentials).mockReset();
    vi.mocked(listCredentials).mockResolvedValue([]);

    render(<AgentAdminPanel />);

    await screen.findByRole('button', { name: /open agent ops agent/i });

    expect(screen.queryByText(/agt_stale_01/i)).toBeNull();
    expect(screen.queryByText(/persisted enrollment token available/i)).toBeNull();
    expect(JSON.parse(sessionStorage.getItem('mcp_admin_latest_enrollment_tokens') || '{}')).toEqual({
      agt_ops_01: {
        enrollment_token: 'token_for_ops',
        enrollment_token_id: 'enrollment_ops',
        agent_id: 'agt_ops_01',
        credential_name: 'finance',
        scopes: [],
        default_group_id: 'grp_finance',
        allowed_group_ids: ['grp_finance'],
        expires_at: '2026-03-03T12:00:00Z',
      },
    });
  });

  it('keeps agent context hidden until an agent card is opened and then shows it in an overlay', async () => {
    const user = userEvent.setup();
    sessionStorage.setItem('mcp_admin_base_url', 'http://127.0.0.1:8000');
    sessionStorage.setItem('mcp_admin_api_key', 'admin-secret');
    vi.mocked(listAgents).mockReset();
    vi.mocked(listAgents).mockResolvedValue([
      {
        agent_id: 'agt_ops_01',
        name: 'Ops Agent',
        description: 'Shared runtime',
        status: 'active',
      },
    ]);
    vi.mocked(listCredentials).mockReset();
    vi.mocked(listCredentials).mockResolvedValue([]);

    render(<AgentAdminPanel />);

    await waitFor(() => {
      expect(listAgents).toHaveBeenCalledWith('http://127.0.0.1:8000', 'admin-secret');
    });

    expect(screen.queryByLabelText(/credential name/i)).toBeNull();
    expect(screen.queryByRole('dialog', { name: /agent context/i })).toBeNull();
    await user.click(await screen.findByRole('button', { name: /open agent ops agent/i }));
    expect(await screen.findByRole('dialog', { name: /agent context for ops agent/i })).toBeTruthy();
    expect(screen.getByLabelText(/credential name/i)).toBeTruthy();
    await user.click(screen.getByRole('button', { name: /close agent context/i }));
    expect(screen.queryByRole('dialog', { name: /agent context/i })).toBeNull();
  });

  it('shows status, credential count, and latest token metadata on agent cards', async () => {
    sessionStorage.setItem('mcp_admin_base_url', 'http://127.0.0.1:8000');
    sessionStorage.setItem('mcp_admin_api_key', 'admin-secret');
    sessionStorage.setItem('mcp_admin_latest_enrollment_tokens', JSON.stringify({
      agt_ops_01: {
        enrollment_token: 'token_for_ops',
        enrollment_token_id: 'enrollment_ops',
        agent_id: 'agt_ops_01',
        credential_name: 'finance',
        scopes: [],
        default_group_id: 'grp_finance',
        allowed_group_ids: ['grp_finance'],
        expires_at: '2026-03-03T12:00:00Z',
      },
    }));
    vi.mocked(listAgents).mockReset();
    vi.mocked(listAgents).mockResolvedValue([
      {
        agent_id: 'agt_ops_01',
        name: 'Ops Agent',
        description: 'Shared runtime',
        status: 'active',
      },
    ]);
    vi.mocked(listCredentials).mockReset();
    vi.mocked(listCredentials).mockResolvedValue([
      {
        credential_id: 'cred_finance_a',
        agent_id: 'agt_ops_01',
        name: 'finance',
        client_id: 'uo_client_finance_a',
        scopes: [],
        default_group_id: 'grp_finance',
        allowed_group_ids: ['grp_finance'],
        status: 'active',
      },
      {
        credential_id: 'cred_support_a',
        agent_id: 'agt_ops_01',
        name: 'support',
        client_id: 'uo_client_support_a',
        scopes: [],
        default_group_id: 'grp_support',
        allowed_group_ids: ['grp_support'],
        status: 'active',
      },
    ]);

    render(<AgentAdminPanel />);

    await waitFor(() => {
      expect(listAgents).toHaveBeenCalledWith('http://127.0.0.1:8000', 'admin-secret');
    });

    expect(screen.getByText(/2 credentials/i)).toBeTruthy();
    expect(screen.getByText(/latest token: finance/i)).toBeTruthy();
    expect(screen.getByText(/^active$/i)).toBeTruthy();
  });

  it('lets operators add and remove allowed groups without native multi-select modifiers', async () => {
    const user = userEvent.setup();
    sessionStorage.setItem('mcp_admin_base_url', 'http://127.0.0.1:8000');
    sessionStorage.setItem('mcp_admin_api_key', 'admin-secret');
    vi.mocked(listAgents).mockReset();
    vi.mocked(listAgents).mockResolvedValue([
      {
        agent_id: 'agt_ops_01',
        name: 'Ops Agent',
        description: 'Shared runtime',
        status: 'active',
      },
    ]);
    vi.mocked(listCredentials).mockReset();
    vi.mocked(listCredentials).mockResolvedValue([]);

    render(<AgentAdminPanel />);

    await user.click(await screen.findByRole('button', { name: /open agent ops agent/i }));
    await screen.findByRole('dialog', { name: /agent context for ops agent/i });

    const financeCheckbox = screen.getByRole('checkbox', { name: /finance \(grp_finance\)/i });
    const supportCheckbox = screen.getByRole('checkbox', { name: /support \(grp_support\)/i });

    expect(financeCheckbox).toHaveProperty('checked', false);
    expect(supportCheckbox).toHaveProperty('checked', false);

    await user.click(financeCheckbox);
    expect(financeCheckbox).toHaveProperty('checked', true);
    expect(supportCheckbox).toHaveProperty('checked', false);

    await user.click(supportCheckbox);
    expect(financeCheckbox).toHaveProperty('checked', true);
    expect(supportCheckbox).toHaveProperty('checked', true);

    await user.click(financeCheckbox);
    expect(financeCheckbox).toHaveProperty('checked', false);
    expect(supportCheckbox).toHaveProperty('checked', true);
  });

  it('shows the default group as implicitly allowed and keeps it across reopening the agent context', async () => {
    const user = userEvent.setup();
    sessionStorage.setItem('mcp_admin_base_url', 'http://127.0.0.1:8000');
    sessionStorage.setItem('mcp_admin_api_key', 'admin-secret');
    vi.mocked(listAgents).mockReset();
    vi.mocked(listAgents).mockResolvedValue([
      {
        agent_id: 'agt_ops_01',
        name: 'Ops Agent',
        description: 'Shared runtime',
        status: 'active',
      },
    ]);
    vi.mocked(listCredentials).mockReset();
    vi.mocked(listCredentials).mockResolvedValue([]);

    render(<AgentAdminPanel />);

    await user.click(await screen.findByRole('button', { name: /open agent ops agent/i }));
    await screen.findByRole('dialog', { name: /agent context for ops agent/i });

    await user.selectOptions(screen.getByLabelText(/default group/i), 'grp_finance');

    const financeCheckbox = screen.getByRole('checkbox', { name: /finance \(grp_finance\)/i });
    const supportCheckbox = screen.getByRole('checkbox', { name: /support \(grp_support\)/i });

    expect(financeCheckbox).toHaveProperty('checked', true);
    expect(financeCheckbox).toHaveProperty('disabled', true);
    expect(supportCheckbox).toHaveProperty('checked', false);
    expect(supportCheckbox).toHaveProperty('disabled', false);

    await user.click(screen.getByRole('button', { name: /close agent context/i }));
    await user.click(await screen.findByRole('button', { name: /open agent ops agent/i }));
    await screen.findByRole('dialog', { name: /agent context for ops agent/i });

    expect(screen.getByLabelText(/default group/i)).toHaveProperty('value', 'grp_finance');
    expect(screen.getByRole('checkbox', { name: /finance \(grp_finance\)/i })).toHaveProperty('checked', true);
    expect(screen.getByRole('checkbox', { name: /finance \(grp_finance\)/i })).toHaveProperty('disabled', true);
  });

  it('keeps the enrollment form editable after selecting a default group', async () => {
    const user = userEvent.setup();
    sessionStorage.setItem('mcp_admin_base_url', 'http://127.0.0.1:8000');
    sessionStorage.setItem('mcp_admin_api_key', 'admin-secret');
    vi.mocked(listAgents).mockReset();
    vi.mocked(listAgents).mockResolvedValue([
      {
        agent_id: 'agt_ops_01',
        name: 'Ops Agent',
        description: 'Shared runtime',
        status: 'active',
      },
    ]);
    vi.mocked(listCredentials).mockReset();
    vi.mocked(listCredentials).mockResolvedValue([]);

    render(<AgentAdminPanel />);

    await user.click(await screen.findByRole('button', { name: /open agent ops agent/i }));
    await screen.findByRole('dialog', { name: /agent context for ops agent/i });

    await user.selectOptions(screen.getByLabelText(/default group/i), 'grp_finance');
    await user.type(screen.getByLabelText(/credential name/i), 'ops-finance');

    expect(screen.getByLabelText(/credential name/i)).toHaveProperty('value', 'ops-finance');
    expect(screen.getByLabelText(/default group/i)).toHaveProperty('value', 'grp_finance');
  });
});
