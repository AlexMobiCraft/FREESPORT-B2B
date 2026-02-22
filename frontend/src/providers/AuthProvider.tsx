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
import { useAuthStore } from '@/stores/authStore';
import apiClient from '@/services/api-client';
import type { User } from '@/types/api';

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
  const { setUser, logout, getRefreshToken } = useAuthStore();

  useEffect(() => {
    /**
     * Инициализация сессии с retry logic
     */
    async function initializeAuth(retries = 3) {
      const refreshToken = getRefreshToken();

      // Нет refresh token - пользователь не залогинен
      if (!refreshToken) {
        setIsLoading(false);
        setIsInitialized(true);
        return;
      }

      // Попытка восстановить сессию
      for (let attempt = 0; attempt < retries; attempt++) {
        try {
          // AC 2.2: Вызов /auth/me/ для получения user данных
          const response = await apiClient.get<User>('/users/profile/');

          // AC 2.3: Обновляем authStore при успехе
          setUser(response.data);

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
            // Все попытки исчерпаны - logout
            console.warn('Auth initialization failed after retries:', error);
            logout();
            setIsInitialized(true);
            setIsLoading(false);
          }
        }
      }
    }

    initializeAuth();
  }, [setUser, logout, getRefreshToken]);

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
