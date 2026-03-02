import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import App from './App';
import {
  checkLLMConnection,
  createGroup,
  createRule,
  executeTest,
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
    vi.mocked(executeTest).mockResolvedValue({
      outcome: 'APPROVE',
      request_id: 'req_123',
    });
  });

  it('loads a selected rule from the rule card into the builder', async () => {
    const user = userEvent.setup();

    render(<App />);

    await screen.findByText('High Value Review');
    await user.click(screen.getByRole('button', { name: /open rule/i }));

    await waitFor(() => {
      expect((screen.getByPlaceholderText('Rule name') as HTMLInputElement).value).toBe('High Value Review');
      expect((screen.getByPlaceholderText('Feature (e.g. Fraud Check)') as HTMLInputElement).value).toBe('Fraud');
      expect((screen.getByPlaceholderText('e.g. amount > 500') as HTMLInputElement).value).toBe('transaction_amount > 500');
    });
  });

  it('shows the rule library in the center by default and hides the builder until a card is selected', async () => {
    render(<App />);

    await screen.findByText('High Value Review');
    expect(screen.getByRole('heading', { name: /rule library/i })).toBeTruthy();
    expect(screen.getByRole('button', { name: /create new rule/i })).toBeTruthy();
    expect(screen.queryByPlaceholderText('Rule name')).toBeNull();
    expect(screen.queryByRole('button', { name: /translate with ai/i })).toBeNull();
  });

  it('opens an editing workspace with the form first and chat context underneath', async () => {
    const user = userEvent.setup();

    render(<App />);

    await screen.findByText('High Value Review');
    await user.click(screen.getByRole('button', { name: /open rule/i }));

    const builderHeading = await screen.findByRole('heading', { name: /rule builder/i });
    const chatHeading = await screen.findByRole('heading', { name: /chat context/i });

    expect(
      builderHeading.compareDocumentPosition(chatHeading) & Node.DOCUMENT_POSITION_FOLLOWING
    ).toBeTruthy();
    expect(screen.getByPlaceholderText('Rule name')).toBeTruthy();
    expect(screen.getByText(/editing 'high value review'/i)).toBeTruthy();
  });

  it('opens a fresh builder workspace from the create new rule card', async () => {
    const user = userEvent.setup();

    render(<App />);

    await screen.findByText('High Value Review');
    await user.click(screen.getByRole('button', { name: /create new rule/i }));

    expect(await screen.findByRole('heading', { name: /rule builder/i })).toBeTruthy();
    expect(screen.getByRole('heading', { name: /chat context/i })).toBeTruthy();
    expect((screen.getByPlaceholderText('Rule name') as HTMLInputElement).value).toBe('');
    expect(screen.queryByText(/editing stored rule/i)).toBeNull();
  });

  it('renders the mobile groups toggle while keeping rules in the main workspace', async () => {
    render(<App />);

    await screen.findByText('High Value Review');
    expect(screen.getByRole('button', { name: /open groups/i })).toBeTruthy();
    expect(screen.queryByRole('button', { name: /open rules/i })).toBeNull();
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

  it('prefills the OpenAI settings modal with the current default model when none is stored', async () => {
    const user = userEvent.setup();

    sessionStorage.clear();
    sessionStorage.setItem('llm_provider', 'openai');
    sessionStorage.setItem('llm_api_key', 'test-key');

    render(<App />);

    await screen.findByText('High Value Review');
    await user.click(screen.getByRole('button', { name: /configure llm/i }));

    expect(await screen.findByDisplayValue('gpt-5.2-2025-12-11')).toBeTruthy();
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

  it('clears a prior system notice when switching to a different group', async () => {
    const user = userEvent.setup();
    const secondGroup: RuleGroup = {
      id: 'group_456',
      name: 'Lending',
      description: 'Loan controls',
      rules: [],
      datapoint_definitions: [],
    };

    vi.mocked(fetchGroups).mockResolvedValue([baseGroup, secondGroup]);
    vi.mocked(getGroup).mockImplementation(async (groupId: string) => (
      groupId === secondGroup.id ? secondGroup : baseGroup
    ));
    vi.mocked(updateRule).mockResolvedValue({
      ...existingRule,
      active: false,
    });

    render(<App />);

    await screen.findByText('High Value Review');
    await user.click(screen.getByRole('button', { name: /deactivate/i }));
    await screen.findByText("Rule 'High Value Review' deactivated. It remains documented but will be skipped during evaluation.");

    await user.click(screen.getByRole('button', { name: /lending/i }));

    await screen.findByText('No saved rules in this group yet.');
    expect(
      screen.queryByText("Rule 'High Value Review' deactivated. It remains documented but will be skipped during evaluation.")
    ).toBeNull();
  });

  it('keeps the saved rule in the builder when save and test opens the test console', async () => {
    const user = userEvent.setup();

    render(<App />);

    await screen.findByText('High Value Review');
    await user.click(screen.getByRole('button', { name: /open rule/i }));

    const conditionInput = await screen.findByPlaceholderText('e.g. amount > 500');
    await user.clear(conditionInput);
    await user.type(conditionInput, 'transaction_amount > 700');
    await user.click(screen.getByRole('button', { name: /translate with ai/i }));
    await screen.findByText(/proposed logic/i);
    await user.click(screen.getByRole('button', { name: /save & test/i }));

    await screen.findByText("✅ Rule 'High Value Review' updated. Opening test console while you stay in edit mode.");
    await screen.findByText(/test rule setup/i);
    await screen.findByText(/editing stored rule/i);
    expect((screen.getByPlaceholderText('Rule name') as HTMLInputElement).value).toBe('High Value Review');
    expect((screen.getByPlaceholderText('e.g. amount > 500') as HTMLInputElement).value).toBe('transaction_amount > 700');
  });
});
