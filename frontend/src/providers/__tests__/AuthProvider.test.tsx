/**
 * AuthProvider Integration Tests
 * Story 28.4 - Защищенные маршруты и управление сессиями
 *
 * Тестирует:
 * - Успешная инициализация с валидным refresh token
 * - Logout при истекшем refresh token (401/403)
 * - Loading state во время инициализации
 * - Обработка network errors с retry logic
 */

import { describe, test, expect, vi, beforeEach, afterEach, beforeAll, afterAll } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { AuthProvider, useAuth } from '../AuthProvider';
import { useAuthStore } from '@/stores/authStore';
import { server } from '@/__mocks__/api/server';
import { http, HttpResponse } from 'msw';
import { handlers as baseHandlers } from '@/__mocks__/handlers';

// Mock localStorage
const localStorageMock = (() => {
  let store: Record<string, string> = {};

  return {
    getItem: (key: string) => store[key] || null,
    setItem: (key: string, value: string) => {
      store[key] = value.toString();
    },
    removeItem: (key: string) => {
      delete store[key];
    },
    clear: () => {
      store = {};
    },
  };
})();

Object.defineProperty(window, 'localStorage', {
  value: localStorageMock,
});

// Setup MSW server
// Story 31.2: Изменено на 'warn' т.к. logout теперь async и делает API call
beforeAll(() => server.listen({ onUnhandledRequest: 'warn' }));
afterAll(() => server.close());

