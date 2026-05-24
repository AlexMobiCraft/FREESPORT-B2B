/**
 * Password Reset Confirm Form Component
 * Story 28.3 - Восстановление пароля
 *
 * AC 2, 3, 4, 5, 10: Форма подтверждения сброса пароля с валидацией токена
 */

'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import {
  passwordResetConfirmSchema,
  type PasswordResetConfirmFormData,
} from '@/schemas/authSchemas';
import authService from '@/services/authService';
import { Input } from '@/components/ui/Input/Input';
import { Button } from '@/components/ui/Button/Button';
import Link from 'next/link';

interface PasswordResetConfirmFormProps {
  uid: string;
  token: string;
}

/**
 * PasswordResetConfirmForm Component
 *
 * Форма для установки нового пароля после валидации токена.
 * Проверяет валидность токена при монтировании.
 * После успешного сброса делает редирект на страницу логина.
 */
export const PasswordResetConfirmForm = ({ uid, token }: PasswordResetConfirmFormProps) => {
  const router = useRouter();
  const [isValidatingToken, setIsValidatingToken] = useState(true);
  const [tokenError, setTokenError] = useState<string | null>(null);
  const [apiError, setApiError] = useState<string | null>(null);

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<PasswordResetConfirmFormData>({
    resolver: zodResolver(passwordResetConfirmSchema),
  });

  // AC 3: Валидация токена при монтировании компонента
  useEffect(() => {
    const validateToken = async () => {
      try {
        await authService.validateResetToken(uid, token);
        setIsValidatingToken(false);
      } catch (error: unknown) {
        const err = error as { response?: { status?: number } };
        console.error('Token validation error:', error);

        if (err.response?.status === 410) {
          setTokenError(
            'Срок действия ссылки истёк. Пожалуйста, запросите новую ссылку для сброса пароля.'
          );
        } else if (err.response?.status === 404) {
          setTokenError('Недействительная ссылка для сброса пароля.');
        } else {
          setTokenError('Произошла ошибка при проверке ссылки.');
        }

        setIsValidatingToken(false);
      }
    };

    validateToken();
  }, [uid, token]);

  const onSubmit = async (data: PasswordResetConfirmFormData) => {
    try {
      setApiError(null);
      await authService.confirmPasswordReset(uid, token, data.password);

      // AC 2: Редирект на /login с toast сообщением
      // Security Note: Используем replace() чтобы URL с токеном не сохранился в history
      router.replace('/login?reset=success');
    } catch (error: unknown) {
      const err = error as { response?: { status?: number; data?: { new_password?: string[] } } };
      console.error('Password reset confirm error:', error);

      if (err.response?.status === 410) {
        setApiError('Срок действия ссылки истёк. Пожалуйста, запросите новую ссылку.');
      } else if (err.response?.status === 404) {
        setApiError('Недействительная ссылка для сброса пароля.');
      } else if (err.response?.status === 400) {
        const validationErrors = err.response?.data?.new_password;
        if (validationErrors && Array.isArray(validationErrors)) {
          setApiError(validationErrors.join(' '));
        } else {
          setApiError('Пароль не соответствует требованиям безопасности.');
        }
      } else {
        setApiError('Произошла ошибка. Попробуйте позже.');
      }
    }
  };

  // Loading state - проверка токена
  if (isValidatingToken) {
    return (
      <div className="text-center p-6 space-y-4">
        <div
          className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary mx-auto"
          aria-hidden="true"
        />
        <p className="text-gray-600">Проверка ссылки...</p>
      </div>
    );
  }

  // Error state - невалидный или истёкший токен
  if (tokenError) {
    return (
      <div className="text-center p-6 space-y-4">
        <div className="text-red-600 text-4xl mb-4" aria-hidden="true">
          ✕
        </div>
        <h2 className="text-xl font-semibold text-gray-900">Ошибка сброса пароля</h2>
        <p className="text-gray-600 max-w-md mx-auto">{tokenError}</p>
        <Link
          href="/password-reset"
          className="inline-block mt-4 text-primary hover:text-primary-hover underline"
        >
          Запросить новую ссылку
        </Link>
      </div>
    );
  }

  // Main form
  return (
    <form onSubmit={handleSubmit(onSubmit)} className="space-y-6" noValidate>
      {/* Password Input */}
      <div>
        <Input
          label="Новый пароль"
          type="password"
          {...register('password')}
          error={errors.password?.message}
          aria-describedby={errors.password ? 'password-error' : undefined}
          aria-required="true"
          placeholder="Минимум 8 символов"
          autoComplete="new-password"
          disabled={isSubmitting}
        />
        {errors.password && (
          <p id="password-error" className="mt-1 text-sm text-red-600" role="alert">
            {errors.password.message}
          </p>
        )}
        <p className="mt-2 text-xs text-gray-500">
          Пароль должен содержать минимум 8 символов, включая 1 цифру и 1 заглавную букву
        </p>
      </div>

      {/* Confirm Password Input */}
      <div>
        <Input
          label="Подтверждение пароля"
          type="password"
          {...register('confirmPassword')}
          error={errors.confirmPassword?.message}
          aria-describedby={errors.confirmPassword ? 'confirm-password-error' : undefined}
          aria-required="true"
          placeholder="Повторите пароль"
          autoComplete="new-password"
          disabled={isSubmitting}
        />
        {errors.confirmPassword && (
          <p id="confirm-password-error" className="mt-1 text-sm text-red-600" role="alert">
            {errors.confirmPassword.message}
          </p>
        )}
      </div>

      {/* API Error Message */}
      {apiError && (
        <div
          className="p-4 bg-red-50 border border-red-200 rounded-md text-red-600 text-sm"
          role="alert"
        >
          {apiError}
        </div>
      )}

      {/* Submit Button */}
      <Button
        type="submit"
        loading={isSubmitting}
        disabled={isSubmitting}
        className="w-full"
        aria-label="Сбросить пароль"
      >
        {isSubmitting ? 'Сброс пароля...' : 'Сбросить пароль'}
      </Button>
    </form>
  );
};
