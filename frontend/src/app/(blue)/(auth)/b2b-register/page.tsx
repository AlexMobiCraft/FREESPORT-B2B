/**
 * B2B Register Page
 * Story 28.2 - Поток регистрации B2B
 *
 * Страница регистрации B2B пользователей (бизнес-партнеров)
 *
 * AC 1: Отдельная страница /b2b-register
 * AC 3: Визуальное отличие от B2C регистрации
 */

'use client';

import React, { Suspense } from 'react';
import Link from 'next/link';
import { useSearchParams } from 'next/navigation';
import { B2BRegisterForm } from '@/components/auth/B2BRegisterForm';

function B2BRegisterContent() {
  const searchParams = useSearchParams();
  const redirectUrl = searchParams.get('next') || searchParams.get('redirect') || undefined;

  return (
    <div className="bg-white rounded-lg shadow-[var(--shadow-default)] p-8">
      <B2BRegisterForm redirectUrl={redirectUrl} />

      {/* AC 3: Ссылка на B2C регистрацию */}
      <div className="mt-6 pt-6 border-t border-gray-200 text-center">
        <p className="text-body-s text-[var(--color-text-muted)]">
          Не бизнес-клиент?{' '}
          <Link
            href="/register"
            className="font-medium text-primary hover:text-primary-hover transition-colors"
          >
            Обычная регистрация
          </Link>
        </p>
      </div>

      {/* Link to Login */}
      <div className="mt-4 text-center">
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

export default function B2BRegisterPage() {
  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-blue-50 to-gray-100 py-12 px-4 sm:px-6 lg:px-8">
      <div className="max-w-2xl w-full space-y-8">
        {/* Header - AC 3: Визуальное отличие */}
        <div className="text-center">
          <div className="flex justify-center items-center space-x-2 mb-4">
            <svg
              className="w-10 h-10 text-blue-600"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
              aria-hidden="true"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4"
              />
            </svg>
            <h1 className="text-heading-l font-bold text-[var(--color-text-primary)]">
              Регистрация для бизнеса
            </h1>
          </div>
          <p className="text-body-m text-[var(--color-text-muted)] max-w-lg mx-auto">
            Зарегистрируйтесь как бизнес-партнер для получения доступа к оптовым ценам и специальным
            условиям
          </p>
        </div>

        {/* B2B Register Form with Suspense */}
        <Suspense
          fallback={<div className="bg-white rounded-lg shadow p-8 h-[800px] animate-pulse" />}
        >
          <B2BRegisterContent />
        </Suspense>

        {/* Дополнительная информация о преимуществах */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mt-8">
          <div className="bg-white p-4 rounded-lg shadow-sm">
            <div className="flex items-center space-x-2 mb-2">
              <svg
                className="w-5 h-5 text-primary"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
                />
              </svg>
              <h3 className="text-body-m font-semibold">Оптовые цены</h3>
            </div>
            <p className="text-body-xs text-gray-600">Скидки до 40% для постоянных партнеров</p>
          </div>

          <div className="bg-white p-4 rounded-lg shadow-sm">
            <div className="flex items-center space-x-2 mb-2">
              <svg
                className="w-5 h-5 text-primary"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"
                />
              </svg>
              <h3 className="text-body-m font-semibold">Персональный менеджер</h3>
            </div>
            <p className="text-body-xs text-gray-600">Индивидуальное обслуживание и консультации</p>
          </div>

          <div className="bg-white p-4 rounded-lg shadow-sm">
            <div className="flex items-center space-x-2 mb-2">
              <svg
                className="w-5 h-5 text-primary"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M13 10V3L4 14h7v7l9-11h-7z"
                />
              </svg>
              <h3 className="text-body-m font-semibold">Быстрая обработка</h3>
            </div>
            <p className="text-body-xs text-gray-600">Проверка заявки в течение 1-2 рабочих дней</p>
          </div>
        </div>
      </div>
    </div>
  );
}
