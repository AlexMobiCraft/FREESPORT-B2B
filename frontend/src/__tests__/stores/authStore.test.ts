/**
 * Unit Tests для authStore - Story 31.2
 * Тестирование async logout() с вызовом backend API
 */

import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { http, HttpResponse } from 'msw';
import { server } from '@/__mocks__/api/server';
import { useAuthStore } from '@/stores/authStore';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8001/api/v1';

// Mock localStorage
const localStorageMock = (() => {
  let store: Record<string, string> = {};
  return {
    getItem: (key: string) => store[key] || null,
    setItem: (key: string, value: string) => {
      store[key] = value;
    },
    removeItem: (key: string) => {
      delete store[key];
    },
    clear: () => {
      store = {};
    },
  };
})();

Object.defineProperty(global, 'localStorage', {
  value: localStorageMock,
});

// Mock document.cookie
let documentCookie = '';
Object.defineProperty(document, 'cookie', {
  get: () => documentCookie,
  set: (value: string) => {
    documentCookie = value;
  },
});

describe('AuthStore - logout', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorageMock.clear();
    documentCookie = '';
    // Reset store state
    useAuthStore.setState({
      accessToken: null,
      user: null,
      isAuthenticated: false,
    });
  });

  afterEach(() => {
    server.resetHandlers();
  });

  /**
   * AC 5: authStore.logout() вызывает authService.logoutFromServer() с refresh токеном
   */
  it('calls authService.logoutFromServer with refresh token from localStorage', async () => {
    const testToken = 'test-refresh-token';
    localStorageMock.setItem('refreshToken', testToken);

    let capturedBody: unknown = null;
    server.use(
      http.post(`${API_BASE_URL}/auth/logout/`, async ({ request }) => {
        capturedBody = await request.json();
        return new HttpResponse(null, { status: 204 });
      })
    );

    // Setup initial authenticated state
    useAuthStore.setState({
      accessToken: 'test-access-token',
      user: {
        id: 1,
        email: 'test@example.com',
        first_name: 'Test',
        last_name: 'User',
        phone: '',
        role: 'retail',
      },
      isAuthenticated: true,
    });

    await useAuthStore.getState().logout();

    expect(capturedBody).toEqual({ refresh: testToken });
  });

  /**
   * AC 5: После logout состояние очищается
   */
  it('clears auth state after successful logout', async () => {
    localStorageMock.setItem('refreshToken', 'test-token');

    useAuthStore.setState({
      accessToken: 'test-access-token',
      user: {
        id: 1,
        email: 'test@example.com',
        first_name: 'Test',
        last_name: 'User',
        phone: '',
        role: 'retail',
      },
      isAuthenticated: true,
    });

    await useAuthStore.getState().logout();

    const state = useAuthStore.getState();
    expect(state.isAuthenticated).toBe(false);
    expect(state.accessToken).toBeNull();
    expect(state.user).toBeNull();
    expect(localStorageMock.getItem('refreshToken')).toBeNull();
  });

  /**
   * AC 6: При ошибке API локальная очистка все равно происходит (fail-safe)
   */
  it('clears state even when API fails (fail-safe)', async () => {
    const testToken = 'test-token';
    localStorageMock.setItem('refreshToken', testToken);

    // Override handler для симуляции ошибки (400 вместо 500 чтобы избежать axios retry)
    server.use(
      http.post(`${API_BASE_URL}/auth/logout/`, () => {
        return HttpResponse.json({ error: 'Invalid token' }, { status: 400 });
      })
    );

    // Suppress console.error during this test (логируется в authService)
    const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {});

    useAuthStore.setState({
      accessToken: 'test-access-token',
      user: {
        id: 1,
        email: 'test@example.com',
        first_name: 'Test',
        last_name: 'User',
        phone: '',
        role: 'retail',
      },
      isAuthenticated: true,
    });

    // Должен выполниться без throw, даже при ошибке API
    await useAuthStore.getState().logout();

    const state = useAuthStore.getState();
    expect(state.isAuthenticated).toBe(false);
    expect(state.accessToken).toBeNull();
    expect(state.user).toBeNull();
    expect(localStorageMock.getItem('refreshToken')).toBeNull();

    // Verify error was logged
    expect(consoleSpy).toHaveBeenCalled();

    consoleSpy.mockRestore();
  });

  /**
   * AC 6: При network error локальная очистка все равно происходит
   */
  it('clears state even when network error occurs', async () => {
    localStorageMock.setItem('refreshToken', 'test-token');

    server.use(
      http.post(`${API_BASE_URL}/auth/logout/`, () => {
        return HttpResponse.error();
      })
    );

    const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {});

    useAuthStore.setState({
      accessToken: 'test-access-token',
      user: {
        id: 1,
        email: 'test@example.com',
        first_name: 'Test',
        last_name: 'User',
        phone: '',
        role: 'retail',
      },
      isAuthenticated: true,
    });

    await useAuthStore.getState().logout();

    const state = useAuthStore.getState();
    expect(state.isAuthenticated).toBe(false);
    expect(state.accessToken).toBeNull();
    expect(state.user).toBeNull();

    expect(consoleSpy).toHaveBeenCalled();
    consoleSpy.mockRestore();
  });

  /**
   * AC 6: Удаляет refreshToken cookie при logout
   */
  it('removes refreshToken cookie during logout', async () => {
    // Set cookie before logout
    document.cookie = 'refreshToken=test-cookie-token; path=/';
    localStorageMock.setItem('refreshToken', 'token');

    // Successful response
    server.use(
      http.post(`${API_BASE_URL}/auth/logout/`, () => {
        return new HttpResponse(null, { status: 204 });
      })
    );

    useAuthStore.setState({
      accessToken: 'test-access-token',
      user: {
        id: 1,
        email: 'test@example.com',
        first_name: 'Test',
        last_name: 'User',
        phone: '',
        role: 'retail',
      },
      isAuthenticated: true,
    });

    await useAuthStore.getState().logout();

    expect(document.cookie).not.toContain('refreshToken=test-cookie-token');
  });

  /**
   * Если нет refresh token, не вызывать API
   */
  it('does not call API when no refresh token exists', async () => {
    // Ensure localStorage is empty
    localStorageMock.clear();

    let apiCalled = false;
    server.use(
      http.post(`${API_BASE_URL}/auth/logout/`, () => {
        apiCalled = true;
        return new HttpResponse(null, { status: 204 });
      })
    );

    useAuthStore.setState({
      accessToken: 'test-access-token',
      user: {
        id: 1,
        email: 'test@example.com',
        first_name: 'Test',
        last_name: 'User',
        phone: '',
        role: 'retail',
      },
      isAuthenticated: true,
    });

    await useAuthStore.getState().logout();

    expect(apiCalled).toBe(false);
    expect(useAuthStore.getState().isAuthenticated).toBe(false);
  });
});
