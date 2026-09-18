/**
 * SubscribeForm Component
 * Форма подписки на email-рассылку
 *
 * @see Story 11.3 - AC 1, 2, 5
 */

'use client';

import React from 'react';
import Link from 'next/link';
import { useForm } from 'react-hook-form';
import { toast } from 'react-hot-toast';
import { subscribeService } from '@/services/subscribeService';
import { Input } from '@/components/ui/Input/Input';
import { Button } from '@/components/ui/Button/Button';
import { Checkbox } from '@/components/ui/Checkbox/Checkbox';
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
const SERVER_TEMPORARILY_UNAVAILABLE = 'Сервер временно недоступен. Попробуйте позже';

const consentErrorClassName =
  'border-[var(--color-accent-danger)] bg-[var(--color-accent-danger)]/8 peer-focus:ring-[var(--color-accent-danger)]';

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

export const SubscribeForm: React.FC = () => {
  const consentBaseId = React.useId();
  const pdpConsentId = `${consentBaseId}-subscribe-pdp-consent`;
  const pdpConsentLabelPrefixId = `${consentBaseId}-subscribe-pdp-consent-label-prefix`;
  const pdpConsentPolicyLinkId = `${consentBaseId}-subscribe-pdp-consent-policy-link`;
  const pdpConsentErrorId = `${consentBaseId}-subscribe-pdp-consent-error`;
  const marketingConsentId = `${consentBaseId}-subscribe-marketing-consent`;
  const marketingConsentLabelId = `${consentBaseId}-subscribe-marketing-consent-label`;
  const marketingConsentErrorId = `${consentBaseId}-subscribe-marketing-consent-error`;

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
  const hasPdpConsentError = !!errors.pdp_consent;
  const emailRegistration = register('email', {
    required: 'Укажите электронную почту',
    pattern: {
      value: /^[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}$/i,
      message: 'Введите корректный адрес электронной почты',
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
  const hasMarketingConsentError = !!errors.marketing_consent;

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
      toast.success('Вы успешно подписались на рассылку');
      reset();
    } catch (error: unknown) {
      if (error instanceof Error) {
        if (isConsentTextOutdatedError(error)) {
          // Формулировку поправили после того, как эта вкладка была отрисована.
          // Человеку нужно обновить страницу, а не править ввод, поэтому случай
          // разводится по машинному коду, а не по тексту сообщения.
          toast.error(getConsentOutdatedMessage(error));
        } else if (error.message === 'validation_error') {
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
              'Введите корректный адрес электронной почты'
          );
        } else if (error.message === 'throttled') {
          toast.error(getFirstBackendError(error) ?? THROTTLED_ERROR);
        } else if (error.message === 'server_error') {
          toast.error(getFirstBackendError(error) ?? SERVER_TEMPORARILY_UNAVAILABLE);
        } else {
          toast.error('Не удалось подписаться. Попробуйте позже');
        }
      } else {
        toast.error('Не удалось подписаться. Попробуйте позже');
      }
    }
  };

  return (
    <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
      <h3 className="text-xl font-semibold text-text-primary">Подписаться на рассылку</h3>
      <p className="text-sm text-text-secondary">
        Получайте первыми информацию о новинках и акциях
      </p>
      <Input
        label="Электронная почта"
        type="email"
        error={errors.email?.message}
        aria-required="true"
        aria-invalid={!!errors.email}
        {...emailRegistration}
      />
      {/* Два отдельных согласия (стори 41.11): ст. 9 ч. 1 152-ФЗ требует оформлять
          согласие на ПДн отдельно от согласия на рекламную рассылку (ст. 18 38-ФЗ).
          Оба обязательны и объявлены через `aria-required`, а не `required`:
          нативная валидация перехватила бы отправку до `react-hook-form`. */}
      <div className="space-y-3">
        <div className="space-y-2">
          <div className="flex items-start gap-3">
            <Checkbox
              id={pdpConsentId}
              name={pdpConsentRegistration.name}
              ref={pdpConsentRegistration.ref}
              onBlur={pdpConsentRegistration.onBlur}
              onChange={pdpConsentRegistration.onChange}
              checked={pdpConsent}
              disabled={isSubmitting}
              aria-required="true"
              aria-invalid={hasPdpConsentError || undefined}
              aria-labelledby={`${pdpConsentLabelPrefixId} ${pdpConsentPolicyLinkId}`}
              aria-describedby={hasPdpConsentError ? pdpConsentErrorId : undefined}
              className={hasPdpConsentError ? consentErrorClassName : undefined}
            />
            <span className="text-body-s text-text-primary select-none">
              <label id={pdpConsentLabelPrefixId} htmlFor={pdpConsentId} className="cursor-pointer">
                Я даю согласие на обработку моих персональных данных в соответствии с
              </label>{' '}
              <Link
                id={pdpConsentPolicyLinkId}
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
              id={pdpConsentErrorId}
              className="text-body-xs text-[var(--color-accent-danger)]"
              role="alert"
            >
              {errors.pdp_consent.message}
            </p>
          )}
        </div>
        <div className="space-y-2">
          <div className="flex items-start gap-3">
            <Checkbox
              id={marketingConsentId}
              name={marketingConsentRegistration.name}
              ref={marketingConsentRegistration.ref}
              onBlur={marketingConsentRegistration.onBlur}
              onChange={marketingConsentRegistration.onChange}
              checked={marketingConsent}
              disabled={isSubmitting}
              aria-required="true"
              aria-invalid={hasMarketingConsentError || undefined}
              // Имя — через `aria-labelledby`, а не «все <label for>»: первый такой
              // label — пустой квадрат `Checkbox`, и при `aria-describedby` axe
              // (label-title-only) счёл бы чекбокс подписанным только описанием.
              aria-labelledby={marketingConsentLabelId}
              aria-describedby={hasMarketingConsentError ? marketingConsentErrorId : undefined}
              className={hasMarketingConsentError ? consentErrorClassName : undefined}
            />
            <label
              id={marketingConsentLabelId}
              htmlFor={marketingConsentId}
              className="text-body-s text-text-primary cursor-pointer select-none"
            >
              Я даю согласие на получение информационных и рекламных рассылок от OPTISPORT по
              электронной почте
            </label>
          </div>
          {errors.marketing_consent?.message && (
            <p
              id={marketingConsentErrorId}
              className="text-body-xs text-[var(--color-accent-danger)]"
              role="alert"
            >
              {errors.marketing_consent.message}
            </p>
          )}
        </div>
      </div>
      <Button
        type="submit"
        variant="primary"
        disabled={isSubmitting || !pdpConsent}
        loading={isSubmitting}
        className="w-full"
      >
        {isSubmitting ? 'Отправка...' : 'Подписаться'}
      </Button>
    </form>
  );
};
