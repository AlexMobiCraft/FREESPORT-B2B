/**
 * Login Page — клиентская часть
 * Story 28.1 - Базовая аутентификация и регистрация B2C
 * Story 28.4 - Защищенные маршруты и управление сессиями
 *
 * Страница входа в систему
 *
 * AC 1: Login Flow с поддержкой ?next= и ?redirect= query параметров
 * Story 41.18: точка возврата приходит и из cookie `loginReturnTo`. Значение
 * читает серверная часть (`page.tsx`) и передаёт пропом; клиент при открытии
 * переносит его в свою память и удаляет cookie
 */

'use client';

import React, { Suspense, useEffect, useState } from 'react';
import Link from 'next/link';
import { useSearchParams, useRouter } from 'next/navigation';
import { LoginForm } from '@/components/auth/LoginForm';
import { Spinner } from '@/components/ui/Spinner/Spinner';
import { authSelectors } from '@/stores/authStore';
import { clearLoginReturnCookie, resolvePostLoginTarget } from '@/utils/loginReturn';

interface LoginPageClientProps {
  /** Значение cookie точки возврата из запроса на `/login` (читает сервер) */
  returnCookie: string | null;
}

/**
 * LoginPageContent - отдельный компонент для использования useSearchParams
 * (требуется из-за Suspense boundary в Next.js 15)
 */
function LoginPageContent({ returnCookie }: LoginPageClientProps) {
  const searchParams = useSearchParams();
  const router = useRouter();
  const isAuthenticated = authSelectors.useIsAuthenticated();
  // Поддержка обоих параметров: 'next' и 'redirect' — старые ссылки (41.18: URL важнее cookie)
  const urlCandidate = searchParams?.get('next') || searchParams?.get('redirect') || null;

  // Цель из cookie точки возврата — в памяти страницы: запоминается первое
  // значение, и повторный рендер без cookie её не затирает (S11)
  const [cookieTarget] = useState(returnCookie);

  // Cookie действует только на этот заход на /login (S8): удаляется сразу при
  // открытии. Удаление с явным Path=/login работает с любого адреса документа
  useEffect(() => {
    if (cookieTarget) clearLoginReturnCookie();
  }, [cookieTarget]);

  const target = resolvePostLoginTarget(urlCandidate, cookieTarget);

  // Редирект аутентифицированного пользователя со страницы логина
  // Это обрабатывает случай, когда AuthProvider восстановил сессию из localStorage,
  // но middleware уже перенаправил на /login (т.к. cookie отсутствовала)
  useEffect(() => {
    if (isAuthenticated) {
      router.replace(target);
    }
  }, [isAuthenticated, target, router]);

  if (isAuthenticated) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <Spinner size="large" />
      </div>
    );
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-[var(--color-neutral-100)] py-12 px-4 sm:px-6 lg:px-8">
      <div className="max-w-md w-full space-y-8">
        {/* Header */}
        <div className="text-center">
          <h1 className="text-heading-l font-bold text-[var(--color-text-primary)] mb-2">
            Вход на портал
          </h1>
          <p className="text-body-m text-[var(--color-text-muted)]">
            Войдите в свой аккаунт для доступа к платформе
          </p>
        </div>

        {/* Login Form */}
        <div className="bg-white rounded-lg shadow-[var(--shadow-default)] p-8">
          <LoginForm redirectUrl={target} />

          {/* Link to Register */}
          <div className="mt-6 text-center">
            <p className="text-body-s text-[var(--color-text-muted)]">
              Нет аккаунта?{' '}
              <Link
                href="/register"
                className="font-medium text-primary hover:text-primary-hover transition-colors"
              >
                Зарегистрироваться
              </Link>
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}

/**
 * LoginPageClient - клиентская часть страницы с Suspense boundary
 */
export default function LoginPageClient({ returnCookie }: LoginPageClientProps) {
  return (
    <Suspense
      fallback={
        <div className="min-h-screen flex items-center justify-center">
          <Spinner size="large" />
        </div>
      }
    >
      <LoginPageContent returnCookie={returnCookie} />
    </Suspense>
  );
}
