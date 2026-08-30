/**
 * RegisterForm Component
 * Story 28.1 - Базовая аутентификация и регистрация B2C
 * Story 29.1 - Role Selection UI & Warnings
 *
 * Форма регистрации с выбором роли и условными B2B полями
 *
 * Story 28.1 AC 2: Registration Flow (автологина нет: розничная регистрация
 *                   отключена, все роли формы требуют верификации менеджером)
 * Story 28.1 AC 3: Client-side валидация (Zod)
 * Story 28.1 AC 4: Error Handling и Loading States
 * Story 28.1 AC 5: Интеграция с authService
 * Story 28.1 AC 6: Использование UI компонентов
 * Story 28.1 AC 7: Responsive Design
 * Story 28.1 AC 10: Accessibility
 *
 * Story 29.1 AC 1: Поле выбора роли (3 B2B-опции, розничной нет)
 * Story 29.1 AC 2: Роль не предвыбрана — выбор обязателен
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
import { cn } from '@/utils/cn';
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

// Story 29.1 AC 1: Константа с опциями ролей.
// Розничного покупателя в списке нет: портал — B2B-площадка, саморегистрация
// доступна только ролям, которые проходят верификацию менеджером.
const ROLE_OPTIONS = [
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
  country: 'country',
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
  // Заявка принята и ждёт верификации менеджером: токенов нет, входить некуда
  const [isPending, setIsPending] = useState(false);

  const {
    register,
    handleSubmit,
    watch,
    setError,
    formState: { errors, isSubmitting },
  } = useForm<RegisterFormInput, unknown, RegisterFormData>({
    resolver: zodResolver(registerSchema),
    // Роль не предвыбрана: пользователь обязан осознанно указать тип аккаунта.
    // Пустая строка — значение плейсхолдера в <select>, схема её отклоняет.
    defaultValues: {
      role: '' as unknown as RegisterFormInput['role'],
      country: 'Россия',
      pdp_consent: false,
      marketing_consent: false,
    },
  });

  // Story 29.1: Отслеживаем выбранную роль для условной логики
  const selectedRole = watch('role');
  const hasPdpConsentError = Boolean(errors.pdp_consent?.message);
  // Кнопка регистрации активна только при согласии на обработку ПДн
  const pdpConsentChecked = watch('pdp_consent') === true;

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
        // Фамилию и телефон эта форма не собирает — их запрашивает строгая
        // B2B-форма /b2b-register (см. deferred-work.md)
        last_name: '',
        phone: '',
        role: data.role, // Story 29.1 AC 4: Используем выбранную роль
        // Story 29.1 AC 8: B2B-поля обязательны для всех доступных ролей
        company_name: data.company_name,
        tax_id: data.tax_id?.trim(),
        country: data.country,
        pdp_consent: data.pdp_consent,
        marketing_consent: data.marketing_consent ?? false,
      };

      const response = await authService.register(registerData);

      // Callback при успехе
      if (onSuccess) {
        onSuccess();
      }

      // После отключения розничной регистрации автологина не бывает: все роли
      // формы — B2B, аккаунт создаётся неверифицированным и токенов не получает.
      // Молчаливый редирект на главную выглядел бы как потеря заявки, поэтому
      // показываем то же состояние ожидания, что и B2B-форма.
      if (!response.user || response.user.is_verified === false) {
        setIsPending(true);
        return;
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

  // Story 29.1 AC 3: B2B-блоки показываются, как только роль выбрана —
  // все доступные в форме роли являются B2B.
  const isB2BRole = Boolean(selectedRole);
  // Story 29.1 AC 8: Определяем, нужно ли поле ИНН.
  // ИНН обязателен для ВСЕХ B2B-ролей (включая trainer): без него
  // CustomerIdentityResolver не находит существующего клиента из 1С
  // и вместо привязки создается дубль пользователя.
  const requiresTaxId = isB2BRole;
  // Подсказка под полем зависит от страны: маска российского ИНН
  // неприменима к белорусскому УНП и казахстанскому БИН/ИИН
  const selectedCountry = watch('country') ?? 'Россия';
  const taxIdHelper =
    selectedCountry === 'Россия'
      ? 'Тренер как физлицо или ИП указывает свой ИНН (12 цифр), клуб — ИНН организации (10 цифр). Один ИНН — один аккаунт.'
      : 'Налоговый номер организации: от 8 до 12 цифр. Один номер — один аккаунт.';

  // Состояние «заявка на рассмотрении» — единственный успешный исход формы,
  // пока розничная регистрация отключена (см. onSubmit)
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
                Ваша заявка на регистрацию успешно отправлена.
              </p>
              <p className="text-body-s text-text-secondary">
                Мы проверим предоставленные данные и свяжемся с вами в течение 1-2 рабочих дней.
                После одобрения заявки вы сможете войти в личный кабинет.
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
          aria-invalid={Boolean(errors.role?.message) || undefined}
          aria-describedby={errors.role?.message ? 'register-role-error' : undefined}
          className={cn(
            // --color-primary-500 в проекте не объявлен: битый var() откатывал кольцо фокуса
            // к currentcolor, а с приглушённым плейсхолдером оно стало бы почти невидимым
            'w-full px-3 py-2 border border-gray-300 rounded-sm shadow-sm focus:ring-2 focus:ring-[var(--color-primary)] focus:ring-offset-2 focus:outline-none disabled:opacity-50 disabled:cursor-not-allowed',
            // Пока роль не выбрана, текст плейсхолдера приглушён тем же токеном,
            // что и placeholder в Input («Иван»): --color-neutral-500
            selectedRole ? 'text-[var(--color-text-primary)]' : 'text-[var(--color-neutral-500)]'
          )}
        >
          {/* Без явного цвета пункты списка унаследовали бы приглушённый color у <select>.
              Ограничение: Safari и Chrome на Android рисуют попап системно и цвет <option> там может
              игнорироваться — тогда весь список будет приглушённым, пока роль не выбрана. */}
          <option value="" className="text-[var(--color-neutral-500)]">
            Выберите тип аккаунта
          </option>
          {ROLE_OPTIONS.map(option => (
            <option
              key={option.value}
              value={option.value}
              className="text-[var(--color-text-primary)]"
            >
              {option.label}
            </option>
          ))}
        </select>
        {errors.role?.message && (
          <p
            id="register-role-error"
            className="text-body-xs text-[var(--color-accent-danger)]"
            role="alert"
          >
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

      {/* Story 29.1 AC 8: Условные B2B поля - tax_id для всех B2B ролей */}
      {requiresTaxId && (
        <Input
          label="ИНН"
          type="text"
          {...register('tax_id')}
          error={errors.tax_id?.message}
          disabled={isSubmitting}
          placeholder="1234567890 или 123456789012"
          helper={taxIdHelper}
          required
        />
      )}

      {/* Страна регистрации для B2B: определяет маршрутизацию заявки на менеджера */}
      {isB2BRole && (
        <div className="space-y-1">
          <label htmlFor="register-country" className="block text-body-s font-medium text-gray-700">
            Страна
          </label>
          <select
            id="register-country"
            {...register('country')}
            disabled={isSubmitting}
            aria-invalid={Boolean(errors.country?.message) || undefined}
            aria-describedby={errors.country?.message ? 'register-country-error' : undefined}
            className="w-full px-3 py-2 border border-gray-300 rounded-sm shadow-sm focus:ring-2 focus:ring-[var(--color-primary)] focus:ring-offset-2 focus:outline-none disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <option value="Россия">Россия</option>
            <option value="Беларусь">Беларусь</option>
            <option value="Казахстан">Казахстан</option>
          </select>
          {errors.country?.message && (
            <p
              id="register-country-error"
              className="text-body-xs text-[var(--color-accent-danger)]"
              role="alert"
            >
              {errors.country.message}
            </p>
          )}
        </div>
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
              «Политикой обработки персональных данных»
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
          Я согласен (на) получать рекламные и информационные рассылки от OPTISPORT
        </label>
      </div>

      {/* AC 6: Использование Button компонента */}
      {/* AC 4: Loading state с блокировкой кнопки */}
      <Button
        type="submit"
        loading={isSubmitting}
        disabled={isSubmitting || !pdpConsentChecked}
        className="w-full"
      >
        Зарегистрироваться
      </Button>
    </form>
  );
};
