'use client';

import { UseFormReturn } from 'react-hook-form';
import { CheckoutFormData, CheckoutFormInput } from '@/schemas/checkoutSchema';
import { Input } from '@/components/ui';

export interface AddressSectionProps {
  form: UseFormReturn<CheckoutFormInput, unknown, CheckoutFormData>;
}

/**
 * Секция адреса доставки для формы checkout
 *
 * Story 15.1: Checkout страница и упрощённая форма
 *
 * Поля:
 * - Город (обязательно, минимум 2 символа)
 * - Улица (обязательно, минимум 3 символа)
 * - Дом (обязательно)
 * - Квартира (опционально)
 * - Индекс (обязательно, 6 цифр)
 *
 * Автозаполнение:
 * - Для авторизованных пользователей данные берутся из user.addresses[0] (если есть)
 */
export function AddressSection({ form }: AddressSectionProps) {
  const {
    register,
    formState: { errors },
  } = form;

  return (
    <section className="rounded-lg bg-white p-6 shadow-sm" aria-labelledby="address-section">
      <h2 id="address-section" className="mb-4 text-lg font-semibold text-gray-900">
        Адрес доставки
      </h2>

      <div className="grid grid-cols-1 gap-4">
        {/* Город */}
        <div>
          <Input
            {...register('city')}
            label="Город"
            type="text"
            placeholder="Москва"
            error={errors.city?.message}
            aria-required="true"
            aria-invalid={!!errors.city}
            aria-describedby={errors.city ? 'city-error' : undefined}
            autoComplete="address-level2"
          />
          {errors.city && (
            <p id="city-error" className="sr-only">
              {errors.city.message}
            </p>
          )}
        </div>

        {/* Улица */}
        <div>
          <Input
            {...register('street')}
            label="Улица"
            type="text"
            placeholder="Ленина"
            error={errors.street?.message}
            aria-required="true"
            aria-invalid={!!errors.street}
            aria-describedby={errors.street ? 'street-error' : undefined}
            autoComplete="address-line1"
          />
          {errors.street && (
            <p id="street-error" className="sr-only">
              {errors.street.message}
            </p>
          )}
        </div>

        {/* Дом, Корпус и Квартира в одной строке на desktop */}
        <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
          {/* Дом */}
          <div>
            <Input
              {...register('house')}
              label="Дом"
              type="text"
              placeholder="10"
              error={errors.house?.message}
              aria-required="true"
              aria-invalid={!!errors.house}
              aria-describedby={errors.house ? 'house-error' : undefined}
              autoComplete="address-line2"
            />
            {errors.house && (
              <p id="house-error" className="sr-only">
                {errors.house.message}
              </p>
            )}
          </div>

          {/* Корпус */}
          <div>
            <Input
              {...register('buildingSection')}
              label="Корпус"
              type="text"
              placeholder="А"
              error={errors.buildingSection?.message}
              aria-invalid={!!errors.buildingSection}
              aria-describedby={errors.buildingSection ? 'buildingSection-error' : undefined}
            />
            {errors.buildingSection && (
              <p id="buildingSection-error" className="sr-only">
                {errors.buildingSection.message}
              </p>
            )}
          </div>

          {/* Квартира */}
          <div>
            <Input
              {...register('apartment')}
              label="Кв./офис"
              type="text"
              placeholder="25"
              error={errors.apartment?.message}
              aria-invalid={!!errors.apartment}
              aria-describedby={errors.apartment ? 'apartment-error' : undefined}
              autoComplete="address-line3"
            />
            {errors.apartment && (
              <p id="apartment-error" className="sr-only">
                {errors.apartment.message}
              </p>
            )}
          </div>
        </div>

        {/* Индекс */}
        <div className="md:w-1/2">
          <Input
            {...register('postalCode')}
            label="Почтовый индекс"
            type="text"
            placeholder="123456"
            error={errors.postalCode?.message}
            helper="6 цифр"
            aria-required="true"
            aria-invalid={!!errors.postalCode}
            aria-describedby={errors.postalCode ? 'postalCode-error' : undefined}
            autoComplete="postal-code"
            maxLength={6}
          />
          {errors.postalCode && (
            <p id="postalCode-error" className="sr-only">
              {errors.postalCode.message}
            </p>
          )}
        </div>
      </div>
    </section>
  );
}
