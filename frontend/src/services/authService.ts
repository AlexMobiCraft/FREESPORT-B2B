/**
 * Auth Service - методы для аутентификации
 *
 * Обрабатывает login, register, logout, refreshToken
 * Story 28.2: Добавлен метод registerB2B для регистрации B2B пользователей
 */

import apiClient from './api-client';
import { useAuthStore } from '@/stores/authStore';
import type {
  LoginRequest,
  LoginResponse,
  PasswordResetConfirmRequest,
  PasswordResetConfirmResponse,
  PasswordResetRequest,
  PasswordResetResponse,
  RefreshTokenResponse,
  RegisterRequest,
  RegisterResponse,
  ValidateTokenRequest,
  ValidateTokenResponse,
} from '@/types/api';

class AuthService {
  /**
   * Авторизация пользователя
   */
  async login(credentials: LoginRequest): Promise<LoginResponse> {
    const response = await apiClient.post<LoginResponse>('/auth/login/', credentials);

    const { access, refresh, user } = response.data;

    // Сохранить tokens в store
    useAuthStore.getState().setTokens(access, refresh);
    useAuthStore.getState().setUser(user);

    return response.data;
  }

  /**
   * Регистрация нового пользователя (B2C)
   */
  async register(userData: RegisterRequest): Promise<RegisterResponse> {
    const response = await apiClient.post<RegisterResponse>('/auth/register/', userData);

    const { access, refresh, user } = response.data;

    // Сохранить tokens в store только если они пришли (Story 32.1 fix: avoid undefined tokens)
    if (access && refresh) {
      useAuthStore.getState().setTokens(access, refresh);
    }

    useAuthStore.getState().setUser(user);

    return response.data;
  }

  /**
   * Регистрация B2B пользователя (бизнес-партнер)
   * Story 28.2 - AC 4: Интеграция с Backend API
   *
   * @param userData - данные для регистрации B2B пользователя
   * @returns Promise с данными зарегистрированного пользователя и токенами
   *
   * Отличия от B2C:
   * - Обязательные поля: company_name, tax_id
   * - User может иметь is_verified: false (требуется модерация)
   * - Не происходит автоматический редирект (обрабатывается в компоненте)
   */
  async registerB2B(userData: RegisterRequest): Promise<RegisterResponse> {
    const response = await apiClient.post<RegisterResponse>('/auth/register/', userData);

    const { access, refresh, user } = response.data;

    // Story 28.2 - AC 6: Сохранение токенов если они сгенерированы (только для активных юзеров)
    // Story 32.1 fix: Для pending B2B юзеров токены не приходят, избегаем 'undefined' в store
    if (access && refresh) {
      useAuthStore.getState().setTokens(access, refresh);
    }

    useAuthStore.getState().setUser(user);

    return response.data;
  }

  /**
   * Выход из системы (локальный)
   * @deprecated Используйте logoutFromServer() + authStore.logout()
   */
  async logout(): Promise<void> {
    await useAuthStore.getState().logout();
  }

  /**
   * Инвалидация refresh токена на сервере
   * Story 31.2 - AC 1-4, 7: Отправка POST на /auth/logout/ для инвалидации токена
   *
   * @param refreshToken - refresh token для инвалидации
   * @returns Promise<void> - resolves даже при ошибках (fail-safe)
   */
  async logoutFromServer(refreshToken: string): Promise<void> {
    try {
      await apiClient.post('/auth/logout/', { refresh: refreshToken });
    } catch (error) {
      // Fail-safe: логируем, но не прерываем локальный logout
      console.error('Logout API request failed:', error);
    }
  }

  /**
   * Обновление access token через refresh token
   * (обычно вызывается автоматически через api-client interceptor)
   */
  async refreshToken(): Promise<RefreshTokenResponse> {
    const refreshToken = useAuthStore.getState().getRefreshToken();

    if (!refreshToken) {
      throw new Error('No refresh token available');
    }

    const response = await apiClient.post<RefreshTokenResponse>('/auth/refresh/', {
      refresh: refreshToken,
    });

    const { access } = response.data;

    // Обновить access token в store
    useAuthStore.getState().setTokens(access, refreshToken);

    return response.data;
  }

  /**
   * Запрос на сброс пароля
   * Story 28.3 - AC 1, 6: Отправка email для сброса пароля
   *
   * @param email - email пользователя
   * @returns Promise с сообщением о результате
   *
   * Security Note: Всегда возвращает 200 OK, даже если email не существует
   */
  async requestPasswordReset(email: string): Promise<PasswordResetResponse> {
    const response = await apiClient.post<PasswordResetResponse>('/auth/password-reset/', {
      email,
    } as PasswordResetRequest);

    return response.data;
  }

  /**
   * Валидация токена сброса пароля
   * Story 28.3 - AC 3: Проверка валидности токена перед сбросом
   *
   * @param uid - base64 encoded user ID
   * @param token - одноразовый токен
   * @returns Promise с результатом валидации
   * @throws {Error} 404 - Invalid token, 410 - Token expired
   */
  async validateResetToken(uid: string, token: string): Promise<ValidateTokenResponse> {
    const response = await apiClient.post<ValidateTokenResponse>(
      '/auth/password-reset/validate-token/',
      { uid, token } as ValidateTokenRequest
    );

    return response.data;
  }

  /**
   * Подтверждение сброса пароля с новым паролем
   * Story 28.3 - AC 2, 6: Установка нового пароля
   *
   * @param uid - base64 encoded user ID
   * @param token - одноразовый токен
   * @param password - новый пароль
   * @returns Promise с сообщением об успешном сбросе
   * @throws {Error} 400 - Validation errors, 404 - Invalid token, 410 - Token expired
   */
  async confirmPasswordReset(
    uid: string,
    token: string,
    password: string
  ): Promise<PasswordResetConfirmResponse> {
    const response = await apiClient.post<PasswordResetConfirmResponse>(
      '/auth/password-reset/confirm/',
      {
        uid,
        token,
        new_password: password,
      } as PasswordResetConfirmRequest
    );

    return response.data;
  }
}

const authService = new AuthService();
export default authService;
