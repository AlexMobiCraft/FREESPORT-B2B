/**
 * Page-level тесты страницы входа (Story 41.12 — Task 5.5, AC5/AC6).
 *
 * Рендерится реальный default export `/login` с реальным `LoginForm`; мокируются
 * только инфраструктурные зависимости (`useSearchParams`, router, authStore,
 * authService). Прямые тесты `LoginForm` остаются защитой компонента, но не
 * проверяют чтение query-параметров страницей.
 *
 * Каждая строка матрицы выполняется в двух режимах:
 * (а) успешный submit реальной формы → точный `router.push(expected)`;
 * (б) `isAuthenticated=true` → `router.replace(expected)` (заодно доказывает
 *     выход из spinner-ветки редиректом).
 *
 * Story 41.18: цель приходит и из cookie точки возврата (`Path=/login`). Страница —
 * серверный компонент: cookie читает `cookies()` из запроса, здесь мок отдаёт
 * то, что видит документ happy-dom на `/login`. Поэтому документ переводится на
 * `/login`, а cookie очищается до и после каждого теста. Матрицы A и B идут без
 * cookie и ожиданий не меняют.
 */

import { StrictMode } from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import LoginPage from '../page';
import LoginPageClient from '../LoginPageClient';
import authService from '@/services/authService';
import {
  LOGIN_RETURN_COOKIE,
  clearLoginReturnCookie,
  writeLoginReturnCookie,
} from '@/utils/loginReturn';

const { mockPush, mockReplace, searchParamsRef, authState } = vi.hoisted(() => ({
  mockPush: vi.fn(),
  mockReplace: vi.fn(),
  searchParamsRef: { current: new URLSearchParams() },
  authState: { isAuthenticated: false },
}));

vi.mock('next/navigation', () => ({
  useRouter: () => ({ push: mockPush, replace: mockReplace }),
  useSearchParams: () => searchParamsRef.current,
}));

// Cookie запроса на /login = то, что видит документ на /login в момент рендера
vi.mock('next/headers', () => ({
  cookies: async () => ({
    get: (name: string) => {
      const raw = document.cookie
        .split('; ')
        .find(part => part.startsWith(`${name}=`))
        ?.slice(name.length + 1);
      if (!raw) return undefined;
      try {
        return { name, value: decodeURIComponent(raw) };
      } catch {
        return undefined;
      }
    },
  }),
}));

vi.mock('@/stores/authStore', () => ({
  authSelectors: {
    useIsAuthenticated: () => authState.isAuthenticated,
  },
}));

vi.mock('@/services/authService', () => ({
  default: { login: vi.fn() },
}));

type LoginResult = Awaited<ReturnType<typeof authService.login>>;
const mockLoginResponse: LoginResult = {
  access: 'mock-token',
  refresh: 'mock-refresh',
  user: {
    id: 1,
    email: 'test@example.com',
    first_name: 'Test',
    last_name: 'User',
    phone: '',
    role: 'retail',
    is_verified: true,
  },
};

function setQuery(encoded: string) {
  searchParamsRef.current = new URLSearchParams(encoded);
}

function submitForm() {
  fireEvent.change(screen.getByLabelText(/учетное имя/i), {
    target: { value: 'test@example.com' },
  });
  fireEvent.change(screen.getByLabelText(/^пароль$/i), {
    target: { value: 'SecurePass123' },
  });
  fireEvent.click(screen.getByRole('button', { name: /войти/i }));
}

/** Режим (а): успешный вход через реальную форму → router.push. */
async function expectPushAfterSubmit(expected: string) {
  authState.isAuthenticated = false;
  render(await LoginPage());
  submitForm();
  await waitFor(() => expect(mockPush).toHaveBeenCalledWith(expected));
}

/** Режим (б): уже авторизованный пользователь → router.replace. */
async function expectReplaceWhenAuthenticated(expected: string) {
  authState.isAuthenticated = true;
  render(await LoginPage());
  await waitFor(() => expect(mockReplace).toHaveBeenCalledWith(expected));
}

beforeEach(() => {
  vi.clearAllMocks();
  authState.isAuthenticated = false;
  searchParamsRef.current = new URLSearchParams();
  vi.mocked(authService.login).mockResolvedValue(mockLoginResponse);
  window.history.pushState({}, '', '/login');
  clearLoginReturnCookie();
});

afterEach(() => {
  window.history.pushState({}, '', '/login');
  clearLoginReturnCookie();
  window.history.pushState({}, '', '/');
});

