import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { TestConsole } from './TestConsole';
import { executeTest } from '../api';

vi.mock('../api', () => ({
  executeTest: vi.fn(),
}));

describe('TestConsole', () => {
  beforeEach(() => {
    vi.mocked(executeTest).mockResolvedValue({
      outcome: 'APPROVE',
      request_id: 'req_123',
      matched_rules: [],
      matched_details: [],
    });
  });

  it('runs evaluation against only the selected rule', async () => {
    const user = userEvent.setup();

    render(
      <TestConsole
        groupId="group_123"
        ruleToTest={{
          id: 'rule_456',
          name: 'Delivery Rule',
          feature: 'Delivery',
          active: true,
          datapoints: ['delivery_time'],
          edge_cases: [],
          edge_cases_json: [],
          rule_logic: 'IF delivery_time > 10 THEN REJECT',
          rule_logic_json: { if: [{ '>': [{ var: 'delivery_time' }, 10] }, 'REJECT', null] },
        }}
        datapointDefinitions={[
          { name: 'delivery_time', type: 'number', values: [] },
        ]}
        onClose={vi.fn()}
      />
    );

    await user.type(screen.getByPlaceholderText('Value...'), '12');
    await user.click(screen.getByRole('button', { name: /run test/i }));

    expect(executeTest).toHaveBeenCalledWith('group_123', '', { delivery_time: 12 }, 'rule_456');
  });
});
