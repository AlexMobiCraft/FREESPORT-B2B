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

import React, { useEffect, useRef, useState } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { Input } from '@/components/ui/Input/Input';
import { PhoneInput } from '@/components/ui/Input/PhoneInput';
import { Button } from '@/components/ui/Button/Button';
import { Checkbox } from '@/components/ui/Checkbox/Checkbox';
import authService from '@/services/authService';
import { isSafeRedirectUrl } from '@/utils/urlUtils';
import {
  b2bRegisterSchema,
  type B2BRegisterFormData,
  type B2BRegisterFormInput,
} from '@/schemas/authSchemas';
import type { RegisterRequest } from '@/types/api';
import {
  applyBackendFieldErrors,
  getFirstValidationMessage,
  getValidationMessage,
  type ApiErrorData,
  type BackendFieldErrorMap,
} from '@/utils/validationErrorParser';

const B2B_FIELD_ERROR_MAP = {
  email: 'email',
  password: 'password',
  password_confirm: 'confirmPassword',
  first_name: 'first_name',
  last_name: 'last_name',
  phone: 'phone',
  role: 'role',
  company_name: 'company_name',
  tax_id: 'tax_id',
  country: 'country',
  ogrn: 'ogrn',
  legal_address: 'legal_address',
  pdp_consent: 'pdp_consent',
} satisfies BackendFieldErrorMap<B2BRegisterFormInput>;

export interface B2BRegisterFormProps {
  /**
   * Callback после успешной регистрации.
   * Для pending B2B-заявки вызывается после рендера inline pending state.
   */
  onSuccess?: () => void;
  /** URL для редиректа после успешной регистрации */
  redirectUrl?: string;
}

