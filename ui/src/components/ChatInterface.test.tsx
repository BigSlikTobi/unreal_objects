import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { ChatInterface } from './ChatInterface';
import { createRule, getGroup, translateRule, updateDatapointDefinitions, updateRule } from '../api';
import type { RuleGroup } from '../types';

vi.mock('../api', () => ({
  createRule: vi.fn(),
  getGroup: vi.fn(),
  translateRule: vi.fn(),
  updateDatapointDefinitions: vi.fn(),
  updateRule: vi.fn(),
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

describe('ChatInterface rule management', () => {
  beforeEach(() => {
    vi.mocked(getGroup).mockResolvedValue(baseGroup);
    vi.mocked(createRule).mockResolvedValue(existingRule);
    vi.mocked(updateRule).mockResolvedValue(existingRule);
    vi.mocked(updateDatapointDefinitions).mockResolvedValue(baseGroup);
    vi.mocked(translateRule).mockResolvedValue({
      datapoints: ['transaction_amount', 'currency'],
      edge_cases: ['IF currency != EUR THEN REJECT'],
      edge_cases_json: [{ if: [{ '!=': [{ var: 'currency' }, 'EUR'] }, 'REJECT', null] }],
      rule_logic: 'IF transaction_amount > 700 THEN ASK_FOR_APPROVAL ELSE APPROVE',
      rule_logic_json: { if: [{ '>': [{ var: 'transaction_amount' }, 700] }, 'ASK_FOR_APPROVAL', 'APPROVE'] },
    });
  });

  it('loads an existing rule into the builder for editing', async () => {
    render(
      <ChatInterface
        groupId="group_123"
        llmConfig={{ provider: 'openai', model: 'gpt-5.2', api_key: 'test-key' }}
        selectedRule={existingRule}
        onRuleCreated={vi.fn()}
        onStartTest={vi.fn()}
      />
    );

    await screen.findByText(/editing stored rule/i);
    expect((screen.getByPlaceholderText('Rule name') as HTMLInputElement).value).toBe('High Value Review');
    expect((screen.getByPlaceholderText('Feature (e.g. Fraud Check)') as HTMLInputElement).value).toBe('Fraud');
    expect((screen.getByPlaceholderText('e.g. amount > 500') as HTMLInputElement).value).toBe('transaction_amount > 500');
  });

  it('updates the existing rule instead of creating a new one when saving edits', async () => {
    const user = userEvent.setup();

    render(
      <ChatInterface
        groupId="group_123"
        llmConfig={{ provider: 'openai', model: 'gpt-5.2', api_key: 'test-key' }}
        selectedRule={existingRule}
        onRuleCreated={vi.fn()}
        onStartTest={vi.fn()}
      />
    );

    const conditionInput = screen.getByPlaceholderText('e.g. amount > 500');
    await user.clear(conditionInput);
    await user.type(conditionInput, 'transaction_amount > 700');
    await user.click(screen.getByRole('button', { name: /translate with ai/i }));
    await screen.findByText(/proposed logic/i);
    await user.click(screen.getByRole('button', { name: /accept & save/i }));

    await waitFor(() => {
      expect(updateRule).toHaveBeenCalledWith('group_123', 'rule_1', expect.objectContaining({
        active: true,
        name: 'High Value Review',
      }));
    });
    expect(createRule).not.toHaveBeenCalled();
  });
});
