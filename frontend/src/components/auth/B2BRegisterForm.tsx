/**
 * B2BRegisterForm Component
 * Story 28.2 - Поток регистрации B2B
 *
 * Форма регистрации B2B пользователей с валидацией ИНН/ОГРН
 *
 * AC 1: B2B Registration Form с корпоративными полями
 * AC 2: Валидация ИНН/ОГРН
 * AC 3: UI/UX отличие от B2C
 * AC 4, 5: Интеграция с API и обработка ошибок
 * AC 6: Обработка статуса "На рассмотрении"
 * AC 8: Accessibility
 */

'use client';

import React, { useState } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { useRouter } from 'next/navigation';
import { Input } from '@/components/ui/Input/Input';
import { PhoneInput } from '@/components/ui/Input/PhoneInput';
import { Button } from '@/components/ui/Button/Button';
import authService from '@/services/authService';
import { isSafeRedirectUrl } from '@/utils/urlUtils';
import { b2bRegisterSchema, type B2BRegisterFormData } from '@/schemas/authSchemas';
import type { RegisterRequest } from '@/types/api';

export interface B2BRegisterFormProps {
  /** Callback после успешной регистрации (optional) */
  onSuccess?: () => void;
  /** URL для редиректа после успешной регистрации */
  redirectUrl?: string;
}

