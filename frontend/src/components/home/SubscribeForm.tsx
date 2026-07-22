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

interface SubscribeFormData {
  email: string;
  pdp_consent: boolean;
}

type SubscribeFormField = keyof SubscribeFormData;
type SubscribeValidationDetails = Record<string, string[]>;
type SubscribeValidationError = Error & {
  details?: SubscribeValidationDetails;
};

const PDP_CONSENT_REQUIRED = 'Необходимо согласие на обработку персональных данных.';
const THROTTLED_ERROR = 'Слишком много попыток. Попробуйте через минуту.';
const SERVER_TEMPORARILY_UNAVAILABLE = 'Сервер временно недоступен. Попробуйте позже';

const getBackendMessage = (value: string[] | undefined) => value?.[0];

const getBackendFieldError = (error: unknown, field: SubscribeFormField) => {
  if (!(error instanceof Error) || !('details' in error)) {
    return undefined;
  }

  return getBackendMessage((error as SubscribeValidationError).details?.[field]);
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

  const {
    register,
    handleSubmit,
    watch,
    setError,
    clearErrors,
    formState: { errors, isSubmitting },
    reset,
  } = useForm<SubscribeFormData>({
    defaultValues: { email: '', pdp_consent: false },
  });

  const pdpConsent = watch('pdp_consent');
  const pdpConsentRegistration = register('pdp_consent', {
    required: PDP_CONSENT_REQUIRED,
  });
  const hasPdpConsentError = !!errors.pdp_consent;

  const onSubmit = async (data: SubscribeFormData) => {
    clearErrors('pdp_consent');

    try {
      await subscribeService.subscribe({
        email: data.email,
        pdp_consent: data.pdp_consent,
      });
      toast.success('Вы успешно подписались на рассылку');
      reset();
    } catch (error: unknown) {
      if (error instanceof Error) {
        if (error.message === 'validation_error') {
          const pdpConsentError = getBackendFieldError(error, 'pdp_consent');
          const emailError = getBackendFieldError(error, 'email');
          const backendError = getFirstBackendError(error);

          if (pdpConsentError) {
            setError('pdp_consent', { type: 'server', message: pdpConsentError });
          }
          if (emailError) {
            setError('email', { type: 'server', message: emailError });
          }

          toast.error(pdpConsentError ?? emailError ?? backendError ?? 'Введите корректный email');
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
        placeholder="your@email.com"
        error={errors.email?.message}
        aria-required="true"
        aria-invalid={!!errors.email}
        {...register('email', {
          required: 'Email обязателен',
          pattern: {
            value: /^[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}$/i,
            message: 'Введите корректный email',
          },
        })}
      />
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
            aria-invalid={hasPdpConsentError || undefined}
            aria-labelledby={`${pdpConsentLabelPrefixId} ${pdpConsentPolicyLinkId}`}
            aria-describedby={hasPdpConsentError ? pdpConsentErrorId : undefined}
            className={
              hasPdpConsentError
                ? 'border-[var(--color-accent-danger)] bg-[var(--color-accent-danger)]/8 peer-focus:ring-[var(--color-accent-danger)]'
                : undefined
            }
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
              «Политикой обработки персональных данных ООО „Фриспорт“»
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
      <Button
        type="submit"
        variant="primary"
        disabled={isSubmitting}
        loading={isSubmitting}
        className="w-full"
      >
        {isSubmitting ? 'Отправка...' : 'Подписаться'}
      </Button>
    </form>
  );
};
