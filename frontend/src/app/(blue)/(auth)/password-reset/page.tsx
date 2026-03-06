/**
 * Password Reset Request Page
 * Story 28.3 - Восстановление пароля
 *
 * AC 1: Страница запроса на сброс пароля
 * Route: /password-reset
 */

import Link from 'next/link';
import { PasswordResetRequestForm } from '@/components/auth/PasswordResetRequestForm';

export const metadata = {
  title: 'Восстановление пароля | FREESPORT',
  description: 'Запросить ссылку для сброса пароля. Введите ваш email для получения инструкций.',
};

export default function PasswordResetPage() {
  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50 py-12 px-4 sm:px-6 lg:px-8">
      <div className="max-w-md w-full space-y-8">
        {/* Header */}
        <div className="text-center">
          <h1 className="text-3xl font-bold text-gray-900">Восстановление пароля</h1>
          <p className="mt-2 text-sm text-gray-600">
            Введите ваш email для получения ссылки на сброс пароля
          </p>
        </div>

        {/* Form Card */}
        <div className="bg-white py-8 px-6 shadow-md rounded-lg border border-gray-200">
          <PasswordResetRequestForm />
        </div>

        {/* Back to Login Link */}
        <div className="text-center">
          <Link href="/login" className="text-sm text-primary hover:text-primary-hover underline">
            Вернуться на страницу входа
          </Link>
        </div>
      </div>
    </div>
  );
}