describe('AuthProvider - Session Initialization', () => {
  beforeEach(async () => {
    // Clear localStorage и authStore перед каждым тестом
    localStorageMock.clear();
    server.resetHandlers();
    // Возвращаем базовые handlers (включая /users/profile/, /auth/logout/, /auth/refresh/)
    server.use(...baseHandlers);
    // Story 31.2: logout теперь async
    await useAuthStore.getState().logout();
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  test('initializes without refresh token - shows children immediately', async () => {
    // Нет refresh token в localStorage
    render(
      <AuthProvider>
        <div data-testid="app-content">App Content</div>
      </AuthProvider>
    );

    // Должен показать loading state вначале
    // Затем сразу показать children (без вызова API)
    await waitFor(() => {
      expect(screen.getByTestId('app-content')).toBeInTheDocument();
    });

    // Проверка: /auth/me/ НЕ должен был вызваться
    const { user } = useAuthStore.getState();
    expect(user).toBeNull();
  });

  test('initializes session with valid refresh token', async () => {
    // Устанавливаем valid refresh token
    localStorageMock.setItem('refreshToken', 'valid-refresh-token');

    // Mock /users/profile/ response (updated endpoint)
    server.use(
      http.get('http://localhost:8001/api/v1/users/profile/', () => {
        return HttpResponse.json({
          id: 1,
          email: 'test@example.com',
          first_name: 'Test',
          last_name: 'User',
          role: 'retail',
          is_verified: true,
        });
      })
    );

    render(
      <AuthProvider>
        <div data-testid="app-content">App Content</div>
      </AuthProvider>
    );

    // Loading state вначале
    expect(screen.queryByText('Загрузка...')).toBeInTheDocument();

    // После инициализации
    await waitFor(() => {
      expect(screen.getByTestId('app-content')).toBeInTheDocument();
    });

    // Проверка: authStore был обновлен
    const { user } = useAuthStore.getState();
    expect(user?.email).toBe('test@example.com');
    expect(user?.role).toBe('retail');
  });

  test('logs out on expired refresh token (401)', async () => {
    localStorageMock.setItem('refreshToken', 'expired-token');

    // Mock /users/profile/ с 401 ошибкой
    server.use(
      http.get('*/users/profile/', () => {
        return HttpResponse.json({ detail: 'Invalid token' }, { status: 401 });
      }),
      // ВАЖНО: api-client interceptor попытается refresh при 401, нужно обработать
      http.post('*/auth/refresh/', () => {
        return HttpResponse.json({ detail: 'Invalid refresh token' }, { status: 401 });
      })
    );

    render(
      <AuthProvider>
        <div data-testid="app-content">App Content</div>
      </AuthProvider>
    );

    await waitFor(() => {
      expect(screen.getByTestId('app-content')).toBeInTheDocument();
    });

    // Проверка: logout был вызван
    const { isAuthenticated } = useAuthStore.getState();
    expect(isAuthenticated).toBe(false);
    expect(localStorageMock.getItem('refreshToken')).toBeNull();
  });

  test('logs out on forbidden token (403)', async () => {
    localStorageMock.setItem('refreshToken', 'forbidden-token');

    // Mock /users/profile/ с 403 ошибкой
    server.use(
      http.get('*/users/profile/', () => {
        return HttpResponse.json({ detail: 'Token expired' }, { status: 403 });
      })
    );

    render(
      <AuthProvider>
        <div data-testid="app-content">App Content</div>
      </AuthProvider>
    );

    await waitFor(() => {
      expect(screen.getByTestId('app-content')).toBeInTheDocument();
    });

    // Проверка: logout был вызван
    const { isAuthenticated } = useAuthStore.getState();
    expect(isAuthenticated).toBe(false);
  });

  test('shows loading state during initialization', async () => {
    localStorageMock.setItem('refreshToken', 'valid-token');

    // Mock /users/profile/ с задержкой
    server.use(
      http.get('*/users/profile/', async () => {
        await new Promise(resolve => setTimeout(resolve, 100));
        return HttpResponse.json({
          id: 1,
          email: 'test@example.com',
          role: 'retail',
        });
      })
    );

    render(
      <AuthProvider>
        <div data-testid="app-content">App Content</div>
      </AuthProvider>
    );

    // Вначале должен быть loading state
    expect(screen.getByText('Загрузка...')).toBeInTheDocument();
    expect(screen.queryByTestId('app-content')).not.toBeInTheDocument();

    // После завершения - children
    await waitFor(() => {
      expect(screen.getByTestId('app-content')).toBeInTheDocument();
      expect(screen.queryByText('Загрузка...')).not.toBeInTheDocument();
    });
  });

  test('retries on network error and succeeds', async () => {
    localStorageMock.setItem('refreshToken', 'valid-token');

    let attempt = 0;

    // Mock /users/profile/ - первый вызов failит, второй succeeds
    server.use(
      http.get('*/users/profile/', () => {
        attempt++;
        if (attempt === 1) {
          // Первая попытка - network error
          return HttpResponse.error();
        }
        // Вторая попытка - success
        return HttpResponse.json({
          id: 1,
          email: 'test@example.com',
          role: 'retail',
        });
      })
    );

    render(
      <AuthProvider>
        <div data-testid="app-content">App Content</div>
      </AuthProvider>
    );

    // Должен retry и в итоге успешно инициализировать
    await waitFor(
      () => {
        expect(screen.getByTestId('app-content')).toBeInTheDocument();
      },
      { timeout: 5000 }
    );

    const { user } = useAuthStore.getState();
    expect(user?.email).toBe('test@example.com');
    expect(attempt).toBeGreaterThan(1); // Должно было быть несколько попыток
  });

  test('logs out after all retry attempts fail', async () => {
    localStorageMock.setItem('refreshToken', 'valid-token');

    // Mock /users/profile/ - все вызовы failят
    server.use(
      http.get('*/users/profile/', () => {
        return HttpResponse.error();
      })
    );

    render(
      <AuthProvider>
        <div data-testid="app-content">App Content</div>
      </AuthProvider>
    );

    // После всех попыток должен logout
    await waitFor(
      () => {
        expect(screen.getByTestId('app-content')).toBeInTheDocument();
      },
      { timeout: 10000 }
    );

    const { isAuthenticated } = useAuthStore.getState();
    expect(isAuthenticated).toBe(false);
    expect(localStorageMock.getItem('refreshToken')).toBeNull();
  });
});

describe('AuthProvider - useAuth Hook', () => {
  test('provides isInitialized and isLoading values', async () => {
    localStorageMock.clear();

    let hookValue: { isInitialized: boolean; isLoading: boolean } | null = null;

    function TestComponent() {
      // Используем useAuth hook из импорта
      hookValue = useAuth();
      return <div data-testid="test-component">Test</div>;
    }

    render(
      <AuthProvider>
        <TestComponent />
      </AuthProvider>
    );

    await waitFor(() => {
      expect(screen.getByTestId('test-component')).toBeInTheDocument();
      expect(hookValue?.isInitialized).toBe(true);
      expect(hookValue?.isLoading).toBe(false);
    });
  });
});