describe.each(['next', 'redirect'] as const)('Матрица A — один параметр (%s)', param => {
  const rows = [
    { encoded: '', runtime: null as string | null, expected: '/' },
    { encoded: `${param}=`, runtime: '', expected: '/' },
    { encoded: `${param}=%2F`, runtime: '/', expected: '/' },
    { encoded: `${param}=%2Fcheckout`, runtime: '/checkout', expected: '/checkout' },
    { encoded: `${param}=%2Fprofile`, runtime: '/profile', expected: '/profile' },
    {
      encoded: `${param}=%2Fcatalog%3Fcategory%3Dx%23top`,
      runtime: '/catalog?category=x#top',
      expected: '/catalog?category=x#top',
    },
    { encoded: `${param}=https%3A%2F%2Fevil.com`, runtime: 'https://evil.com', expected: '/' },
    { encoded: `${param}=%2F%2Fevil.com`, runtime: '//evil.com', expected: '/' },
    { encoded: `${param}=javascript%3Aalert%281%29`, runtime: 'javascript:alert(1)', expected: '/' },
    { encoded: `${param}=%5Cevil.com`, runtime: '\\evil.com', expected: '/' },
    { encoded: `${param}=%2F%5Cevil.com`, runtime: '/\\evil.com', expected: '/' },
    { encoded: `${param}=%2Fcatalog%5Citem`, runtime: '/catalog\\item', expected: '/' },
  ];

  it.each(rows)('после входа: "$encoded" → $expected', async ({ encoded, runtime, expected }) => {
    setQuery(encoded);
    // Сначала утверждаем декодированное runtime-значение (Task 5.6)
    expect(searchParamsRef.current.get(param)).toBe(runtime);
    await expectPushAfterSubmit(expected);
  });

  it.each(rows)(
    'уже авторизован: "$encoded" → $expected',
    async ({ encoded, runtime, expected }) => {
      setQuery(encoded);
      expect(searchParamsRef.current.get(param)).toBe(runtime);
      await expectReplaceWhenAuthenticated(expected);
    }
  );

  const authRoutes = [
    '/login',
    '/login/',
    '/login/anything',
    '/login?next=%2Fprofile',
    '/register',
    '/register/',
    '/register/anything',
    '/b2b-register',
    '/b2b-register/',
    '/b2b-register/anything',
    '/password-reset',
    '/password-reset/',
    '/password-reset/confirm/u/t',
    '/foo/../login',
  ];

  it.each(authRoutes)('после входа: auth-route %s → "/"', async route => {
    setQuery(`${param}=${encodeURIComponent(route)}`);
    expect(searchParamsRef.current.get(param)).toBe(route);
    await expectPushAfterSubmit('/');
  });

  it.each(authRoutes)('уже авторизован: auth-route %s → "/"', async route => {
    setQuery(`${param}=${encodeURIComponent(route)}`);
    expect(searchParamsRef.current.get(param)).toBe(route);
    await expectReplaceWhenAuthenticated('/');
  });
});

describe('Матрица B — оба параметра и приоритет', () => {
  const rows = [
    { encoded: 'next=%2Fcheckout&redirect=%2Fprofile', expected: '/checkout' },
    { encoded: 'next=%2Fprofile&redirect=https%3A%2F%2Fevil.com', expected: '/profile' },
    { encoded: 'next=https%3A%2F%2Fevil.com&redirect=%2Fprofile', expected: '/' },
    { encoded: 'next=%2Flogin%2F&redirect=%2Fprofile', expected: '/' },
    { encoded: 'next=%2F%5Cevil.com&redirect=%2Fprofile', expected: '/' },
    { encoded: 'next=&redirect=%2Fprofile', expected: '/profile' },
    { encoded: 'redirect=%2Fprofile', expected: '/profile' },
    { encoded: 'next=&redirect=', expected: '/' },
  ];

  it.each(rows)('после входа: "$encoded" → $expected', async ({ encoded, expected }) => {
    setQuery(encoded);
    await expectPushAfterSubmit(expected);
  });

  it.each(rows)('уже авторизован: "$encoded" → $expected', async ({ encoded, expected }) => {
    setQuery(encoded);
    await expectReplaceWhenAuthenticated(expected);
  });
});

