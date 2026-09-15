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
 */

import { beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import LoginPage from '../page';
import authService from '@/services/authService';

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
  fireEvent.change(screen.getByLabelText(/электронная почта/i), {
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
  render(<LoginPage />);
  submitForm();
  await waitFor(() => expect(mockPush).toHaveBeenCalledWith(expected));
}

/** Режим (б): уже авторизованный пользователь → router.replace. */
async function expectReplaceWhenAuthenticated(expected: string) {
  authState.isAuthenticated = true;
  render(<LoginPage />);
  await waitFor(() => expect(mockReplace).toHaveBeenCalledWith(expected));
}

beforeEach(() => {
  vi.clearAllMocks();
  authState.isAuthenticated = false;
  searchParamsRef.current = new URLSearchParams();
  vi.mocked(authService.login).mockResolvedValue(mockLoginResponse);
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
