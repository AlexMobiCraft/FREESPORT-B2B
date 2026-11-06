/**
 * Unit тесты getUserRole (SSR): роль из профиля backend.
 *
 * Неизвестная роль превращается в `retail`, поэтому каждая новая роль обязана быть в списке
 * допустимых: иначе VIP-клиент увидит розницу при серверном рендеринге.
 */

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const cookieGet = vi.fn();

vi.mock('next/headers', () => ({
  cookies: vi.fn(async () => ({ get: cookieGet })),
}));

import { getUserRole } from '../server-auth';

function mockProfile(body: unknown, ok = true) {
  vi.stubGlobal(
    'fetch',
    vi.fn(async () => ({ ok, json: async () => body }))
  );
}

describe('getUserRole', () => {
  beforeEach(() => {
    cookieGet.mockReset();
    cookieGet.mockImplementation((name: string) =>
      name === 'sessionid' ? { value: 'session-1' } : undefined
    );
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it.each([
    'retail',
    'wholesale_level1',
    'wholesale_level4',
    'trainer',
    'federation_rep',
    'vip',
    'special_price',
    'admin',
    'unregistered',
  ])('отдаёт роль %s из профиля', async role => {
    mockProfile({ role });

    expect(await getUserRole()).toBe(role);
  });

  it('неизвестная роль превращается в retail', async () => {
    mockProfile({ role: 'no_such_role' });

    expect(await getUserRole()).toBe('retail');
  });

  it('без сессии — guest, без запроса к API', async () => {
    cookieGet.mockReturnValue(undefined);
    mockProfile({ role: 'vip' });

    expect(await getUserRole()).toBe('guest');
    expect(fetch).not.toHaveBeenCalled();
  });

  it('ошибка профиля — guest', async () => {
    mockProfile({ role: 'vip' }, false);

    expect(await getUserRole()).toBe('guest');
  });

  it('сбой сети — guest', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => {
        throw new Error('network');
      })
    );

    expect(await getUserRole()).toBe('guest');
  });
});
