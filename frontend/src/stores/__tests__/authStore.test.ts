/**
 * Auth Store Tests
 */
import { renderHook } from '@testing-library/react';
import type { User } from '@/types/api';
import { authSelectors, useAuthStore } from '../authStore';

describe('authStore', () => {
  beforeEach(async () => {
    // Reset store перед каждым тестом
    await useAuthStore.getState().logout();
    localStorage.clear();
  });

  test('setTokens saves tokens correctly', () => {
    const store = useAuthStore.getState();

    store.setTokens('test-access', 'test-refresh');

    const state = useAuthStore.getState();
    expect(state.accessToken).toBe('test-access');
    expect(state.isAuthenticated).toBe(true);
    expect(localStorage.getItem('refreshToken')).toBe('test-refresh');
  });

  test('setUser saves user data', () => {
    const store = useAuthStore.getState();
    const user = {
      id: 1,
      email: 'test@test.com',
      first_name: 'Test',
      last_name: 'User',
      phone: '+79001234567',
      role: 'retail' as const,
    };

    store.setUser(user);

    const state = useAuthStore.getState();
    expect(state.user).toEqual(user);
  });

  test('logout clears all data', async () => {
    const store = useAuthStore.getState();

    // Setup: установить токены и пользователя
    store.setTokens('test-access', 'test-refresh');
    store.setUser({
      id: 1,
      email: 'test@test.com',
      first_name: 'Test',
      last_name: 'User',
      phone: '+79001234567',
      role: 'retail',
    });

    // Act: выполнить logout
    await store.logout();

    // Assert: проверить что все очищено
    const state = useAuthStore.getState();
    expect(state.accessToken).toBeNull();
    expect(state.user).toBeNull();
    expect(state.isAuthenticated).toBe(false);
    expect(localStorage.getItem('refreshToken')).toBeNull();
  });

  test('getRefreshToken returns token from localStorage', () => {
    const store = useAuthStore.getState();
    localStorage.setItem('refreshToken', 'test-refresh');

    expect(store.getRefreshToken()).toBe('test-refresh');
  });
});

describe('authSelectors.useIsB2BUser', () => {
  const makeUser = (role: User['role'], is_verified: boolean): User => ({
    id: 1,
    email: 'test@test.com',
    first_name: 'Test',
    last_name: 'User',
    phone: '+79001234567',
    role,
    is_verified,
  });

  beforeEach(async () => {
    await useAuthStore.getState().logout();
    localStorage.clear();
  });

  test.each(['vip', 'special_price', 'wholesale_level1', 'trainer'] as const)(
    'верифицированная роль %s — B2B',
    role => {
      useAuthStore.getState().setUser(makeUser(role, true));

      const { result } = renderHook(() => authSelectors.useIsB2BUser());

      expect(result.current).toBe(true);
    }
  );

  test.each(['vip', 'special_price'] as const)(
    'неверифицированная роль %s считается розничной',
    role => {
      useAuthStore.getState().setUser(makeUser(role, false));

      const { result } = renderHook(() => authSelectors.useIsB2BUser());

      expect(result.current).toBe(false);
    }
  );

  test('розница не B2B даже после верификации', () => {
    useAuthStore.getState().setUser(makeUser('retail', true));

    const { result } = renderHook(() => authSelectors.useIsB2BUser());

    expect(result.current).toBeFalsy();
  });
});
