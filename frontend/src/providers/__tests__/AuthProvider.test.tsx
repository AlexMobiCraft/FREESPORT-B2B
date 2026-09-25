/**
 * AuthProvider Integration Tests
 * Story 28.4 - Защищенные маршруты и управление сессиями
 *
 * Тестирует:
 * - Успешная инициализация с валидным refresh token
 * - Logout при истекшем refresh token (401/403)
 * - Дети рендерятся сразу, isInitialized публикуется через контекст
 * - Обработка network errors с retry logic
 * - Запросы детей ждут восстановления сессии (authReadyGate)
 * - Заблокированный localStorage не подвешивает инициализацию
 */

import { describe, test, expect, vi, beforeEach, afterEach, beforeAll, afterAll } from 'vitest';
import React, { useEffect } from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import { AuthProvider, useAuth } from '../AuthProvider';
import { useAuthStore } from '@/stores/authStore';
import apiClient from '@/services/api-client';
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

/** Состояние контекста в DOM: дети рендерятся сразу, конец инициализации виден только здесь */
function AuthStateProbe() {
  const { isInitialized, isLoading } = useAuth();
  return (
    <div data-testid="auth-state">
      {isInitialized ? 'initialized' : 'pending'}
      {isLoading ? ':loading' : ''}
    </div>
  );
}

function renderProvider(extraChildren?: React.ReactNode) {
  return render(
    <AuthProvider>
      <div data-testid="app-content">App Content</div>
      <AuthStateProbe />
      {extraChildren}
    </AuthProvider>
  );
}

async function waitForInit(timeout?: number) {
  await waitFor(
    () => {
      expect(screen.getByTestId('auth-state')).toHaveTextContent(/^initialized$/);
    },
    timeout ? { timeout } : undefined
  );
}

const PROFILE = {
  id: 1,
  email: 'test@example.com',
  first_name: 'Test',
  last_name: 'User',
  role: 'wholesale_level1',
  is_verified: true,
};

/** Ребёнок, который, как секции главной, грузит данные в useEffect при монтировании */
function EagerFetcher({ onDone }: { onDone: () => void }) {
  useEffect(() => {
    apiClient
      .get('/products/probe/')
      .catch(() => undefined)
      .finally(onDone);
  }, [onDone]);
  return null;
}

async function resetAuth() {
  // Clear localStorage и authStore перед каждым тестом
  localStorageMock.clear();
  server.resetHandlers();
  // Возвращаем базовые handlers (включая /users/profile/, /auth/logout/, /auth/refresh/)
  server.use(...baseHandlers);
  // Story 31.2: logout теперь async
  await useAuthStore.getState().logout();
  vi.clearAllMocks();
}

