/**
 * Auth Store - управление аутентификацией и пользователем
 *
 * @security
 * - Access token хранится ТОЛЬКО в memory (Zustand store)
 * - Refresh token хранится в localStorage И cookies (для middleware)
 * - Tokens очищаются при logout
 */

import { create } from 'zustand';
import { devtools } from 'zustand/middleware';
import type { User } from '@/types/api';

/**
 * Утилита для установки cookie (для синхронизации с middleware)
 */
function setCookie(name: string, value: string, days: number = 30) {
  const expires = new Date();
  expires.setTime(expires.getTime() + days * 24 * 60 * 60 * 1000);
  document.cookie = `${name}=${value};expires=${expires.toUTCString()};path=/;SameSite=Lax`;
}

/**
 * Утилита для удаления cookie
 */
function deleteCookie(name: string) {
  document.cookie = `${name}=;expires=Thu, 01 Jan 1970 00:00:00 UTC;path=/;`;
}

interface AuthState {
  accessToken: string | null;
  user: User | null;
  isAuthenticated: boolean;

  // Actions
  setTokens: (access: string, refresh: string) => void;
  setUser: (user: User) => void;
  logout: (skipServerLogout?: boolean) => Promise<void>;
  getRefreshToken: () => string | null;
}

export const useAuthStore = create<AuthState>()(
  devtools(
    set => ({
      accessToken: null,
      user: null,
      isAuthenticated: false,

      setTokens: (access: string, refresh: string) => {
        // Refresh token в localStorage для persistence
        localStorage.setItem('refreshToken', refresh);

        /**
         * Cookie Sync Strategy (Story 28.4)
         *
         * WHY: Next.js Middleware runs on Edge Runtime и НЕ имеет доступа к localStorage.
         * Для проверки аутентификации на protected routes middleware нужен доступ к
         * refresh token через cookies.
         *
         * IMPLEMENTATION:
         * - localStorage: Primary storage для client-side JavaScript
         * - Cookie: Fallback для Edge Runtime middleware (читается через request.cookies)
         * - Оба синхронизируются при login/logout для консистентности
         *
         * SECURITY:
         * - Cookie НЕ HttpOnly (доступен JS), т.к. middleware - это только UX improvement
         * - Реальная валидация токенов происходит на backend при каждом API request
         * - SameSite=Lax для CSRF protection
         */
        setCookie('refreshToken', refresh, 30);
        // Story 16.2: Access token в cookies для SSR
        setCookie('accessToken', access, 30);

        // Access token ТОЛЬКО в memory
        set({
          accessToken: access,
          isAuthenticated: true,
        });
      },

      setUser: (user: User) => {
        set({ user });
      },

      /**
       * Выход из системы с инвалидацией токена на сервере
       * Story 31.2 - AC 5, 6: Async logout с вызовом backend API
       *
       * @param skipServerLogout - Если true, пропускает попытку выхода на сервере.
       * Используется когда известно, что токены уже невалидны (например, при ответе 401),
       * чтобы избежать бесконечного цикла запросов.
       *
       * Fail-safe: Локальная очистка ВСЕГДА происходит, даже при ошибке API
       */
      logout: async (skipServerLogout?: boolean) => {
        const refreshToken = localStorage.getItem('refreshToken');

        // Попытка инвалидировать токен на сервере
        if (refreshToken && !skipServerLogout) {
          try {
            // Динамический импорт для избежания circular dependency
            const { default: authService } = await import('../services/authService');
            await authService.logoutFromServer(refreshToken);
          } catch (error) {
            // Fail-safe: логируем ошибку, но продолжаем локальную очистку
            console.error('Server logout failed, proceeding with local cleanup:', error);
          }
        }

        // Локальная очистка ВСЕГДА выполняется (fail-safe)
        localStorage.removeItem('refreshToken');
        deleteCookie('refreshToken');
        deleteCookie('accessToken');
        set({
          accessToken: null,
          user: null,
          isAuthenticated: false,
        });
      },

      getRefreshToken: () => {
        const token = localStorage.getItem('refreshToken');
        // Fix: фильтруем невалидные значения, которые могли попасть ранее
        if (!token || token === 'undefined' || token === 'null' || token.trim() === '') {
          return null;
        }
        return token;
      },
    }),
    { name: 'AuthStore' }
  )
);

const B2B_ROLES: Array<User['role']> = [
  'wholesale_level1',
  'wholesale_level2',
  'wholesale_level3',
  'trainer',
  'federation_rep',
  'admin',
];

export const authSelectors = {
  /**
   * Возвращает актуальный флаг аутентификации пользователя
   */
  useIsAuthenticated: () => useAuthStore(state => state.isAuthenticated),
  /**
   * Возвращает текущего пользователя из стора
   */
  useUser: () => useAuthStore(state => state.user),
  /**
   * Определяет, относится ли пользователь к B2B сегменту
   */
  useIsB2BUser: () =>
    useAuthStore(state => {
      const role = state.user?.role;
      const isVerified = state.user?.is_verified;
      // Story 29.2: Неверифицированные B2B пользователи считаются розничными
      // B2B функционал доступен только при is_verified=true
      return role && B2B_ROLES.includes(role) && isVerified === true;
    }),
};
