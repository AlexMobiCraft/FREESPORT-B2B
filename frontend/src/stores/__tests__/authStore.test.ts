/**
 * Auth Store Tests
 */
import { useAuthStore } from '../authStore';

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
