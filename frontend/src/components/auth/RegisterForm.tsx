/**
 * RegisterForm Component
 * Story 28.1 - Базовая аутентификация и регистрация B2C
 * Story 29.1 - Role Selection UI & Warnings
 *
 * Форма регистрации с выбором роли и условными B2B полями
 *
 * Story 28.1 AC 2: B2C Registration Flow с автологином
 * Story 28.1 AC 3: Client-side валидация (Zod)
 * Story 28.1 AC 4: Error Handling и Loading States
 * Story 28.1 AC 5: Интеграция с authService
 * Story 28.1 AC 6: Использование UI компонентов
 * Story 28.1 AC 7: Responsive Design
 * Story 28.1 AC 10: Accessibility
 *
 * Story 29.1 AC 1: Поле выбора роли с 4 опциями
 * Story 29.1 AC 2: Retail выбран по умолчанию
 * Story 29.1 AC 3: InfoPanel для B2B ролей
 * Story 29.1 AC 4: Передача роли в API
 * Story 29.1 AC 5, 6: Accessibility
 * Story 29.1 AC 8: Условные B2B поля
 */

'use client';

import React, { useState } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { Input } from '@/components/ui/Input/Input';
import { Button } from '@/components/ui/Button/Button';
import { Checkbox } from '@/components/ui/Checkbox/Checkbox';
import { RoleInfoPanel } from '@/components/auth/RoleInfoPanel';
import authService from '@/services/authService';
import { isSafeRedirectUrl } from '@/utils/urlUtils';
import {
  registerSchema,
  type RegisterFormData,
  type RegisterFormInput,
} from '@/schemas/authSchemas';
import type { RegisterRequest } from '@/types/api';
import {
  applyBackendFieldErrors,
  getFirstValidationMessage,
  getValidationMessage,
  type ApiErrorData,
  type BackendFieldErrorMap,
} from '@/utils/validationErrorParser';

// Story 29.1 AC 1: Константа с опциями ролей
const ROLE_OPTIONS = [
  { value: 'retail' as const, label: 'Розничный покупатель' },
  { value: 'trainer' as const, label: 'Тренер / Спортивный клуб' },
  { value: 'wholesale_level1' as const, label: 'Оптовик' },
  { value: 'federation_rep' as const, label: 'Представитель спортивной федерации' },
] as const;

const REGISTER_FIELD_ERROR_MAP = {
  email: 'email',
  password: 'password',
  password_confirm: 'confirmPassword',
  first_name: 'first_name',
  role: 'role',
  company_name: 'company_name',
  tax_id: 'tax_id',
  pdp_consent: 'pdp_consent',
} satisfies BackendFieldErrorMap<RegisterFormInput>;

export interface RegisterFormProps {
  /** Callback после успешной регистрации (optional) */
  onSuccess?: () => void;
  /** URL для редиректа после успешной регистрации */
  redirectUrl?: string;
}

