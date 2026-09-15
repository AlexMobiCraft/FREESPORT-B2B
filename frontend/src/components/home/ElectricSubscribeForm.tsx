/**
 * Electric Subscribe Form Component
 * Форма подписки на email-рассылку в стиле Electric Orange
 */

'use client';

import React from 'react';
import Link from 'next/link';
import { useForm, type UseFormRegisterReturn } from 'react-hook-form';
import { toast } from 'react-hot-toast';
import { subscribeService } from '@/services/subscribeService';
import { ElectricButton } from '@/components/ui/Button/ElectricButton';
import { cn } from '@/utils/cn';
import {
  CONSENT_TEXT_OUTDATED_CODE,
  CONSENT_TEXT_OUTDATED_MESSAGE,
  CONSENT_TEXT_VERSIONS,
  getConsentTextOutdatedMessage,
} from '@/constants/consentTexts';

interface SubscribeFormData {
  email: string;
  pdp_consent: boolean;
  marketing_consent: boolean;
}

type SubscribeFormField = keyof SubscribeFormData;
type SubscribeValidationDetails = Record<string, string[]>;
type SubscribeValidationError = Error & {
  details?: SubscribeValidationDetails;
  code?: string;
};

const PDP_CONSENT_REQUIRED = 'Необходимо согласие на обработку персональных данных.';
// Тот же текст, что `MARKETING_CONSENT_REQUIRED` на бэкенде (стори 41.11).
const MARKETING_CONSENT_REQUIRED =
  'Необходимо согласие на получение рассылок по электронной почте.';
const THROTTLED_ERROR = 'Слишком много попыток. Попробуйте через минуту.';
const SERVER_TEMPORARILY_UNAVAILABLE = 'СЕРВЕР ВРЕМЕННО НЕДОСТУПЕН. ПОПРОБУЙТЕ ПОЗЖЕ';

const electricToastErrorOptions = {
  style: { borderRadius: '0', background: '#000', color: '#fff', border: '1px solid red' },
};

const getBackendMessage = (value: string[] | undefined) => value?.[0];

const getBackendFieldError = (error: unknown, field: SubscribeFormField) => {
  if (!(error instanceof Error) || !('details' in error)) {
    return undefined;
  }

  return getBackendMessage((error as SubscribeValidationError).details?.[field]);
};

/**
 * Отказ по устаревшей (или непереданной) версии формулировки согласия.
 * Признак — машинный код с верхнего уровня ответа сервера: текст сообщения
 * правят, а HTTP-статус общий для всей валидации.
 */
const isConsentTextOutdatedError = (error: unknown) =>
  error instanceof Error && (error as SubscribeValidationError).code === CONSENT_TEXT_OUTDATED_CODE;

/**
 * Сообщение об устаревшей формулировке. Берётся не «первым из `details`»:
 * в ответе рядом с полем версии может лежать попутная ошибка (например, email),
 * и человеку показалось бы «введите корректный email» вместо единственного
 * работающего действия — обновить страницу. `getConsentTextOutdatedMessage`
 * берёт текст только из полей версии, иначе — запасное сообщение.
 */
const getConsentOutdatedMessage = (error: unknown) => {
  const { code, details } = (error ?? {}) as SubscribeValidationError;
  return getConsentTextOutdatedMessage({ error: code, details }) ?? CONSENT_TEXT_OUTDATED_MESSAGE;
};

const getFirstBackendError = (error: unknown) => {
  if (!(error instanceof Error) || !('details' in error)) {
    return undefined;
  }

  const details = (error as SubscribeValidationError).details;
  if (!details) {
    return undefined;
  }

  for (const value of Object.values(details)) {
    const message = getBackendMessage(value);
    if (message) {
      return message;
    }
  }

  return undefined;
};

