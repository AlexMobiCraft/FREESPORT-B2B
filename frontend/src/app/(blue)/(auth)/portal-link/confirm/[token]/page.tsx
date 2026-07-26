/**
 * Portal Link Confirm Page
 *
 * Страница подтверждения привязки 1С-клиента к регистрации на портале
 * (email формы отличался от email в 1С) — ссылка из письма
 * portal_link_confirmation.{html,txt}.
 * Route: /portal-link/confirm/[token]
 */

import Link from 'next/link';
import { PortalLinkConfirmForm } from '@/components/auth/PortalLinkConfirmForm';

export const metadata = {
  title: 'Подтверждение привязки аккаунта | FREESPORT',
  description: 'Подтвердите привязку регистрации к записи в 1С и задайте пароль.',
};

interface PortalLinkConfirmPageProps {
  params: Promise<{
    token: string;
  }>;
}

export default async function PortalLinkConfirmPage({ params }: PortalLinkConfirmPageProps) {
  const { token } = await params;

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50 py-12 px-4 sm:px-6 lg:px-8">
      <div className="max-w-md w-full space-y-8">
        <div className="text-center">
          <h1 className="text-3xl font-bold text-gray-900">Подтверждение привязки аккаунта</h1>
          <p className="mt-2 text-sm text-gray-600">
            Задайте пароль, чтобы завершить привязку регистрации к записи в 1С
          </p>
        </div>

        <div className="bg-white py-8 px-6 shadow-md rounded-lg border border-gray-200">
          <PortalLinkConfirmForm token={token} />
        </div>

        <div className="text-center">
          <Link href="/login" className="text-sm text-primary hover:text-primary-hover underline">
            Вернуться на страницу входа
          </Link>
        </div>
      </div>
    </div>
  );
}
