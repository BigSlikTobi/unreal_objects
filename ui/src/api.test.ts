import { beforeEach, describe, expect, it, vi } from 'vitest';

import { fetchGroups, getGroup } from './api';

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
});
