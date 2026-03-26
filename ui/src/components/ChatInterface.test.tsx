import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { useState } from 'react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { ChatInterface, replaceVariableToken, swapVariableInResult } from './ChatInterface';
import { createRule, fetchSchemas, getGroup, translateRule, updateDatapointDefinitions, updateRule } from '../api';
import type { Rule, RuleGroup } from '../types';

vi.mock('../api', () => ({
  createRule: vi.fn(),
  fetchSchemas: vi.fn(),
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
    vi.mocked(fetchSchemas).mockResolvedValue([]);
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

  it('keeps the builder attached to the saved rule after accepting an edit', async () => {
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

    await screen.findByText("✅ Rule 'High Value Review' updated successfully! You are still editing it.");
    await screen.findByText(/editing stored rule/i);
    expect((screen.getByPlaceholderText('Rule name') as HTMLInputElement).value).toBe('High Value Review');
    expect((screen.getByPlaceholderText('Feature (e.g. Fraud Check)') as HTMLInputElement).value).toBe('Fraud');
    expect((screen.getByPlaceholderText('e.g. amount > 500') as HTMLInputElement).value).toBe('transaction_amount > 700');
  });

  it('leaves edit mode when stop editing is clicked', async () => {
    const user = userEvent.setup();

    const Wrapper = () => {
      const [selectedRule, setSelectedRule] = useState<Rule | null>(existingRule);
      return (
        <ChatInterface
          groupId="group_123"
          llmConfig={{ provider: 'openai', model: 'gpt-5.2', api_key: 'test-key' }}
          selectedRule={selectedRule}
          onRuleCreated={vi.fn()}
          onStartTest={vi.fn()}
          onStopEditing={() => setSelectedRule(null)}
        />
      );
    };

    render(<Wrapper />);

    await screen.findByText(/editing stored rule/i);
    await user.click(screen.getByRole('button', { name: /stop editing/i }));

    await waitFor(() => {
      expect(screen.queryByText(/editing stored rule/i)).toBeNull();
    });
    expect((screen.getByPlaceholderText('Rule name') as HTMLInputElement).value).toBe('');
    expect((screen.getByPlaceholderText('Feature (e.g. Fraud Check)') as HTMLInputElement).value).toBe('');
    expect((screen.getByPlaceholderText('e.g. amount > 500') as HTMLInputElement).value).toBe('');
  });

  it('renders quoted literals in the proposal preview without duplicating the inner text', async () => {
    const user = userEvent.setup();

    vi.mocked(translateRule).mockResolvedValueOnce({
      datapoints: ['transaction_amount', 'currency'],
      edge_cases: ["IF currency != 'EUR' THEN REJECT"],
      edge_cases_json: [{ if: [{ '!=': [{ var: 'currency' }, 'EUR'] }, 'REJECT', null] }],
      rule_logic: 'IF transaction_amount > 700 THEN ASK_FOR_APPROVAL ELSE APPROVE',
      rule_logic_json: { if: [{ '>': [{ var: 'transaction_amount' }, 700] }, 'ASK_FOR_APPROVAL', 'APPROVE'] },
    });

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
    expect(screen.getByText("'EUR'")).toBeTruthy();
    expect(screen.queryByText("'EUR'EUR")).toBeNull();
  });
});

describe('ChatInterface utility functions', () => {
  describe('replaceVariableToken', () => {
    it('replaces all occurrences of a variable', () => {
      const result = replaceVariableToken('amount > 100 AND amount < 500', 'amount', 'price');
      expect(result).toBe('price > 100 AND price < 500');
    });

    it('does not replace substrings inside other variable names', () => {
      const result = replaceVariableToken('transaction_amount > 100', 'amount', 'price');
      expect(result).toBe('transaction_amount > 100');
    });

    it('replaces standalone variable but leaves compound variables unchanged', () => {
      const result = replaceVariableToken(
        'amount > 100 AND transaction_amount < 500',
        'amount',
        'price'
      );
      expect(result).toBe('price > 100 AND transaction_amount < 500');
    });
  });

  describe('swapVariableInResult', () => {
    it('replaces variable in all parts of translation result', () => {
      const input = {
        datapoints: ['account_age_days', 'currency'],
        rule_logic: 'IF account_age_days > 10 THEN REJECT',
        rule_logic_json: { if: [{ '>': [{ var: 'account_age_days' }, 10] }, 'REJECT', null] },
        edge_cases: ['IF account_age_days < 0 THEN REJECT'],
        edge_cases_json: [{ if: [{ '<': [{ var: 'account_age_days' }, 0] }, 'REJECT', null] }],
      };

      const result = swapVariableInResult(input, 'account_age_days', 'delivery_time_days');
      const logic = result.rule_logic_json as { if: Array<Record<string, Array<unknown>>> };
      const edgeCase = result.edge_cases_json[0] as { if: Array<Record<string, Array<unknown>>> };

      expect(result.datapoints).toEqual(['delivery_time_days', 'currency']);
      expect(result.rule_logic).toBe('IF delivery_time_days > 10 THEN REJECT');
      expect(logic.if[0]['>']).toEqual([{ var: 'delivery_time_days' }, 10]);
      expect(result.edge_cases[0]).toBe('IF delivery_time_days < 0 THEN REJECT');
      expect(edgeCase.if[0]['<']).toEqual([{ var: 'delivery_time_days' }, 0]);
    });

    it('replaces multiple occurrences in rule_logic', () => {
      const input = {
        datapoints: ['amount'],
        rule_logic: 'IF amount > 100 AND amount < 500 THEN ASK_FOR_APPROVAL',
        rule_logic_json: {
          if: [
            { and: [{ '>': [{ var: 'amount' }, 100] }, { '<': [{ var: 'amount' }, 500] }] },
            'ASK_FOR_APPROVAL',
            null,
          ],
        },
        edge_cases: [],
        edge_cases_json: [],
      };

      const result = swapVariableInResult(input, 'amount', 'price');

      expect(result.rule_logic).toBe('IF price > 100 AND price < 500 THEN ASK_FOR_APPROVAL');
    });

    it('does not replace substrings in compound variable names', () => {
      const input = {
        datapoints: ['amount', 'transaction_amount'],
        rule_logic: 'IF amount > 100 AND transaction_amount < 500 THEN ASK_FOR_APPROVAL',
        rule_logic_json: {
          if: [
            { and: [{ '>': [{ var: 'amount' }, 100] }, { '<': [{ var: 'transaction_amount' }, 500] }] },
            'ASK_FOR_APPROVAL',
            null,
          ],
        },
        edge_cases: ['IF transaction_amount < 0 OR amount > 1000 THEN REJECT'],
        edge_cases_json: [
          {
            if: [
              { or: [{ '<': [{ var: 'transaction_amount' }, 0] }, { '>': [{ var: 'amount' }, 1000] }] },
              'REJECT',
              null,
            ],
          },
        ],
      };

      const result = swapVariableInResult(input, 'amount', 'price');

      expect(result.datapoints).toEqual(['price', 'transaction_amount']);
      expect(result.rule_logic).toBe('IF price > 100 AND transaction_amount < 500 THEN ASK_FOR_APPROVAL');
      expect(result.edge_cases[0]).toBe('IF transaction_amount < 0 OR price > 1000 THEN REJECT');
    });
  });
});
