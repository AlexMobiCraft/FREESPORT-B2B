/**
 * Password Reset Request Form Component
 * Story 28.3 - Восстановление пароля
 *
 * AC 1, 4, 5, 10: Форма запроса на сброс пароля с валидацией
 */

'use client';

import { useState } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import {
  passwordResetRequestSchema,
  type PasswordResetRequestFormData,
} from '@/schemas/authSchemas';
import authService from '@/services/authService';
import { Input } from '@/components/ui/Input/Input';
import { Button } from '@/components/ui/Button/Button';

/**
 * PasswordResetRequestForm Component
 *
 * Форма для запроса на сброс пароля.
 * После успешной отправки показывает сообщение о том, что email отправлен.
 */
export const PasswordResetRequestForm = () => {
  const [isSubmitted, setIsSubmitted] = useState(false);
  const [apiError, setApiError] = useState<string | null>(null);

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<PasswordResetRequestFormData>({
    resolver: zodResolver(passwordResetRequestSchema),
  });

  const onSubmit = async (data: PasswordResetRequestFormData) => {
    try {
      setApiError(null);
      await authService.requestPasswordReset(data.email);
      setIsSubmitted(true);
    } catch (error) {
      console.error('Password reset request error:', error);
      setApiError('Произошла ошибка. Попробуйте позже.');
    }
  };

  // Success state - показываем сообщение после отправки
  if (isSubmitted) {
    return (
      <div className="text-center p-6 space-y-4">
        <div className="text-green-600 text-4xl mb-4" aria-hidden="true">
          ✓
        </div>
        <h2 className="text-xl font-semibold text-gray-900">Проверьте вашу почту</h2>
        <p className="text-gray-600 max-w-md mx-auto">
          Если аккаунт с указанным email существует, мы отправили ссылку для сброса пароля.
          Проверьте папку «Входящие» и «Спам».
        </p>
      </div>
    );
  }

  return (
    <form onSubmit={handleSubmit(onSubmit)} className="space-y-6" noValidate>
      {/* Email Input */}
      <div>
        <Input
          label="Email"
          type="email"
          {...register('email')}
          error={errors.email?.message}
          aria-describedby={errors.email ? 'email-error' : undefined}
          aria-required="true"
          placeholder="example@email.com"
          autoComplete="email"
          disabled={isSubmitting}
        />
        {errors.email && (
          <p id="email-error" className="mt-1 text-sm text-red-600" role="alert">
            {errors.email.message}
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
        aria-label="Отправить ссылку для сброса пароля"
      >
        {isSubmitting ? 'Отправка...' : 'Отправить ссылку для сброса'}
      </Button>
    </form>
  );
};
