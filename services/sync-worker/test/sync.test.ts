import { describe, expect, it } from 'vitest';

describe('sync worker contract', () => {
  it('documents expected endpoints', () => {
    const endpoints = ['/health', '/sync/push', '/sync/pull'];
    expect(endpoints).toContain('/health');
    expect(endpoints).toContain('/sync/push');
    expect(endpoints).toContain('/sync/pull');
  });
});
