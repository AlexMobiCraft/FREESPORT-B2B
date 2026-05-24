/**
 * Electric Subscribe Form Component
 * Форма подписки на email-рассылку в стиле Electric Orange
 */

'use client';

import React from 'react';
import Link from 'next/link';
import { useForm } from 'react-hook-form';
import { toast } from 'react-hot-toast';
import { subscribeService } from '@/services/subscribeService';
import { ElectricButton } from '@/components/ui/Button/ElectricButton';
import { cn } from '@/utils/cn';

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

export const ElectricSubscribeForm: React.FC = () => {
  const formBaseId = React.useId();
  const emailId = `${formBaseId}-electric-email-subscribe`;
  const pdpConsentId = `${formBaseId}-electric-subscribe-pdp-consent`;
  const pdpConsentLabelPrefixId = `${formBaseId}-electric-subscribe-pdp-consent-label-prefix`;
  const pdpConsentPolicyLinkId = `${formBaseId}-electric-subscribe-pdp-consent-policy-link`;
  const pdpConsentLabelSuffixId = `${formBaseId}-electric-subscribe-pdp-consent-label-suffix`;
  const pdpConsentErrorId = `${formBaseId}-electric-subscribe-pdp-consent-error`;

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
      if (error instanceof Error && error.message === 'validation_error') {
        const pdpConsentError = getBackendFieldError(error, 'pdp_consent');
        const emailError = getBackendFieldError(error, 'email');
        const backendError = getFirstBackendError(error);

        if (pdpConsentError) {
          setError('pdp_consent', { type: 'server', message: pdpConsentError });
        }
        if (emailError) {
          setError('email', { type: 'server', message: emailError });
        }

        toast.error(
          pdpConsentError ?? emailError ?? backendError ?? 'ОШИБКА ПОДПИСКИ',
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
            {...register('email', {
              required: 'Email обязателен',
              pattern: {
                value: /^[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}$/i,
                message: 'Введите корректный email',
              },
            })}
          />
        </div>
        {errors.email && (
          <p className="text-red-500 text-xs font-bold uppercase mt-1">{errors.email.message}</p>
        )}
      </div>

      <div className="space-y-2">
        <div className="flex items-start gap-3">
          <div className="relative flex items-center pt-0.5">
            <input
              id={pdpConsentId}
              type="checkbox"
              className="sr-only peer"
              disabled={isSubmitting}
              name={pdpConsentRegistration.name}
              ref={pdpConsentRegistration.ref}
              onBlur={pdpConsentRegistration.onBlur}
              checked={pdpConsent}
              onChange={pdpConsentRegistration.onChange}
              aria-invalid={hasPdpConsentError || undefined}
              aria-labelledby={`${pdpConsentLabelPrefixId} ${pdpConsentPolicyLinkId} ${pdpConsentLabelSuffixId}`}
              aria-describedby={hasPdpConsentError ? pdpConsentErrorId : undefined}
            />
            <label
              htmlFor={pdpConsentId}
              className={cn(
                'flex h-5 w-5 cursor-pointer items-center justify-center border-2 transition-all duration-150',
                'transform -skew-x-12',
                'peer-checked:border-[var(--color-primary)] peer-checked:bg-[var(--color-primary)]',
                'peer-focus:ring-2 peer-focus:ring-[var(--color-primary)]/30 peer-focus:ring-offset-2',
                hasPdpConsentError
                  ? 'border-red-500 peer-focus:ring-red-500/30'
                  : 'border-[var(--color-primary)] hover:bg-[var(--color-primary)]/15',
                isSubmitting && 'cursor-not-allowed opacity-50'
              )}
            >
              {pdpConsent && (
                <span className="transform skew-x-12 text-xs font-bold text-black">✓</span>
              )}
            </label>
          </div>
          <span className="font-inter text-xs md:text-sm uppercase leading-relaxed text-[var(--color-text-secondary)]">
            <label id={pdpConsentLabelPrefixId} htmlFor={pdpConsentId} className="cursor-pointer">
              Я даю согласие на
            </label>{' '}
            <Link
              id={pdpConsentPolicyLinkId}
              href="/privacy-policy"
              target="_blank"
              rel="noopener noreferrer"
              className="text-[var(--color-primary)] underline hover:text-[var(--foreground)]"
            >
              обработку моих персональных данных
            </Link>{' '}
            <label id={pdpConsentLabelSuffixId} htmlFor={pdpConsentId} className="cursor-pointer">
              в соответствии с Политикой
            </label>
          </span>
        </div>
        {errors.pdp_consent?.message && (
          <p
            id={pdpConsentErrorId}
            className="text-red-500 text-xs font-bold uppercase mt-1"
            role="alert"
          >
            {errors.pdp_consent.message}
          </p>
        )}
      </div>

      <ElectricButton
        type="submit"
        variant="primary"
        size="lg"
        disabled={isSubmitting}
        className="w-full"
      >
        {isSubmitting ? 'ОТПРАВКА...' : 'ПОДПИСАТЬСЯ'}
      </ElectricButton>
    </form>
  );
};