interface ElectricConsentCheckboxProps {
  id: string;
  /** Id элементов, из которых складывается доступное имя чекбокса. */
  labelledBy: string;
  errorId: string;
  error?: string;
  checked: boolean;
  disabled: boolean;
  registration: UseFormRegisterReturn;
  /** Видимый текст согласия: `<label htmlFor={id}>` и, при необходимости, ссылка. */
  children: React.ReactNode;
}

/**
 * Обязательный чекбокс согласия в стилистике electric: скошенный квадрат поверх
 * `sr-only peer` input. Разметка общая для чекбоксов ПДн и рассылки (стори 41.11),
 * наружу не экспортируется: у темы blue свой `Checkbox`, стили разные.
 *
 * Имя задаётся `aria-labelledby`, а не всеми `<label>` input: квадрат — тоже
 * `<label htmlFor>`, и его галочка «✓» попала бы в доступное имя.
 */
const ElectricConsentCheckbox = ({
  id,
  labelledBy,
  errorId,
  error,
  checked,
  disabled,
  registration,
  children,
}: ElectricConsentCheckboxProps) => {
  const hasError = !!error;

  return (
    <div className="space-y-2">
      <div className="flex items-start gap-3">
        <div className="relative flex items-center pt-0.5">
          <input
            id={id}
            type="checkbox"
            className="sr-only peer"
            disabled={disabled}
            name={registration.name}
            ref={registration.ref}
            onBlur={registration.onBlur}
            checked={checked}
            onChange={registration.onChange}
            aria-required="true"
            aria-invalid={hasError || undefined}
            aria-labelledby={labelledBy}
            aria-describedby={hasError ? errorId : undefined}
          />
          <label
            htmlFor={id}
            className={cn(
              'flex h-5 w-5 cursor-pointer items-center justify-center border-2 transition-all duration-150',
              'transform -skew-x-12',
              'peer-checked:border-[var(--color-primary)] peer-checked:bg-[var(--color-primary)]',
              'peer-focus:ring-2 peer-focus:ring-[var(--color-primary)]/30 peer-focus:ring-offset-2',
              hasError
                ? 'border-red-500 peer-focus:ring-red-500/30'
                : 'border-[var(--color-primary)] hover:bg-[var(--color-primary)]/15',
              disabled && 'cursor-not-allowed opacity-50'
            )}
          >
            {checked && (
              <span aria-hidden="true" className="transform skew-x-12 text-xs font-bold text-black">
                ✓
              </span>
            )}
          </label>
        </div>
        <span className="font-inter text-xs md:text-sm uppercase leading-relaxed text-[var(--color-text-secondary)]">
          {children}
        </span>
      </div>
      {error && (
        <p id={errorId} className="text-red-500 text-xs font-bold uppercase mt-1" role="alert">
          {error}
        </p>
      )}
    </div>
  );
};

