/**
 * AuthProvider - Provider для инициализации сессии
 * Story 28.4 - Защищенные маршруты и управление сессиями
 *
 * Функциональность:
 * - Проверяет refresh token при загрузке приложения
 * - Вызывает /auth/me/ для получения данных пользователя
 * - Гидрирует authStore из localStorage
 * - Публикует isInitialized/isLoading через контекст
 *
 * AC 2: Session initialization при монтировании
 *
 * Дети рендерятся сразу, без ожидания инициализации: иначе сервер, где эффекты
 * не выполняются, отдавал бы вместо содержимого любой страницы спиннер. Запросы
 * детей, начатые до восстановления сессии, придерживает apiClient
 * (см. services/authReadyGate). Кому нужен готовый store для отрисовки, ждут
 * isInitialized сами: шапка, AuthGate на /profile/*, checkout.
 */

'use client';

import React, { useLayoutEffect, useMemo, useState, createContext, useContext } from 'react';
import axios from 'axios';
import { useAuthStore } from '@/stores/authStore';
import apiClient, { API_URL_PUBLIC } from '@/services/api-client';
import { holdUntilAuthReady } from '@/services/authReadyGate';
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

  // useLayoutEffect, а не useEffect: все layout-эффекты коммита выполняются раньше
  // passive-эффектов, а дети грузят данные в useEffect. Так ожидание в apiClient
  // включается до их первых запросов, хотя эффекты детей идут раньше родительских.
  useLayoutEffect(() => {
    let release: (() => void) | null = null;

    /**
     * Refresh token из localStorage, а при его отсутствии — из cookie.
     *
     * Источник истины — localStorage; но при первой инициализации после
     * обновления кэша браузера он может быть пуст, тогда как middleware
     * и backend всё ещё видят cookie. В этом случае читаем cookie и
     * зеркалируем его в localStorage, иначе AuthProvider выйдет рано
     * и store останется пустым → Header показывает кнопки входа,
     * а middleware блокирует переход на /login (бесконечный цикл).
     *
     * Заблокированное хранилище бросает на любом обращении — тогда работаем
     * по cookie, а если его нет, как гость.
     */
    function readRefreshToken(): string | null {
      try {
        const stored = getRefreshToken();
        if (stored) return stored;
      } catch (storageError) {
        console.warn('localStorage недоступен при инициализации сессии:', storageError);
      }

      const cookieRefreshToken = readCookie('refreshToken');
      if (cookieRefreshToken) {
        try {
          localStorage.setItem('refreshToken', cookieRefreshToken);
        } catch {
          // Уже предупредили выше: хранилище недоступно, живём на cookie.
        }
      }
      return cookieRefreshToken;
    }

    /**
     * Восстановление сессии с retry logic
     */
    async function restoreSession(refreshToken: string, retries = 3) {
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
          // AC 2.2: Вызов /auth/me/ для получения user данных.
          // skipAuthWait: запросы детей ждут именно этой инициализации.
          const response = await apiClient.get<User>('/users/profile/', { skipAuthWait: true });

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
              return;
            }
          }

          // Сессия успешно восстановлена
          return;
        } catch (error: unknown) {
          const err = error as { response?: { status?: number } };

          // AC 2.4: Logout при 401/403 (токен истек)
          if (err.response?.status === 401 || err.response?.status === 403) {
            console.warn('Session expired:', error);
            logout();
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
          }
        }
      }
    }

    async function initializeAuth() {
      try {
        const refreshToken = readRefreshToken();

        // Нет refresh token - пользователь не залогинен, запросам ждать нечего
        if (!refreshToken) return;

        // Синхронно, до первых запросов детей (см. комментарий к useLayoutEffect)
        release = holdUntilAuthReady();
        await restoreSession(refreshToken);
      } catch (error) {
        // Любое исключение (например, заблокированное хранилище в setTokens)
        // не должно оставить приложение в вечной инициализации — работаем как гость.
        console.warn('Auth initialization failed:', error);
      } finally {
        release?.();
        setIsInitialized(true);
        setIsLoading(false);
      }
    }

    void initializeAuth();
  }, [setUser, setTokens, logout, getRefreshToken]);

  const value = useMemo(() => ({ isInitialized, isLoading }), [isInitialized, isLoading]);

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
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
