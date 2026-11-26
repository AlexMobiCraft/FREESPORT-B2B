/**
 * Тесты обёртки devtoolsInDev (стори 41.21, AC1–AC2).
 *
 * Значение выбирается при загрузке модуля, поэтому каждый случай
 * подменяет NODE_ENV и импортирует модуль заново.
 */
import { afterEach, describe, expect, it, vi } from 'vitest';

describe('devtoolsInDev', () => {
  afterEach(() => {
    vi.unstubAllEnvs();
    vi.resetModules();
  });

  it('в production возвращает инициализатор без изменений', async () => {
    vi.stubEnv('NODE_ENV', 'production');
    vi.resetModules();
    const { devtoolsInDev } = await import('../devtoolsInDev');
    const { devtools } = await import('zustand/middleware');

    const initializer = vi.fn();

    expect(devtoolsInDev).not.toBe(devtools);
    expect(devtoolsInDev(initializer, { name: 'TestStore' })).toBe(initializer);
  });

  it('вне production — это devtools из zustand/middleware', async () => {
    vi.stubEnv('NODE_ENV', 'development');
    vi.resetModules();
    const { devtoolsInDev } = await import('../devtoolsInDev');
    const { devtools } = await import('zustand/middleware');

    expect(devtoolsInDev).toBe(devtools);
  });
});
