/**
 * Password Reset Confirm Page
 * Story 28.3 - Восстановление пароля
 *
 * AC 2, 3: Страница подтверждения сброса пароля с валидацией токена
 * Route: /password-reset/confirm/[uid]/[token]
 */

import Link from 'next/link';
import { PasswordResetConfirmForm } from '@/components/auth/PasswordResetConfirmForm';

export const metadata = {
  title: 'Установка нового пароля | FREESPORT',
  description: 'Установите новый пароль для вашего аккаунта FREESPORT.',
};

interface PasswordResetConfirmPageProps {
  params: Promise<{
    uid: string;
    token: string;
  }>;
}

export default async function PasswordResetConfirmPage({ params }: PasswordResetConfirmPageProps) {
  // Await params для Next.js 15+ async params
  const { uid, token } = await params;

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50 py-12 px-4 sm:px-6 lg:px-8">
      <div className="max-w-md w-full space-y-8">
        {/* Header */}
        <div className="text-center">
          <h1 className="text-3xl font-bold text-gray-900">Установка нового пароля</h1>
          <p className="mt-2 text-sm text-gray-600">Введите новый пароль для вашего аккаунта</p>
        </div>

        {/* Form Card */}
        <div className="bg-white py-8 px-6 shadow-md rounded-lg border border-gray-200">
          <PasswordResetConfirmForm uid={uid} token={token} />
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