describe('AuthProvider - Session Initialization', () => {
  beforeEach(resetAuth);

  afterEach(() => {
    vi.restoreAllMocks();
  });

  test('initializes without refresh token - shows children immediately', async () => {
    const profileSpy = vi.fn();
    server.use(
      http.get('*/users/profile/', () => {
        profileSpy();
        return HttpResponse.json(PROFILE);
      })
    );

    renderProvider();

    expect(screen.getByTestId('app-content')).toBeInTheDocument();
    await waitForInit();

    // Профиль не запрашивался, store пуст
    expect(profileSpy).not.toHaveBeenCalled();
    expect(useAuthStore.getState().user).toBeNull();
  });

  test('initializes session with valid refresh token', async () => {
    localStorageMock.setItem('refreshToken', 'valid-refresh-token');
    server.use(http.get('*/users/profile/', () => HttpResponse.json(PROFILE)));

    renderProvider();
    await waitForInit();

    // Проверка: authStore был обновлен
    const { user } = useAuthStore.getState();
    expect(user?.email).toBe('test@example.com');
    expect(user?.role).toBe('wholesale_level1');
  });

  test('logs out on expired refresh token (401)', async () => {
    localStorageMock.setItem('refreshToken', 'expired-token');

    server.use(
      http.get('*/users/profile/', () => {
        return HttpResponse.json({ detail: 'Invalid token' }, { status: 401 });
      }),
      // ВАЖНО: api-client interceptor попытается refresh при 401, нужно обработать
      http.post('*/auth/refresh/', () => {
        return HttpResponse.json({ detail: 'Invalid refresh token' }, { status: 401 });
      })
    );

    renderProvider();
    await waitForInit();

    // Проверка: logout был вызван
    await waitFor(() => {
      expect(localStorageMock.getItem('refreshToken')).toBeNull();
    });
    expect(useAuthStore.getState().isAuthenticated).toBe(false);
  });

  test('logs out on forbidden token (403)', async () => {
    localStorageMock.setItem('refreshToken', 'forbidden-token');

    server.use(
      http.get('*/users/profile/', () => {
        return HttpResponse.json({ detail: 'Token expired' }, { status: 403 });
      })
    );

    renderProvider();
    await waitForInit();

    expect(useAuthStore.getState().isAuthenticated).toBe(false);
  });

  test('renders children and no spinner while session is restoring', async () => {
    localStorageMock.setItem('refreshToken', 'valid-token');

    server.use(
      http.get('*/users/profile/', async () => {
        await new Promise(resolve => setTimeout(resolve, 100));
        return HttpResponse.json(PROFILE);
      })
    );

    renderProvider();

    // Сервер рендерит это же состояние: содержимое есть, инициализация идёт
    expect(screen.getByTestId('app-content')).toBeInTheDocument();
    expect(screen.getByTestId('auth-state')).toHaveTextContent('pending:loading');
    expect(screen.queryByText('Загрузка...')).not.toBeInTheDocument();

    await waitForInit();
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
        return HttpResponse.json(PROFILE);
      })
    );

    renderProvider();

    // Должен retry и в итоге успешно инициализировать
    await waitForInit(5000);

    const { user } = useAuthStore.getState();
    expect(user?.email).toBe('test@example.com');
    expect(attempt).toBeGreaterThan(1); // Должно было быть несколько попыток
  });

  test('preserves tokens after all retry attempts fail (network error)', async () => {
    localStorageMock.setItem('refreshToken', 'valid-token');

    // Mock /users/profile/ - все вызовы failят (network error, не 401/403)
    server.use(
      http.get('*/users/profile/', () => {
        return HttpResponse.error();
      })
    );

    renderProvider();

    // После всех попыток инициализация завершается, но logout НЕ вызывается
    // (сохраняем токены для повторных попыток при временной недоступности бэкенда)
    await waitForInit(10000);

    const { isAuthenticated } = useAuthStore.getState();
    expect(isAuthenticated).toBe(false);
    // Токены сохраняются — network error не должен приводить к потере сессии
    expect(localStorageMock.getItem('refreshToken')).toBe('valid-token');
  });

  test('blocked localStorage: finishes as guest instead of hanging', async () => {
    // mockRestore явно: vi.restoreAllMocks не снимает spyOn с localStorage
    const getItemSpy = vi.spyOn(localStorageMock, 'getItem').mockImplementation(() => {
      throw new DOMException('The operation is insecure.', 'SecurityError');
    });
    const warnSpy = vi.spyOn(console, 'warn').mockImplementation(() => {});

    try {
      renderProvider();
      await waitForInit();

      expect(screen.getByTestId('app-content')).toBeInTheDocument();
      expect(useAuthStore.getState().user).toBeNull();
      expect(warnSpy).toHaveBeenCalled();
    } finally {
      getItemSpy.mockRestore();
      warnSpy.mockRestore();
    }
  });
});

