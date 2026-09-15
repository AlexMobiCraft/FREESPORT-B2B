/**
 * AuthProvider - Provider для инициализации сессии
 * Story 28.4 - Защищенные маршруты и управление сессиями
 *
 * Функциональность:
 * - Проверяет refresh token при загрузке приложения
 * - Вызывает /auth/me/ для получения данных пользователя
 * - Гидрирует authStore из localStorage
 * - Показывает loading state до завершения инициализации
 *
 * AC 2: Session initialization при монтировании
 */

'use client';

import React, { useEffect, useState, createContext, useContext } from 'react';
import axios from 'axios';
import { useAuthStore } from '@/stores/authStore';
import apiClient, { API_URL_PUBLIC } from '@/services/api-client';
import type { User } from '@/types/api';

/**
 * Читает значение cookie по имени (только в браузере).
 */
function readCookie(name: string): string | null {
  if (typeof document === 'undefined') return null;
  const match = document.cookie.match(new RegExp('(^|; )' + name + '=([^;]+)'));
  return match ? decodeURIComponent(match[2]) : null;
}

interface AuthContextValue {
  /** Флаг завершения инициализации */
  isInitialized: boolean;
  /** Флаг загрузки */
  isLoading: boolean;
}

const AuthContext = createContext<AuthContextValue>({
  isInitialized: false,
  isLoading: true,
});

interface AuthProviderProps {
  children: React.ReactNode;
}

/**
 * AuthProvider - гидрирует auth state при загрузке приложения
 */
export function AuthProvider({ children }: AuthProviderProps) {
  const [isInitialized, setIsInitialized] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const { setUser, setTokens, logout, getRefreshToken } = useAuthStore();

  useEffect(() => {
    /**
     * Инициализация сессии с retry logic
     */
    async function initializeAuth(retries = 3) {
      // Источник истины — localStorage; но при первой инициализации после
      // обновления кэша браузера он может быть пуст, тогда как middleware
      // и backend всё ещё видят cookie. В этом случае читаем cookie и
      // зеркалируем его в localStorage, иначе AuthProvider выйдет рано
      // и store останется пустым → Header показывает кнопки входа,
      // а middleware блокирует переход на /login (бесконечный цикл).
      let refreshToken = getRefreshToken();
      if (!refreshToken) {
        const cookieRefreshToken = readCookie('refreshToken');
        if (cookieRefreshToken) {
          localStorage.setItem('refreshToken', cookieRefreshToken);
          refreshToken = cookieRefreshToken;
        }
      }

      // Нет refresh token - пользователь не залогинен
      if (!refreshToken) {
        setIsLoading(false);
        setIsInitialized(true);
        return;
      }

      // Гидрируем accessToken из cookie ДО запроса профиля, чтобы axios
      // мог отправить Authorization-заголовок и не зависеть от Django session.
      // Если cookie нет, явный refresh ниже синхронизирует store.
      const cookieAccessToken = readCookie('accessToken');
      if (cookieAccessToken) {
        setTokens(cookieAccessToken, refreshToken);
      }

      // Попытка восстановить сессию
      for (let attempt = 0; attempt < retries; attempt++) {
        try {
          // AC 2.2: Вызов /auth/me/ для получения user данных
          const response = await apiClient.get<User>('/users/profile/');

          // AC 2.3: Обновляем authStore при успехе
          setUser(response.data);

          // Если accessToken cookie не было (сценарий когда профиль ответил
          // через Django SessionAuthentication), store всё ещё с
          // isAuthenticated=false. Делаем явный refresh, чтобы получить
          // свежий access token и установить isAuthenticated=true.
          if (!cookieAccessToken) {
            try {
              // Используем raw axios (без interceptors), чтобы не словить
              // рекурсивный 401 → refresh → retry того же /auth/refresh/.
              const { data } = await axios.post<{ access: string; refresh?: string }>(
                `${API_URL_PUBLIC}/auth/refresh/`,
                { refresh: refreshToken },
                { withCredentials: true }
              );
              const newRefresh = data.refresh || refreshToken;
              setTokens(data.access, newRefresh);
            } catch (refreshErr) {
              // Если refresh упал — выходим, чтобы показать гостевой UI вместо
              // зависшего состояния "залогинен по cookie, но store пустой".
              console.warn('Failed to refresh tokens during init:', refreshErr);
              logout(true);
              setIsInitialized(true);
              setIsLoading(false);
              return;
            }
          }

          // Сессия успешно восстановлена
          setIsInitialized(true);
          setIsLoading(false);
          return;
        } catch (error: unknown) {
          const err = error as { response?: { status?: number } };

          // AC 2.4: Logout при 401/403 (токен истек)
          if (err.response?.status === 401 || err.response?.status === 403) {
            console.warn('Session expired:', error);
            logout();
            setIsInitialized(true);
            setIsLoading(false);
            return;
          }

          // Network error - retry с exponential backoff
          if (attempt < retries - 1) {
            const delay = Math.pow(2, attempt) * 1000; // 1s, 2s, 4s
            console.warn(
              `Auth initialization failed (attempt ${attempt + 1}/${retries}), retrying in ${delay}ms...`
            );
            await new Promise(resolve => setTimeout(resolve, delay));
          } else {
            // Все попытки исчерпаны (сетевая ошибка, не 401/403)
            // НЕ вызываем logout() - сохраняем токены для повторных попыток,
            // чтобы временная недоступность бэкенда не приводила к потере сессии
            console.warn('Auth initialization failed after retries (network error):', error);
            setIsInitialized(true);
            setIsLoading(false);
          }
        }
      }
    }

    initializeAuth();
  }, [setUser, setTokens, logout, getRefreshToken]);

  // AC 6.1: Loading state до завершения инициализации
  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-[var(--color-neutral-100)]">
        <div className="flex flex-col items-center gap-4">
          <div className="animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-primary"></div>
          <p className="text-body-m text-[var(--color-text-muted)]">Загрузка...</p>
        </div>
      </div>
    );
  }

  return (
    <AuthContext.Provider value={{ isInitialized, isLoading }}>{children}</AuthContext.Provider>
  );
}

/**
 * useAuth hook - доступ к auth context
 */
export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within AuthProvider');
  }
  return context;
};
