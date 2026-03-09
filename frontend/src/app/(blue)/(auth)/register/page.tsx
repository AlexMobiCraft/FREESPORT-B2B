/**
 * Register Page
 * Story 28.1 - Базовая аутентификация и регистрация B2C
 *
 * Страница регистрации B2C пользователей
 *
 * AC 2: B2C Registration Flow с автологином
 */

'use client';

import React, { Suspense } from 'react';
import Link from 'next/link';
import { useSearchParams } from 'next/navigation';
import { RegisterForm } from '@/components/auth/RegisterForm';

function RegisterFormContent() {
  const searchParams = useSearchParams();
  // Support both 'next' (Django standard) and 'redirect' (common pattern)
  const redirectUrl = searchParams.get('next') || searchParams.get('redirect') || undefined;

  return (
    <div className="bg-white rounded-lg shadow-[var(--shadow-default)] p-8">
      <RegisterForm redirectUrl={redirectUrl} />

      {/* Link to Login */}
      <div className="mt-6 text-center">
        <p className="text-body-s text-[var(--color-text-muted)]">
          Уже есть аккаунт?{' '}
          <Link
            href="/login"
            className="font-medium text-primary hover:text-primary-hover transition-colors"
          >
            Войти
          </Link>
        </p>
      </div>
    </div>
  );
}

export default function RegisterPage() {
  return (
    <div className="min-h-screen flex items-center justify-center bg-[var(--color-neutral-100)] py-12 px-4 sm:px-6 lg:px-8">
      <div className="max-w-md w-full space-y-8">
        {/* Header */}
        <div className="text-center">
          <h1 className="text-heading-l font-bold text-[var(--color-text-primary)] mb-2">
            Регистрация в FREESPORT
          </h1>
          <p className="text-body-m text-[var(--color-text-muted)]">
            Создайте аккаунт для доступа к платформе
          </p>
        </div>

        {/* Register Form with Suspense */}
        <Suspense
          fallback={<div className="bg-white rounded-lg shadow p-8 h-[500px] animate-pulse" />}
        >
          <RegisterFormContent />
        </Suspense>
      </div>
    </div>
  );
}