describe('AuthProvider - запросы детей ждут восстановления сессии', () => {
  beforeEach(resetAuth);

  afterEach(() => {
    vi.restoreAllMocks();
  });

  /** Порядок событий на «сервере» и заголовок Authorization запроса ребёнка */
  function trackRequests(profileResponse: () => Response) {
    const events: string[] = [];
    let probeAuthorization: string | null = 'not-requested';
    server.use(
      http.get('*/users/profile/', async () => {
        await new Promise(resolve => setTimeout(resolve, 50));
        events.push('profile');
        return profileResponse();
      }),
      http.post('*/auth/refresh/', () => {
        events.push('refresh');
        return HttpResponse.json({ access: 'fresh-access' });
      }),
      http.get('*/products/probe/', ({ request }) => {
        events.push('probe');
        probeAuthorization = request.headers.get('Authorization');
        return HttpResponse.json({ ok: true });
      })
    );
    // MSW в jsdom видит один XHR-запрос дважды (XHR и нижележащий http) —
    // сравниваем порядок первых появлений, а не число срабатываний
    return {
      order: () => [...new Set(events)],
      getProbeAuthorization: () => probeAuthorization,
    };
  }

  test('запрос ребёнка уходит после профиля и с новым токеном', async () => {
    localStorageMock.setItem('refreshToken', 'valid-token');
    const { order, getProbeAuthorization } = trackRequests(() => HttpResponse.json(PROFILE));
    const onDone = vi.fn();

    renderProvider(<EagerFetcher onDone={onDone} />);

    await waitFor(() => expect(onDone).toHaveBeenCalled());
    expect(order()).toEqual(['profile', 'refresh', 'probe']);
    expect(getProbeAuthorization()).toBe('Bearer fresh-access');
  });

  test('без refresh token запрос ребёнка не ждёт', async () => {
    const { order, getProbeAuthorization } = trackRequests(() => HttpResponse.json(PROFILE));
    const onDone = vi.fn();

    renderProvider(<EagerFetcher onDone={onDone} />);

    await waitFor(() => expect(onDone).toHaveBeenCalled());
    expect(order()).toEqual(['probe']);
    expect(getProbeAuthorization()).toBeNull();
  });

  test('истёкшая сессия (403): ожидание снимается, запрос уходит анонимно', async () => {
    localStorageMock.setItem('refreshToken', 'expired-token');
    vi.spyOn(console, 'warn').mockImplementation(() => {});
    const { order, getProbeAuthorization } = trackRequests(() =>
      HttpResponse.json({ detail: 'Token expired' }, { status: 403 })
    );
    const onDone = vi.fn();

    renderProvider(<EagerFetcher onDone={onDone} />);

    await waitFor(() => expect(onDone).toHaveBeenCalled());
    expect(order()).toEqual(['profile', 'probe']);
    expect(getProbeAuthorization()).toBeNull();
  });

  test('исключение внутри инициализации тоже снимает ожидание', async () => {
    localStorageMock.setItem('refreshToken', 'valid-token');
    // accessToken из cookie гидрируется через setTokens до запроса профиля, вне
    // внутренних try; setTokens пишет в localStorage — пусть бросит
    document.cookie = 'accessToken=cookie-access;path=/';
    const setItemSpy = vi.spyOn(localStorageMock, 'setItem').mockImplementation(() => {
      throw new DOMException('Quota exceeded', 'QuotaExceededError');
    });
    const warnSpy = vi.spyOn(console, 'warn').mockImplementation(() => {});
    const { order, getProbeAuthorization } = trackRequests(() => HttpResponse.json(PROFILE));
    const onDone = vi.fn();

    try {
      renderProvider(<EagerFetcher onDone={onDone} />);

      await waitFor(() => expect(onDone).toHaveBeenCalled());
      await waitForInit();
      expect(order()).toEqual(['probe']);
      expect(getProbeAuthorization()).toBeNull();
      expect(warnSpy).toHaveBeenCalledWith('Auth initialization failed:', expect.any(DOMException));
    } finally {
      setItemSpy.mockRestore();
      warnSpy.mockRestore();
      document.cookie = 'accessToken=;expires=Thu, 01 Jan 1970 00:00:00 UTC;path=/';
    }
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
