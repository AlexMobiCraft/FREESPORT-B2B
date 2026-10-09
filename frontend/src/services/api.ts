/**
 * API клиент для взаимодействия с Django backend
 * Настройка Axios с JWT токенами и обработкой ошибок
 */
import axios from 'axios';
import type { AuthTokens, ApiResponse } from '@/types';

// Конфигурация API
const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8001/api/v1';

// Создание Axios инстанса
export const apiClient = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Управление токенами в localStorage
export const tokenStorage = {
  get(): AuthTokens | null {
    if (typeof window === 'undefined') return null;

    const accessToken = localStorage.getItem('access_token');
    const refreshToken = localStorage.getItem('refresh_token');

    if (accessToken && refreshToken) {
      return {
        access: accessToken,
        refresh: refreshToken,
      };
    }

    return null;
  },

  set(tokens: AuthTokens): void {
    if (typeof window === 'undefined') return;

    localStorage.setItem('access_token', tokens.access);
    localStorage.setItem('refresh_token', tokens.refresh);
  },

  clear(): void {
    if (typeof window === 'undefined') return;

    localStorage.removeItem('access_token');
    localStorage.removeItem('refresh_token');
  },
};

// Request interceptor для добавления JWT токена
apiClient.interceptors.request.use(
  config => {
    const tokens = tokenStorage.get();

    if (tokens?.access) {
      config.headers = config.headers || {};
      config.headers.Authorization = `Bearer ${tokens.access}`;
    }

    return config;
  },
  error => {
    return Promise.reject(error);
  }
);

// Response interceptor для обработки ошибок и обновления токенов
apiClient.interceptors.response.use(
  response => {
    return response;
  },
  async error => {
    const originalRequest = error.config;

    // Если получили 401 и это не повторный запрос
    if (error.response?.status === 401 && !originalRequest._retry) {
      originalRequest._retry = true;

      const tokens = tokenStorage.get();

      if (tokens?.refresh) {
        try {
          // Попытка обновить access token
          const response = await axios.post(`${API_BASE_URL}/auth/token/refresh/`, {
            refresh: tokens.refresh,
          });

          const newTokens = response.data as AuthTokens;
          tokenStorage.set(newTokens);

          // Повторить оригинальный запрос с новым токеном
          originalRequest.headers = originalRequest.headers || {};
          originalRequest.headers.Authorization = `Bearer ${newTokens.access}`;
          return apiClient(originalRequest);
        } catch (refreshError) {
          // Refresh токен недействителен, очищаем и перенаправляем на логин
          tokenStorage.clear();

          if (typeof window !== 'undefined') {
            window.location.href = '/login';
          }

          return Promise.reject(refreshError);
        }
      }
    }

    return Promise.reject(error);
  }
);

// Типизированные API методы
export const api = {
  // GET запрос
  async get<T>(url: string): Promise<ApiResponse<T>> {
    try {
      const response = await apiClient.get<ApiResponse<T>>(url);
      return response.data;
    } catch (error) {
      throw this.handleError(error);
    }
  },

  // POST запрос
  async post<T>(url: string, data?: unknown): Promise<ApiResponse<T>> {
    try {
      const response = await apiClient.post<ApiResponse<T>>(url, data);
      return response.data;
    } catch (error) {
      throw this.handleError(error);
    }
  },

  // PUT запрос
  async put<T>(url: string, data?: unknown): Promise<ApiResponse<T>> {
    try {
      const response = await apiClient.put<ApiResponse<T>>(url, data);
      return response.data;
    } catch (error) {
      throw this.handleError(error);
    }
  },

  // DELETE запрос
  async delete<T>(url: string): Promise<ApiResponse<T>> {
    try {
      const response = await apiClient.delete<ApiResponse<T>>(url);
      return response.data;
    } catch (error) {
      throw this.handleError(error);
    }
  },

  // Обработка ошибок
  handleError(error: unknown): Error {
    const axiosError = error as {
      response?: {
        data?: { message?: string; errors?: Record<string, string[]> };
      };
      message?: string;
    };

    if (axiosError.response?.data?.message) {
      return new Error(axiosError.response.data.message);
    }

    if (axiosError.response?.data?.errors) {
      const firstError = Object.values(axiosError.response.data.errors)[0];
      if (Array.isArray(firstError) && firstError.length > 0) {
        return new Error(firstError[0]);
      }
    }

    return new Error(axiosError.message || 'Произошла неизвестная ошибка');
  },
};
