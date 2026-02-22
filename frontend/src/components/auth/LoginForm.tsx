/**
 * LoginForm Component
 * Story 28.1 - Базовая аутентификация и регистрация B2C
 *
 * Форма входа с валидацией и интеграцией с authService
 *
 * AC 1: Login Flow с редиректом
 * AC 3: Client-side валидация (Zod)
 * AC 4: Error Handling и Loading States
 * AC 5: Интеграция с authService
 * AC 6: Использование UI компонентов
 * AC 7: Responsive Design
 * AC 10: Accessibility
 */

'use client';

import React, { useState } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { Input } from '@/components/ui/Input/Input';
import { Button } from '@/components/ui/Button/Button';
import authService from '@/services/authService';
import { loginSchema, type LoginFormData } from '@/schemas/authSchemas';

export interface LoginFormProps {
  /** URL для редиректа после успешного входа (optional) */
  redirectUrl?: string;
  /** Callback после успешного входа (optional) */
  onSuccess?: () => void;
}

export const LoginForm: React.FC<LoginFormProps> = ({ redirectUrl, onSuccess }) => {
  const router = useRouter();
  const [apiError, setApiError] = useState<string | null>(null);

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<LoginFormData>({
    resolver: zodResolver(loginSchema),
  });

  const onSubmit = async (data: LoginFormData) => {
    try {
      setApiError(null);

      // AC 5: Используем authService.login()
      await authService.login(data);

      // AC 1: Редирект после успешного входа
      if (onSuccess) {
        onSuccess();
      }

      // Редирект на указанный URL или на главную
      const targetUrl = redirectUrl || '/';
      router.push(targetUrl);
    } catch (error: unknown) {
      // AC 4: Обработка ошибок API
      const err = error as {
        response?: { status?: number; data?: { detail?: string; code?: string } };
      };

      // Epic 29.2: Обработка ошибки pending verification
      if (
        err.response?.status === 403 &&
        err.response?.data?.code === 'account_pending_verification'
      ) {
        setApiError(
          'Ваша учетная запись находится на проверке. Мы свяжемся с вами после завершения верификации.'
        );
      } else if (err.response?.status === 401) {
        setApiError('Неверные учетные данные');
      } else if (err.response?.status === 500) {
        setApiError('Ошибка сервера. Попробуйте позже');
      } else {
        setApiError(err.response?.data?.detail || 'Произошла ошибка');
      }
    }
  };

  return (
    <form onSubmit={handleSubmit(onSubmit)} className="w-full max-w-md mx-auto p-6 space-y-4">
      {/* AC 4: Отображение API ошибок */}
      {apiError && (
        <div
          className="p-4 rounded-sm bg-[var(--color-accent-danger)]/10 border border-[var(--color-accent-danger)]"
          role="alert"
          aria-live="assertive"
        >
          <p className="text-body-s text-[var(--color-accent-danger)]">{apiError}</p>
        </div>
      )}

      {/* AC 6: Использование Input компонента */}
      {/* AC 10: Label с htmlFor, aria-describedby */}
      <Input
        label="Email"
        type="email"
        {...register('email')}
        error={errors.email?.message}
        disabled={isSubmitting}
        autoComplete="email"
        placeholder="user@example.com"
      />

      <Input
        label="Пароль"
        type="password"
        {...register('password')}
        error={errors.password?.message}
        disabled={isSubmitting}
        autoComplete="current-password"
        placeholder="••••••••"
      />

      <div className="flex justify-end">
        <Link
          href="/password-reset"
          className="text-sm text-primary hover:text-primary-hover hover:underline"
        >
          Забыли пароль?
        </Link>
      </div>

      {/* AC 6: Использование Button компонента */}
      {/* AC 4: Loading state с блокировкой кнопки */}
      <Button type="submit" loading={isSubmitting} disabled={isSubmitting} className="w-full">
        Войти
      </Button>
    </form>
  );
};