export const RegisterForm: React.FC<RegisterFormProps> = ({ onSuccess, redirectUrl }) => {
  const router = useRouter();
  const [apiError, setApiError] = useState<string | null>(null);

  const {
    register,
    handleSubmit,
    watch,
    setError,
    formState: { errors, isSubmitting },
  } = useForm<RegisterFormInput, unknown, RegisterFormData>({
    resolver: zodResolver(registerSchema),
    // Story 29.1 AC 2: Retail роль по умолчанию
    defaultValues: {
      role: 'retail',
      pdp_consent: false,
      marketing_consent: false,
    },
  });

  // Story 29.1: Отслеживаем выбранную роль для условной логики
  const selectedRole = watch('role') ?? 'retail';
  const hasPdpConsentError = Boolean(errors.pdp_consent?.message);

  const onSubmit = async (data: RegisterFormData) => {
    try {
      setApiError(null);

      // Story 28.1 AC 5: Используем authService.register()
      // Story 29.1 AC 4: Передаём выбранную роль и условные B2B поля
      const registerData: RegisterRequest = {
        email: data.email,
        password: data.password,
        password_confirm: data.confirmPassword,
        first_name: data.first_name,
        last_name: '', // B2C registration может не требовать фамилию
        phone: '', // B2C может не требовать телефон при регистрации
        role: data.role ?? 'retail', // Story 29.1 AC 4: Используем выбранную роль
        // Story 29.1 AC 8: Условные B2B поля
        company_name: data.company_name,
        tax_id: data.tax_id,
        pdp_consent: data.pdp_consent,
        marketing_consent: data.marketing_consent ?? false,
      };

      // AC 2: Автоматический вход после регистрации
      await authService.register(registerData);

      // Callback при успехе
      if (onSuccess) {
        onSuccess();
      }

      // Story 28.1 AC 2: Редирект на главную (или redirectUrl) после успешной регистрации
      // Security: Validate redirectUrl to prevent open redirects
      const targetUrl = isSafeRedirectUrl(redirectUrl) ? redirectUrl! : '/';
      router.push(targetUrl);
    } catch (error: unknown) {
      // AC 4: Обработка ошибок API
      const err = error as {
        response?: {
          status?: number;
          data?: ApiErrorData;
        };
      };
      const responseData = err.response?.data || {};
      const firstFieldError = applyBackendFieldErrors(
        responseData,
        setError,
        REGISTER_FIELD_ERROR_MAP
      );

      if (err.response?.status === 409) {
        // Конфликт - пользователь уже существует
        const emailError = getValidationMessage(responseData.email);
        setApiError(emailError || 'Пользователь с таким email уже существует');
      } else if (err.response?.status === 400) {
        // Ошибки валидации
        const errorMessage = firstFieldError || getFirstValidationMessage(responseData);
        setApiError(errorMessage || 'Ошибка валидации данных');
      } else if (err.response?.status === 500) {
        setApiError('Ошибка сервера. Попробуйте позже');
      } else {
        setApiError(
          getValidationMessage(responseData.detail) || 'Произошла ошибка при регистрации'
        );
      }
    }
  };

  // Story 29.1 AC 3: Проверяем, выбрана ли B2B роль
  const isB2BRole = selectedRole !== 'retail';
  // Story 29.1 AC 8: Определяем, нужно ли поле ИНН
  const requiresTaxId = selectedRole === 'wholesale_level1' || selectedRole === 'federation_rep';

  return (
    <form onSubmit={handleSubmit(onSubmit)} className="w-full max-w-md mx-auto p-6 space-y-4">
      {/* Story 28.1 AC 4: Отображение API ошибок */}
      {apiError && (
        <div
          className="p-4 rounded-sm bg-[var(--color-accent-danger)]/10 border border-[var(--color-accent-danger)]"
          role="alert"
          aria-live="assertive"
        >
          <p className="text-body-s text-[var(--color-accent-danger)]">{apiError}</p>
        </div>
      )}

      {/* Story 28.1 AC 6: Использование Input компонента */}
      {/* Story 28.1 AC 10: Label с htmlFor, aria-describedby */}
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
        label="Электронная почта"
        type="email"
        {...register('email')}
        error={errors.email?.message}
        disabled={isSubmitting}
        autoComplete="email"
        placeholder="user@example.com"
      />

      {/* Story 29.1 AC 1, 2, 5: Role Selector с accessibility */}
      <div className="space-y-2">
        <label htmlFor="role-select" className="block text-body-s font-medium text-gray-700">
          Тип аккаунта
        </label>
        <select
          id="role-select"
          {...register('role')}
          disabled={isSubmitting}
          aria-label="Выберите тип аккаунта"
          className="w-full px-3 py-2 border border-gray-300 rounded-sm shadow-sm focus:ring-2 focus:ring-[var(--color-primary-500)] focus:ring-offset-2 focus:outline-none disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {ROLE_OPTIONS.map(option => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>
        {errors.role?.message && (
          <p className="text-body-xs text-[var(--color-accent-danger)]" role="alert">
            {errors.role.message}
          </p>
        )}
      </div>

      {/* Story 29.1 AC 3, 6: RoleInfoPanel для B2B ролей */}
      <RoleInfoPanel visible={isB2BRole} />

      {/* Story 29.1 AC 8: Условные B2B поля - company_name */}
      {isB2BRole && (
        <Input
          label="Название компании"
          type="text"
          {...register('company_name')}
          error={errors.company_name?.message}
          disabled={isSubmitting}
          autoComplete="organization"
          placeholder="ООО «Спортмастер»"
          required
        />
      )}

      {/* Story 29.1 AC 8: Условные B2B поля - tax_id для wholesale и federation_rep */}
      {requiresTaxId && (
        <Input
          label="ИНН"
          type="text"
          {...register('tax_id')}
          error={errors.tax_id?.message}
          disabled={isSubmitting}
          placeholder="1234567890 или 123456789012"
          helper="10 цифр для юр. лица или 12 цифр для ИП"
          required
        />
      )}

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

      <div className="space-y-2">
        <div className="flex items-start gap-3">
          <Checkbox
            id="register-pdp-consent"
            {...register('pdp_consent')}
            disabled={isSubmitting}
            aria-invalid={hasPdpConsentError || undefined}
            aria-labelledby="register-pdp-consent-label-prefix register-pdp-consent-policy-link"
            aria-describedby={
              errors.pdp_consent?.message ? 'register-pdp-consent-error' : undefined
            }
            className={
              hasPdpConsentError
                ? 'border-[var(--color-accent-danger)] bg-[var(--color-accent-danger)]/8 peer-focus:ring-[var(--color-accent-danger)]'
                : undefined
            }
          />
          <span className="text-body-s text-text-primary select-none">
            <label
              id="register-pdp-consent-label-prefix"
              htmlFor="register-pdp-consent"
              className="cursor-pointer"
            >
              Я даю согласие на обработку моих персональных данных в соответствии с
            </label>{' '}
            <Link
              id="register-pdp-consent-policy-link"
              href="/privacy-policy"
              target="_blank"
              rel="noopener noreferrer"
              className="text-primary underline hover:text-primary-hover"
            >
              «Политикой обработки персональных данных ООО „Фриспорт“»
            </Link>
          </span>
        </div>
        {errors.pdp_consent?.message && (
          <p
            id="register-pdp-consent-error"
            className="text-body-xs text-[var(--color-accent-danger)]"
            role="alert"
          >
            {errors.pdp_consent.message}
          </p>
        )}
      </div>

      <div className="flex items-start gap-3">
        {/* Маркетинговое согласие опционально: inline error-state намеренно не назначается. */}
        <Checkbox
          id="register-marketing-consent"
          {...register('marketing_consent')}
          disabled={isSubmitting}
        />
        <label
          htmlFor="register-marketing-consent"
          className="text-body-s text-text-primary cursor-pointer select-none"
        >
          Я согласен (на) получать рекламные и информационные рассылки от ООО „Фриспорт“
        </label>
      </div>

      {/* AC 6: Использование Button компонента */}
      {/* AC 4: Loading state с блокировкой кнопки */}
      <Button type="submit" loading={isSubmitting} disabled={isSubmitting} className="w-full">
        Зарегистрироваться
      </Button>
    </form>
  );
};