describe('Cookie точки возврата (Story 41.18 — AC2, S1/S6/S8/S10/S11)', () => {
  const rows = [
    { encoded: '', cookie: '/profile/favorites', expected: '/profile/favorites' },
    { encoded: 'next=%2Fcart', cookie: '/profile', expected: '/cart' },
    { encoded: 'next=https%3A%2F%2Fevil.com', cookie: '/checkout', expected: '/checkout' },
    { encoded: '', cookie: '//evil.com', expected: '/' },
  ];

  it.each(rows)(
    'после входа: "$encoded" + cookie $cookie → $expected',
    async ({ encoded, cookie, expected }) => {
      setQuery(encoded);
      document.cookie = `${LOGIN_RETURN_COOKIE}=${encodeURIComponent(cookie)}; Path=/login`;
      await expectPushAfterSubmit(expected);
    }
  );

  it.each(rows)(
    'уже авторизован: "$encoded" + cookie $cookie → $expected',
    async ({ encoded, cookie, expected }) => {
      setQuery(encoded);
      document.cookie = `${LOGIN_RETURN_COOKIE}=${encodeURIComponent(cookie)}; Path=/login`;
      await expectReplaceWhenAuthenticated(expected);
      // Мок useRouter отдаёт новый объект на каждый рендер, эффект может сработать
      // повторно — но ни один вызов не должен уводить не туда
      expect(mockReplace.mock.calls.every(([arg]) => arg === expected)).toBe(true);
      expect(document.cookie).not.toContain(`${LOGIN_RETURN_COOKIE}=`);
    }
  );

  it('страница забирает cookie сразу при открытии, до входа', async () => {
    writeLoginReturnCookie('/profile/favorites');
    expect(document.cookie).toContain(LOGIN_RETURN_COOKIE);

    render(await LoginPage());

    await waitFor(() => expect(document.cookie).not.toContain(`${LOGIN_RETURN_COOKIE}=`));
    expect(mockPush).not.toHaveBeenCalled();
  });

  it('S8: ушёл со страницы, не войдя, потом сам открыл /login → вход ведёт на "/"', async () => {
    writeLoginReturnCookie('/profile');
    const first = render(await LoginPage());
    await waitFor(() => expect(document.cookie).not.toContain(`${LOGIN_RETURN_COOKIE}=`));
    first.unmount();

    await expectPushAfterSubmit('/');
  });

  it('S11: неудачный вход (401), затем успешный — цель из памяти страницы сохранена', async () => {
    writeLoginReturnCookie('/profile/favorites');
    vi.mocked(authService.login).mockRejectedValueOnce({
      response: { status: 401, data: { detail: 'Invalid credentials' } },
    });

    render(await LoginPage());
    submitForm();
    expect(await screen.findByText('Неверные учетные данные')).toBeInTheDocument();
    expect(mockPush).not.toHaveBeenCalled();

    submitForm();
    await waitFor(() => expect(mockPush).toHaveBeenCalledWith('/profile/favorites'));
  });

  it('StrictMode: повторный запуск эффекта цель не теряет (после входа)', async () => {
    writeLoginReturnCookie('/checkout');
    render(
      <StrictMode>
        {await LoginPage()}
      </StrictMode>
    );
    submitForm();
    await waitFor(() => expect(mockPush).toHaveBeenCalledWith('/checkout'));
  });

  it('StrictMode: восстановленная сессия уходит на цель из cookie, а не на "/"', async () => {
    writeLoginReturnCookie('/profile/favorites');
    authState.isAuthenticated = true;
    render(
      <StrictMode>
        {await LoginPage()}
      </StrictMode>
    );
    await waitFor(() => expect(mockReplace).toHaveBeenCalled());
    expect(mockReplace.mock.calls.every(([arg]) => arg === '/profile/favorites')).toBe(true);
  });
});

describe('Серверное чтение cookie (Story 41.18 — клиентская навигация в Chromium)', () => {
  it('документ cookie не видит, но значение из запроса ведёт на цель и cookie удаляется', async () => {
    // Chromium после клиентской навигации не показывает cookie с Path=/login в
    // document.cookie: имитируем — cookie есть, но документ на другом адресе
    writeLoginReturnCookie('/profile/favorites');
    window.history.pushState({}, '', '/home');
    expect(document.cookie).not.toContain(LOGIN_RETURN_COOKIE);

    render(<LoginPageClient returnCookie="/profile/favorites" />);
    submitForm();
    await waitFor(() => expect(mockPush).toHaveBeenCalledWith('/profile/favorites'));

    // Удаление с явным Path=/login сработало и с чужого адреса документа
    window.history.pushState({}, '', '/login');
    expect(document.cookie).not.toContain(`${LOGIN_RETURN_COOKIE}=`);
  });

  it('смена пропа после открытия цель не затирает (память страницы)', async () => {
    const view = render(<LoginPageClient returnCookie="/checkout" />);
    view.rerender(<LoginPageClient returnCookie={null} />);
    submitForm();
    await waitFor(() => expect(mockPush).toHaveBeenCalledWith('/checkout'));
  });
});
