/**
 * Profile Route Group Layout
 * Layout для защищённых маршрутов личного кабинета (/profile/*)
 * Story 16.1 - AC: 1, 5
 *
 * ВАЖНО: Middleware (`frontend/src/middleware.ts`) УЖЕ защищает `/profile/*` маршруты.
 * Layout не требует дополнительной auth проверки - middleware автоматически
 * редиректит неавторизованных пользователей на `/login?next=/profile`.
 */

import React from 'react';
import ProfileLayout from '@/components/layout/ProfileLayout';

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
  return <ProfileLayout>{children}</ProfileLayout>;
}
