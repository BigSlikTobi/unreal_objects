import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import App from './App';
import {
  checkLLMConnection,
  createGroup,
  createRule,
  fetchGroups,
  getGroup,
  translateRule,
  updateDatapointDefinitions,
  updateRule,
} from './api';
import type { RuleGroup } from './types';

vi.mock('./api', () => ({
  fetchGroups: vi.fn(),
  createGroup: vi.fn(),
  getGroup: vi.fn(),
  checkLLMConnection: vi.fn(),
  translateRule: vi.fn(),
  updateDatapointDefinitions: vi.fn(),
  createRule: vi.fn(),
  updateRule: vi.fn(),
  executeTest: vi.fn(),
}));

const existingRule = {
  id: 'rule_1',
  name: 'High Value Review',
  feature: 'Fraud',
  active: true,
  datapoints: ['transaction_amount', 'currency'],
  edge_cases: ['IF currency != EUR THEN REJECT'],
  edge_cases_json: [{ if: [{ '!=': [{ var: 'currency' }, 'EUR'] }, 'REJECT', null] }],
  rule_logic: 'IF transaction_amount > 500 THEN ASK_FOR_APPROVAL ELSE APPROVE',
  rule_logic_json: { if: [{ '>': [{ var: 'transaction_amount' }, 500] }, 'ASK_FOR_APPROVAL', 'APPROVE'] },
};

const baseGroup: RuleGroup = {
  id: 'group_123',
  name: 'Payments',
  description: 'Card controls',
  rules: [existingRule],
  datapoint_definitions: [
    { name: 'transaction_amount', type: 'number', values: [] },
    { name: 'currency', type: 'enum', values: ['EUR'] },
  ],
};

describe('App rule library layout', () => {
  beforeEach(() => {
    sessionStorage.clear();
    sessionStorage.setItem('llm_provider', 'openai');
    sessionStorage.setItem('llm_model', 'gpt-5.2');
    sessionStorage.setItem('llm_api_key', 'test-key');

    vi.mocked(fetchGroups).mockResolvedValue([baseGroup]);
    vi.mocked(getGroup).mockResolvedValue(baseGroup);
    vi.mocked(checkLLMConnection).mockResolvedValue({ ok: true });
    vi.mocked(createGroup).mockResolvedValue({
      id: 'group_999',
      name: 'New Group',
      description: '',
      rules: [],
      datapoint_definitions: [],
    });
    vi.mocked(translateRule).mockResolvedValue({
      datapoints: ['transaction_amount'],
      edge_cases: [],
      edge_cases_json: [],
      rule_logic: 'IF transaction_amount > 700 THEN ASK_FOR_APPROVAL',
      rule_logic_json: { if: [{ '>': [{ var: 'transaction_amount' }, 700] }, 'ASK_FOR_APPROVAL', null] },
    });
    vi.mocked(updateDatapointDefinitions).mockResolvedValue(baseGroup);
    vi.mocked(createRule).mockResolvedValue(existingRule);
    vi.mocked(updateRule).mockResolvedValue(existingRule);
  });

  it('loads a selected rule from the rule panel into the builder', async () => {
    const user = userEvent.setup();

    render(<App />);

    await screen.findByText('High Value Review');
    await user.click(screen.getByRole('button', { name: /use in builder/i }));

    await waitFor(() => {
      expect((screen.getByPlaceholderText('Rule name') as HTMLInputElement).value).toBe('High Value Review');
      expect((screen.getByPlaceholderText('Feature (e.g. Fraud Check)') as HTMLInputElement).value).toBe('Fraud');
      expect((screen.getByPlaceholderText('e.g. amount > 500') as HTMLInputElement).value).toBe('transaction_amount > 500');
    });
  });

  it('renders mobile panel toggles for groups and rules', async () => {
    render(<App />);

    await screen.findByText('High Value Review');
    expect(screen.getByRole('button', { name: /open groups/i })).toBeTruthy();
    expect(screen.getByRole('button', { name: /open rules/i })).toBeTruthy();
  });

  it('applies the dark class to the document when the theme toggle is used', async () => {
    const user = userEvent.setup();
    render(<App />);

    await screen.findByText('High Value Review');
    await user.click(screen.getByRole('button', { name: /dark mode/i }));

    expect(document.documentElement.classList.contains('dark')).toBe(true);
    await user.click(screen.getByRole('button', { name: /light mode/i }));
    expect(document.documentElement.classList.contains('dark')).toBe(false);
  });

  it('shows a clear chat message when a rule is deactivated from the rule panel', async () => {
    const user = userEvent.setup();
    vi.mocked(updateRule).mockResolvedValue({
      ...existingRule,
      active: false,
    });

    render(<App />);

    await screen.findByText('High Value Review');
    await user.click(screen.getByRole('button', { name: /deactivate/i }));

    await screen.findByText("Rule 'High Value Review' deactivated. It remains documented but will be skipped during evaluation.");
  });
});