export const B2BRegisterForm: React.FC<B2BRegisterFormProps> = ({ onSuccess, redirectUrl }) => {
  const router = useRouter();
  const [apiError, setApiError] = useState<string | null>(null);
  const [isPending, setIsPending] = useState(false);
  const [neutralMessage, setNeutralMessage] = useState<string | null>(null);
  const [shouldNotifyPendingSuccess, setShouldNotifyPendingSuccess] = useState(false);
  const pendingSuccessCallbackRef = useRef<(() => void) | null>(null);
  const pendingSuccessNotifiedRef = useRef(false);

  const {
    register,
    handleSubmit,
    setError,
    formState: { errors, isSubmitting },
  } = useForm<B2BRegisterFormInput, unknown, B2BRegisterFormData>({
    resolver: zodResolver(b2bRegisterSchema),
    defaultValues: {
      role: 'wholesale_level1',
      country: 'Россия',
      pdp_consent: false,
      marketing_consent: false,
    },
  });

  const hasPdpConsentError = Boolean(errors.pdp_consent?.message);

  useEffect(() => {
    if ((!isPending && !neutralMessage) || !shouldNotifyPendingSuccess) {
      return;
    }

    if (pendingSuccessNotifiedRef.current) {
      return;
    }

    pendingSuccessNotifiedRef.current = true;
    pendingSuccessCallbackRef.current?.();
    setShouldNotifyPendingSuccess(false);
  }, [isPending, neutralMessage, shouldNotifyPendingSuccess]);

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
        country: data.country,
        pdp_consent: data.pdp_consent,
        marketing_consent: data.marketing_consent ?? false,
      };

      // AC 4: Отправка через authService.registerB2B()
      const response = await authService.registerB2B(registerData);

      // Привязка к существующей 1С-записи: бэкенд намеренно возвращает
      // нейтральный ответ без `user` (без PII/JWT найденной записи) —
      // инструкции по дальнейшим шагам присланы на указанный email.
      if (!response.user) {
        pendingSuccessCallbackRef.current = onSuccess ?? null;
        pendingSuccessNotifiedRef.current = false;
        setNeutralMessage(
          response.message ||
            'Если данные совпадают с записью в 1С, дальнейшие инструкции отправлены на указанный email.'
        );
        setShouldNotifyPendingSuccess(Boolean(onSuccess));
        return;
      }

      // AC 6: Обработка статуса "На рассмотрении" (is_verified: false)
      if (response.user.is_verified === false) {
        pendingSuccessCallbackRef.current = onSuccess ?? null;
        pendingSuccessNotifiedRef.current = false;
        setIsPending(true);
        setShouldNotifyPendingSuccess(Boolean(onSuccess));
        return;
      } else {
        // CRITICAL FIX: Force token refresh immediately to ensure valid session
        // Initial access token from registration might be restricted/invalid until refresh
        try {
          await authService.refreshToken();
        } catch {
          // Регистрация уже успешна; сбой refresh не должен превращать ее в ошибку.
        }

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
        response?: {
          status?: number;
          data?: ApiErrorData;
        };
      };
      const responseData = err.response?.data || {};
      const firstFieldError = applyBackendFieldErrors(responseData, setError, B2B_FIELD_ERROR_MAP);

      if (err.response?.status === 409) {
        // AC 5: Специфичная обработка "Компания уже зарегистрирована"
        setApiError(
          getValidationMessage(responseData.company_name) ||
            getValidationMessage(responseData.email) ||
            'Компания или email уже зарегистрированы'
        );
      } else if (err.response?.status === 400) {
        // Ошибки валидации
        setApiError(
          firstFieldError || getFirstValidationMessage(responseData) || 'Ошибка валидации данных'
        );
      } else if (err.response?.status === 500) {
        setApiError('Ошибка сервера. Попробуйте позже');
      } else {
        setApiError(
          getValidationMessage(responseData.detail) || 'Произошла ошибка при регистрации'
        );
      }
    }
  };

  // Привязка к существующей 1С-записи: нейтральное сообщение без раскрытия
  // деталей найденной записи (см. authService.registerB2B / RegisterResponse).
  if (neutralMessage) {
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
              <h3 className="text-lg font-semibold text-text-primary mb-2">Проверьте почту</h3>
              <p className="text-body-m text-text-primary">{neutralMessage}</p>
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

        <div className="space-y-1">
          <label
            htmlFor="b2b-register-country"
            className="block text-body-s font-medium text-text-primary"
          >
            Страна
          </label>
          <select
            id="b2b-register-country"
            {...register('country')}
            disabled={isSubmitting}
            aria-invalid={Boolean(errors.country?.message) || undefined}
            aria-describedby={errors.country?.message ? 'b2b-register-country-error' : undefined}
            className="w-full rounded-md border border-gray-300 bg-white px-3 py-2 text-body-m text-text-primary focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary disabled:opacity-60"
          >
            <option value="Россия">Россия</option>
            <option value="Беларусь">Беларусь</option>
            <option value="Казахстан">Казахстан</option>
          </select>
          {errors.country?.message && (
            <p
              id="b2b-register-country-error"
              className="text-body-xs text-[var(--color-accent-danger)]"
              role="alert"
            >
              {errors.country.message}
            </p>
          )}
        </div>
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

        <div className="space-y-2">
          <div className="flex items-start gap-3">
            <Checkbox
              id="b2b-register-pdp-consent"
              {...register('pdp_consent')}
              disabled={isSubmitting}
              aria-invalid={hasPdpConsentError || undefined}
              aria-labelledby="b2b-register-pdp-consent-label-prefix b2b-register-pdp-consent-policy-link b2b-register-pdp-consent-label-suffix"
              aria-describedby={
                errors.pdp_consent?.message ? 'b2b-register-pdp-consent-error' : undefined
              }
              className={
                hasPdpConsentError
                  ? 'border-[var(--color-accent-danger)] bg-[var(--color-accent-danger)]/8 peer-focus:ring-[var(--color-accent-danger)]'
                  : undefined
              }
            />
            <span className="text-body-s text-text-primary select-none">
              <label
                id="b2b-register-pdp-consent-label-prefix"
                htmlFor="b2b-register-pdp-consent"
                className="cursor-pointer"
              >
                Я даю согласие на
              </label>{' '}
              <Link
                id="b2b-register-pdp-consent-policy-link"
                href="/privacy-policy"
                target="_blank"
                rel="noopener noreferrer"
                className="text-primary underline hover:text-primary-hover"
              >
                обработку моих персональных данных
              </Link>{' '}
              <label
                id="b2b-register-pdp-consent-label-suffix"
                htmlFor="b2b-register-pdp-consent"
                className="cursor-pointer"
              >
                в соответствии с Политикой
              </label>
            </span>
          </div>
          {errors.pdp_consent?.message && (
            <p
              id="b2b-register-pdp-consent-error"
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
            id="b2b-register-marketing-consent"
            {...register('marketing_consent')}
            disabled={isSubmitting}
          />
          <label
            htmlFor="b2b-register-marketing-consent"
            className="text-body-s text-text-primary cursor-pointer select-none"
          >
            Я согласен(на) получать рекламные и информационные рассылки от FREESPORT
          </label>
        </div>
      </div>

      {/* Submit Button */}
      <Button type="submit" loading={isSubmitting} disabled={isSubmitting} className="w-full mt-6">
        Отправить заявку
      </Button>
    </form>
  );
};
