/**
 * Login Page
 * Story 28.1 - Базовая аутентификация и регистрация B2C
 * Story 28.4 - Защищенные маршруты и управление сессиями
 *
 * Страница входа в систему
 *
 * AC 1: Login Flow с поддержкой ?next= и ?redirect= query параметров
 */

'use client';

import React, { Suspense } from 'react';
import Link from 'next/link';
import { useSearchParams } from 'next/navigation';
import { LoginForm } from '@/components/auth/LoginForm';
import { Spinner } from '@/components/ui/Spinner/Spinner';

/**
 * LoginPageContent - отдельный компонент для использования useSearchParams
 * (требуется из-за Suspense boundary в Next.js 15)
 */
function LoginPageContent() {
  const searchParams = useSearchParams();
  // Поддержка обоих параметров: 'next' (middleware) и 'redirect' (legacy)
  const redirectUrl = searchParams.get('next') || searchParams.get('redirect') || undefined;

  return (
    <div className="min-h-screen flex items-center justify-center bg-[var(--color-neutral-100)] py-12 px-4 sm:px-6 lg:px-8">
      <div className="max-w-md w-full space-y-8">
        {/* Header */}
        <div className="text-center">
          <h1 className="text-heading-l font-bold text-[var(--color-text-primary)] mb-2">
            Вход в FREESPORT
          </h1>
          <p className="text-body-m text-[var(--color-text-muted)]">
            Войдите в свой аккаунт для доступа к платформе
          </p>
        </div>

        {/* Login Form */}
        <div className="bg-white rounded-lg shadow-[var(--shadow-default)] p-8">
          <LoginForm redirectUrl={redirectUrl} />

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
 * LoginPage - основная страница с Suspense boundary
 */
export default function LoginPage() {
  return (
    <Suspense
      fallback={
        <div className="min-h-screen flex items-center justify-center">
          <Spinner size="large" />
        </div>
      }
    >
      <LoginPageContent />
    </Suspense>
  );
}
