import { cookies } from 'next/headers';
import type { UserRole } from '@/utils/pricing';

/**
 * Получает роль пользователя из backend API
 * Fallback на 'guest' если не авторизован
 */
export async function getUserRole(): Promise<UserRole> {
  try {
    const cookieStore = await cookies();
    const sessionId = cookieStore.get('sessionid')?.value || cookieStore.get('fs_session')?.value;

    if (!sessionId) {
      return 'guest';
    }

    // Для SSR в Docker используем внутренний URL backend
    // INTERNAL_API_URL - для серверных запросов внутри Docker network
    const apiUrl =
      process.env.INTERNAL_API_URL || process.env.NEXT_PUBLIC_API_URL || 'http://backend:8000';
    const response = await fetch(`${apiUrl}/api/v1/users/profile/`, {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
        Cookie: `sessionid=${sessionId}`,
      },
      cache: 'no-store', // Не кэшируем профиль для актуальности роли
    });

    if (!response.ok) {
      // При ошибке (401, 403, 500) возвращаем guest
      return 'guest';
    }

    const profile = await response.json();

    // Возвращаем роль пользователя из профиля
    const role = profile.role as UserRole;

    // Валидация роли - если роль неизвестна, используем retail как fallback
    const validRoles: UserRole[] = [
      'retail',
      'wholesale_level1',
      'wholesale_level2',
      'wholesale_level3',
      'trainer',
      'federation_rep',
      'admin',
      'guest',
    ];

    return validRoles.includes(role) ? role : 'retail';
  } catch {
    // При любой ошибке сети возвращаем guest (не логируем для чистоты консоли)
    return 'guest';
  }
}