export const B2BRegisterForm: React.FC<B2BRegisterFormProps> = ({ onSuccess, redirectUrl }) => {
  const router = useRouter();
  const [apiError, setApiError] = useState<string | null>(null);
  const [isPending, setIsPending] = useState(false);

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<B2BRegisterFormData>({
    resolver: zodResolver(b2bRegisterSchema),
    defaultValues: {
      role: 'wholesale_level1',
    },
  });

  const onSubmit = async (data: B2BRegisterFormData) => {
    try {
      setApiError(null);

      // AC 4: Формирование payload для B2B регистрации
      const registerData: RegisterRequest = {
        email: data.email,
        password: data.password,
        password_confirm: data.confirmPassword,
        first_name: data.first_name,
        last_name: data.last_name,
        phone: data.phone,
        role: data.role,
        company_name: data.company_name,
        tax_id: data.tax_id,
      };

      // AC 4: Отправка через authService.registerB2B()
      const response = await authService.registerB2B(registerData);

      // CRITICAL FIX: Force token refresh immediately to ensure valid session
      // Initial access token from registration might be restricted/invalid until refresh
      await authService.refreshToken();

      // AC 6: Обработка статуса "На рассмотрении" (is_verified: false)
      if (response.user.is_verified === false) {
        setIsPending(true);
      } else {
        // Callback при успехе
        if (onSuccess) {
          onSuccess();
        }

        // Редирект на главную (корень) если верифицирован сразу
        const targetUrl = isSafeRedirectUrl(redirectUrl) ? redirectUrl! : '/';
        router.push(targetUrl);
      }
    } catch (error: unknown) {
      // AC 5: Обработка ошибок API
      const err = error as {
        response?: { status?: number; data?: Record<string, string[]> & { detail?: string } };
      };

      if (err.response?.status === 409) {
        // AC 5: Специфичная обработка "Компания уже зарегистрирована"
        const companyError = err.response?.data?.company_name?.[0];
        const emailError = err.response?.data?.email?.[0];
        setApiError(companyError || emailError || 'Компания или email уже зарегистрированы');
      } else if (err.response?.status === 400) {
        // Ошибки валидации
        const taxIdError = err.response?.data?.tax_id?.[0];
        const passwordError = err.response?.data?.password?.[0];
        setApiError(taxIdError || passwordError || 'Ошибка валидации данных');
      } else if (err.response?.status === 500) {
        setApiError('Ошибка сервера. Попробуйте позже');
      } else {
        setApiError(err.response?.data?.detail || 'Произошла ошибка при регистрации');
      }
    }
  };

  // AC 6: Отображение статуса "На рассмотрении"
  if (isPending) {
    return (
      <div className="w-full max-w-md mx-auto p-6 space-y-4">
        <div
          className="p-6 rounded-md bg-primary-subtle border border-primary/20"
          role="status"
          aria-live="polite"
        >
          <div className="flex items-start space-x-3">
            <svg
              className="w-6 h-6 text-primary flex-shrink-0 mt-0.5"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
              aria-hidden="true"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"
              />
            </svg>
            <div>
              <h3 className="text-lg font-semibold text-text-primary mb-2">
                Заявка на рассмотрении
              </h3>
              <p className="text-body-m text-text-primary mb-3">
                Ваша заявка на регистрацию в качестве бизнес-партнера успешно отправлена.
              </p>
              <p className="text-body-s text-text-secondary">
                Мы проверим предоставленные данные и свяжемся с вами в течение 1-2 рабочих дней.
                После одобрения заявки вы получите доступ к оптовым ценам.
              </p>
            </div>
          </div>
        </div>

        <Button
          type="button"
          onClick={() => router.push('/')}
          variant="secondary"
          className="w-full"
        >
          На главную
        </Button>
      </div>
    );
  }

  return (
    <form onSubmit={handleSubmit(onSubmit)} className="w-full max-w-md mx-auto p-6 space-y-4">
      {/* AC 5: Отображение API ошибок */}
      {apiError && (
        <div
          className="p-4 rounded-md bg-[var(--color-accent-danger)]/10 border border-[var(--color-accent-danger)]"
          role="alert"
          aria-live="assertive"
        >
          <p className="text-body-s text-[var(--color-accent-danger)]">{apiError}</p>
        </div>
      )}

      {/* AC 3: Информационная панель о B2B регистрации */}
      <div className="p-4 rounded-md bg-primary-subtle border border-primary/20 mb-6">
        <p className="text-body-s text-text-primary font-medium">
          📊 Регистрация для бизнес-партнеров
        </p>
        <p className="text-body-xs text-text-secondary mt-1">
          После проверки реквизитов вы получите доступ к оптовым ценам
        </p>
      </div>

      {/* Контактное лицо */}
      <div className="space-y-4 pb-4 border-b border-gray-200">
        <h3 className="text-body-m font-semibold text-gray-900">Контактное лицо</h3>

        <Input
          label="Имя"
          type="text"
          {...register('first_name')}
          error={errors.first_name?.message}
          disabled={isSubmitting}
          autoComplete="given-name"
          placeholder="Иван"
        />

        <Input
          label="Фамилия"
          type="text"
          {...register('last_name')}
          error={errors.last_name?.message}
          disabled={isSubmitting}
          autoComplete="family-name"
          placeholder="Петров"
        />

        <Input
          label="Электронная почта"
          type="email"
          {...register('email')}
          error={errors.email?.message}
          disabled={isSubmitting}
          autoComplete="email"
          placeholder="company@example.com"
        />

        <PhoneInput
          label="Телефон"
          {...register('phone')}
          error={errors.phone?.message}
          disabled={isSubmitting}
          autoComplete="tel"
          placeholder="+7 (999) 123-45-67"
        />
      </div>

      {/* Реквизиты компании */}
      <div className="space-y-4 pb-4 border-b border-gray-200">
        <h3 className="text-body-m font-semibold text-gray-900">Реквизиты компании</h3>

        <Input
          label="Название компании"
          type="text"
          {...register('company_name')}
          error={errors.company_name?.message}
          disabled={isSubmitting}
          autoComplete="organization"
          placeholder="ООО Спорт"
        />

        <Input
          label="ИНН"
          type="text"
          {...register('tax_id')}
          error={errors.tax_id?.message}
          disabled={isSubmitting}
          placeholder="1234567890"
          helper="10 цифр для юр. лица или 12 для ИП"
        />

        <Input
          label="ОГРН"
          type="text"
          {...register('ogrn')}
          error={errors.ogrn?.message}
          disabled={isSubmitting}
          placeholder="1234567890123"
          helper="13 цифр для юр. лица или 15 для ОГРНИП"
        />

        <Input
          label="Юридический адрес"
          type="text"
          {...register('legal_address')}
          error={errors.legal_address?.message}
          disabled={isSubmitting}
          placeholder="г. Москва, ул. Примерная, д. 1"
        />
      </div>

      {/* Пароль */}
      <div className="space-y-4">
        <h3 className="text-body-m font-semibold text-gray-900">Пароль</h3>

        <Input
          label="Пароль"
          type="password"
          {...register('password')}
          error={errors.password?.message}
          disabled={isSubmitting}
          autoComplete="new-password"
          placeholder="••••••••"
          helper="Минимум 8 символов, 1 цифра и 1 заглавная буква"
        />

        <Input
          label="Подтверждение пароля"
          type="password"
          {...register('confirmPassword')}
          error={errors.confirmPassword?.message}
          disabled={isSubmitting}
          autoComplete="new-password"
          placeholder="••••••••"
        />
      </div>

      {/* Submit Button */}
      <Button type="submit" loading={isSubmitting} disabled={isSubmitting} className="w-full mt-6">
        Отправить заявку
      </Button>
    </form>
  );
};
