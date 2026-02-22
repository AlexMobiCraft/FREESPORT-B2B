'use client';

import { UseFormReturn } from 'react-hook-form';
import { CheckoutFormData, CheckoutFormInput } from '@/schemas/checkoutSchema';
import { Input, PhoneInput } from '@/components/ui';

export interface ContactSectionProps {
  form: UseFormReturn<CheckoutFormInput, unknown, CheckoutFormData>;
}

/**
 * Секция контактных данных для формы checkout
 *
 * Story 15.1: Checkout страница и упрощённая форма
 *
 * Поля:
 * - Email (обязательно, формат email)
 * - Телефон (обязательно, формат +7XXXXXXXXXX)
 * - Имя (обязательно, минимум 2 символа)
 * - Фамилия (обязательно, минимум 2 символа)
 *
 * Автозаполнение:
 * - Для авторизованных пользователей данные берутся из authStore.user
 */
export function ContactSection({ form }: ContactSectionProps) {
  const {
    register,
    formState: { errors },
  } = form;

  return (
    <section className="rounded-lg bg-white p-6 shadow-sm" aria-labelledby="contact-section">
      <h2 id="contact-section" className="mb-4 text-lg font-semibold text-gray-900">
        Контактные данные
      </h2>

      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        {/* Email */}
        <div className="md:col-span-2">
          <Input
            {...register('email')}
            label="Email"
            type="email"
            placeholder="example@mail.com"
            error={errors.email?.message}
            aria-required="true"
            aria-invalid={!!errors.email}
            aria-describedby={errors.email ? 'email-error' : undefined}
            autoComplete="email"
          />
          {errors.email && (
            <p id="email-error" className="sr-only">
              {errors.email.message}
            </p>
          )}
        </div>

        {/* Телефон */}
        <div className="md:col-span-2">
          <PhoneInput
            {...register('phone')}
            label="Телефон"
            placeholder="+79001234567"
            error={errors.phone?.message}
            helper="Формат: +7XXXXXXXXXX"
            aria-required="true"
            aria-invalid={!!errors.phone}
            aria-describedby={errors.phone ? 'phone-error' : undefined}
            autoComplete="tel"
          />
          {errors.phone && (
            <p id="phone-error" className="sr-only">
              {errors.phone.message}
            </p>
          )}
        </div>

        {/* Имя */}
        <div>
          <Input
            {...register('firstName')}
            label="Имя"
            type="text"
            placeholder="Иван"
            error={errors.firstName?.message}
            aria-required="true"
            aria-invalid={!!errors.firstName}
            aria-describedby={errors.firstName ? 'firstName-error' : undefined}
            autoComplete="given-name"
          />
          {errors.firstName && (
            <p id="firstName-error" className="sr-only">
              {errors.firstName.message}
            </p>
          )}
        </div>

        {/* Фамилия */}
        <div>
          <Input
            {...register('lastName')}
            label="Фамилия"
            type="text"
            placeholder="Петров"
            error={errors.lastName?.message}
            aria-required="true"
            aria-invalid={!!errors.lastName}
            aria-describedby={errors.lastName ? 'lastName-error' : undefined}
            autoComplete="family-name"
          />
          {errors.lastName && (
            <p id="lastName-error" className="sr-only">
              {errors.lastName.message}
            </p>
          )}
        </div>
      </div>
    </section>
  );
}