export const ElectricSubscribeForm: React.FC = () => {
  const formBaseId = React.useId();
  const emailId = `${formBaseId}-electric-email-subscribe`;
  const pdpConsentId = `${formBaseId}-electric-subscribe-pdp-consent`;
  const pdpConsentLabelPrefixId = `${formBaseId}-electric-subscribe-pdp-consent-label-prefix`;
  const pdpConsentPolicyLinkId = `${formBaseId}-electric-subscribe-pdp-consent-policy-link`;
  const pdpConsentErrorId = `${formBaseId}-electric-subscribe-pdp-consent-error`;
  const marketingConsentId = `${formBaseId}-electric-subscribe-marketing-consent`;
  const marketingConsentLabelId = `${formBaseId}-electric-subscribe-marketing-consent-label`;
  const marketingConsentErrorId = `${formBaseId}-electric-subscribe-marketing-consent-error`;

  const {
    register,
    handleSubmit,
    watch,
    setError,
    clearErrors,
    formState: { errors, isSubmitting },
    reset,
  } = useForm<SubscribeFormData>({
    defaultValues: { email: '', pdp_consent: false, marketing_consent: false },
  });

  const pdpConsent = watch('pdp_consent');
  // Порядок `register` важен: `react-hook-form` проверяет поля и переводит фокус
  // на первое ошибочное в этом порядке. ПДн — первым: его `required` читает DOM,
  // а к проверке следующих полей `isSubmitting` уже делает чекбоксы `disabled`.
  // Email — до рассылки: при двух ошибках фокус получает поле, стоящее выше
  // по разметке (ревью стори 41.11).
  const pdpConsentRegistration = register('pdp_consent', {
    required: PDP_CONSENT_REQUIRED,
  });
  const emailRegistration = register('email', {
    required: 'Email обязателен',
    pattern: {
      value: /^[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}$/i,
      message: 'Введите корректный email',
    },
  });

  // Согласие на рассылку обязательно, но кнопку не блокирует (решение Alex,
  // 2026-09-12): без галочки `handleSubmit` не вызывает `onSubmit`, ставит
  // ошибку у этого чекбокса и переводит на него фокус (`shouldFocusError`).
  // Правило — `validate` по значению формы, а не `required`: `required` у
  // чекбокса читает DOM и считает отключённый чекбокс пустым, а `handleSubmit`
  // успевает выставить `isSubmitting` (→ `disabled`) до проверки этого поля.
  const marketingConsent = watch('marketing_consent');
  const marketingConsentRegistration = register('marketing_consent', {
    validate: value => value === true || MARKETING_CONSENT_REQUIRED,
  });

  const onSubmit = async (data: SubscribeFormData) => {
    clearErrors(['pdp_consent', 'marketing_consent']);

    try {
      await subscribeService.subscribe({
        email: data.email,
        pdp_consent: data.pdp_consent,
        marketing_consent: data.marketing_consent,
        // Версии формулировок, которые показала эта сборка формы, — у каждого
        // чекбокса своя (стори 41.9, 41.11). Сервер отклонит запрос, если текст
        // успели поправить, — вкладка со старым текстом не запишет согласие на
        // чужую формулировку.
        pdp_consent_text_version: CONSENT_TEXT_VERSIONS.newsletterPdp,
        marketing_consent_text_version: CONSENT_TEXT_VERSIONS.newsletterMarketing,
      });
      toast.success('ВЫ УСПЕШНО ПОДПИСАЛИСЬ НА РАССЫЛКУ!', {
        style: {
          borderRadius: '0',
          background: '#000',
          color: '#fff',
          border: '1px solid #FF6600',
        },
      });
      reset();
    } catch (error: unknown) {
      // Error handling similar to original but with toast styles if we want
      if (isConsentTextOutdatedError(error)) {
        // Формулировку поправили после отрисовки этой вкладки: человеку нужно
        // обновить страницу, а не править ввод. Случай разводится по машинному
        // коду ответа, а не по тексту сообщения.
        toast.error(getConsentOutdatedMessage(error).toUpperCase(), electricToastErrorOptions);
      } else if (error instanceof Error && error.message === 'validation_error') {
        const pdpConsentError = getBackendFieldError(error, 'pdp_consent');
        const marketingConsentError = getBackendFieldError(error, 'marketing_consent');
        const emailError = getBackendFieldError(error, 'email');
        const backendError = getFirstBackendError(error);

        if (pdpConsentError) {
          setError('pdp_consent', { type: 'server', message: pdpConsentError });
        }
        if (marketingConsentError) {
          setError('marketing_consent', { type: 'server', message: marketingConsentError });
        }
        if (emailError) {
          setError('email', { type: 'server', message: emailError });
        }

        toast.error(
          pdpConsentError ??
            marketingConsentError ??
            emailError ??
            backendError ??
            'ОШИБКА ПОДПИСКИ',
          electricToastErrorOptions
        );
      } else if (error instanceof Error && error.message === 'throttled') {
        toast.error(
          (getFirstBackendError(error) ?? THROTTLED_ERROR).toUpperCase(),
          electricToastErrorOptions
        );
      } else if (error instanceof Error && error.message === 'server_error') {
        toast.error(
          getFirstBackendError(error)?.toUpperCase() ?? SERVER_TEMPORARILY_UNAVAILABLE,
          electricToastErrorOptions
        );
      } else {
        toast.error('ОШИБКА ПОДПИСКИ', electricToastErrorOptions);
      }
    }
  };

  return (
    <form
      onSubmit={handleSubmit(onSubmit)}
      className="space-y-6 max-w-xl mx-auto md:max-w-none md:mx-0"
    >
      <div>
        <h3 className="text-2xl md:text-3xl font-bold text-[var(--foreground)] uppercase mb-2 transform -skew-x-12">
          <span className="inline-block transform skew-x-12">Подписаться на рассылку</span>
        </h3>
        <p className="text-[var(--color-text-secondary)] font-inter text-sm md:text-base">
          Получайте первыми информацию о новинках и акциях
        </p>
      </div>

      <div className="space-y-2">
        <label
          htmlFor={emailId}
          className="block text-sm font-bold text-[var(--foreground)] uppercase transform -skew-x-12"
        >
          <span className="inline-block transform skew-x-12">Email</span>
        </label>
        <div className="relative transform -skew-x-12">
          <input
            id={emailId}
            type="email"
            placeholder="your@email.com"
            className={`
                   w-full bg-[var(--bg-card)] border-2 px-4 py-3 outline-none transition-all duration-300 transform skew-x-12
                   placeholder:text-[var(--color-text-muted)]
                   ${
                     errors.email
                       ? 'border-red-500 focus:border-red-500'
                       : 'border-[var(--border-default)] focus:border-[var(--color-primary)]'
                   }
                `}
            {...emailRegistration}
          />
        </div>
        {errors.email && (
          <p className="text-red-500 text-xs font-bold uppercase mt-1">{errors.email.message}</p>
        )}
      </div>

      {/* Два отдельных согласия (стори 41.11): ст. 9 ч. 1 152-ФЗ требует оформлять
          согласие на ПДн отдельно от согласия на рекламную рассылку (ст. 18 38-ФЗ). */}
      <div className="space-y-4">
        <ElectricConsentCheckbox
          id={pdpConsentId}
          labelledBy={`${pdpConsentLabelPrefixId} ${pdpConsentPolicyLinkId}`}
          errorId={pdpConsentErrorId}
          error={errors.pdp_consent?.message}
          checked={pdpConsent}
          disabled={isSubmitting}
          registration={pdpConsentRegistration}
        >
          <label id={pdpConsentLabelPrefixId} htmlFor={pdpConsentId} className="cursor-pointer">
            Я даю согласие на обработку моих персональных данных в соответствии с
          </label>{' '}
          <Link
            id={pdpConsentPolicyLinkId}
            href="/privacy-policy"
            target="_blank"
            rel="noopener noreferrer"
            className="text-[var(--color-primary)] underline hover:text-[var(--foreground)]"
          >
            «Политикой обработки персональных данных»
          </Link>
        </ElectricConsentCheckbox>
        <ElectricConsentCheckbox
          id={marketingConsentId}
          labelledBy={marketingConsentLabelId}
          errorId={marketingConsentErrorId}
          error={errors.marketing_consent?.message}
          checked={marketingConsent}
          disabled={isSubmitting}
          registration={marketingConsentRegistration}
        >
          <label
            id={marketingConsentLabelId}
            htmlFor={marketingConsentId}
            className="cursor-pointer"
          >
            Я согласен(на) получать информационные и рекламные рассылки от OPTISPORT по электронной
            почте
          </label>
        </ElectricConsentCheckbox>
      </div>

      <ElectricButton
        type="submit"
        variant="primary"
        size="lg"
        disabled={isSubmitting || !pdpConsent}
        className="w-full"
      >
        {isSubmitting ? 'ОТПРАВКА...' : 'ПОДПИСАТЬСЯ'}
      </ElectricButton>
    </form>
  );
};
