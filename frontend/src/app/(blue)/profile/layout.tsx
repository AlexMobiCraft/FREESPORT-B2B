/**
 * Profile Route Group Layout
 * Layout для защищённых маршрутов личного кабинета (/profile/*)
 * Story 16.1 - AC: 1, 5
 *
 * ВАЖНО: Middleware (`frontend/src/middleware.ts`) УЖЕ защищает `/profile/*` маршруты.
 * Layout не требует дополнительной auth проверки - middleware автоматически
 * редиректит неавторизованных пользователей на `/login` с cookie точки возврата (стори 41.18).
 * AuthGate держит спиннер, пока AuthProvider не восстановит сессию: кабинет
 * рисуется из authStore и без него показал бы пустого пользователя.
 */

import React from 'react';
import ProfileLayout from '@/components/layout/ProfileLayout';
import { AuthGate } from '@/components/auth/AuthGate';

/**
 * Props для layout компонента
 */
interface ProfileRouteLayoutProps {
  children: React.ReactNode;
}

/**
 * Layout для route group (profile)
 * Оборачивает все дочерние маршруты в ProfileLayout с навигацией
 */
export default function ProfileRouteLayout({ children }: ProfileRouteLayoutProps) {
  return (
    <AuthGate>
      <ProfileLayout>{children}</ProfileLayout>
    </AuthGate>
  );
}
