/**
 * Portal Link Confirm Form Component
 *
 * Подтверждение привязки 1С-клиента к регистрации на портале (email формы
 * отличался от email в 1С) — пользователь переходит по ссылке из письма
 * и задаёт пароль для найденной 1С-записи.
 *
 * В отличие от сброса пароля здесь нет отдельного эндпоинта валидации
 * токена — проверка и применение происходят одним запросом при отправке
 * формы (см. backend PortalLinkConfirmView).
 */

'use client';

import { useState } from 'react';
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

interface PortalLinkConfirmFormProps {
  token: string;
}

export const PortalLinkConfirmForm = ({ token }: PortalLinkConfirmFormProps) => {
  const router = useRouter();
  const [apiError, setApiError] = useState<string | null>(null);
  const [isDone, setIsDone] = useState(false);

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<PasswordResetConfirmFormData>({
    resolver: zodResolver(passwordResetConfirmSchema),
  });

  const onSubmit = async (data: PasswordResetConfirmFormData) => {
    try {
      setApiError(null);
      await authService.confirmPortalLink(token, data.password, data.confirmPassword);
      setIsDone(true);
    } catch (error: unknown) {
      const err = error as { response?: { status?: number } };
      console.error('Portal link confirm error:', error);

      if (err.response?.status === 410) {
        setApiError(
          'Срок действия ссылки истёк или она уже была использована. Зарегистрируйтесь заново, чтобы получить новую ссылку.'
        );
      } else if (err.response?.status === 404) {
        setApiError('Недействительная ссылка подтверждения.');
      } else if (err.response?.status === 409) {
        setApiError('Этот email уже используется другим аккаунтом.');
      } else if (err.response?.status === 400) {
        setApiError('Пароль не соответствует требованиям безопасности.');
      } else {
        setApiError('Произошла ошибка. Попробуйте позже.');
      }
    }
  };

  // Success state
  if (isDone) {
    return (
      <div className="text-center p-6 space-y-4">
        <div className="text-primary text-4xl mb-4" aria-hidden="true">
          ✓
        </div>
        <h2 className="text-xl font-semibold text-gray-900">Заявка отправлена</h2>
        <p className="text-gray-600 max-w-md mx-auto">
          Пароль установлен, аккаунт привязан к записи в 1С и передан на верификацию администратору.
          Мы свяжемся с вами после проверки.
        </p>
        <Button type="button" onClick={() => router.push('/login')} className="mt-4">
          На страницу входа
        </Button>
      </div>
    );
  }

  // Error state — недействительный/истёкший токен, обнаруживается только при отправке
  if (apiError) {
    return (
      <div className="text-center p-6 space-y-4">
        <div className="text-red-600 text-4xl mb-4" aria-hidden="true">
          ✕
        </div>
        <h2 className="text-xl font-semibold text-gray-900">Не удалось подтвердить привязку</h2>
        <p className="text-gray-600 max-w-md mx-auto">{apiError}</p>
        <Link
          href="/b2b-register"
          className="inline-block mt-4 text-primary hover:text-primary-hover underline"
        >
          Вернуться к регистрации
        </Link>
      </div>
    );
  }

  // Main form
  return (
    <form onSubmit={handleSubmit(onSubmit)} className="space-y-6" noValidate>
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

      <Button
        type="submit"
        loading={isSubmitting}
        disabled={isSubmitting}
        className="w-full"
        aria-label="Подтвердить привязку"
      >
        {isSubmitting ? 'Подтверждение...' : 'Подтвердить и установить пароль'}
      </Button>
    </form>
  );
};
