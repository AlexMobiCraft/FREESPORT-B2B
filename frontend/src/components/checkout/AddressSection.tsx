'use client';

import { UseFormReturn } from 'react-hook-form';
import { CheckoutFormData, CheckoutFormInput } from '@/schemas/checkoutSchema';
import { Input, Checkbox } from '@/components/ui';
import { AddressCardOption } from './AddressCardOption';
import type { Address } from '@/types/address';

export interface AddressSectionProps {
  form: UseFormReturn<CheckoutFormInput, unknown, CheckoutFormData>;
  /** Список сохранённых shipping-адресов авторизованного пользователя */
  addresses?: Address[];
  /** ID выбранного адреса в селекторе (null — нет выбора, ввод вручную) */
  selectedAddressId?: number | null;
  /** Колбэк выбора адреса в селекторе */
  onSelectAddress?: (id: number) => void;
  /** Показывать ли чекбокс «запомнить адрес» */
  showSaveCheckbox?: boolean;
  /** Текущее состояние чекбокса «запомнить адрес» */
  saveAddress?: boolean;
  /** Колбэк переключения чекбокса */
  onToggleSaveAddress?: (value: boolean) => void;
}

/**
 * Секция адреса доставки для формы checkout.
 *
 * Поля:
 * - Город, Улица, Дом (обяз.), Корпус, Квартира, Индекс
 *
 * UX:
 * - Если переданы 2+ сохранённых адреса — рендерим селектор-карточки над полями
 * - Если showSaveCheckbox=true — рендерим чекбокс «запомнить адрес» под полями
 * - Иначе — стандартная форма ввода
 */
export function AddressSection({
  form,
  addresses,
  selectedAddressId,
  onSelectAddress,
  showSaveCheckbox = false,
  saveAddress = false,
  onToggleSaveAddress,
}: AddressSectionProps) {
  const {
    register,
    formState: { errors },
  } = form;

  const showSelector = !!addresses && addresses.length > 1 && !!onSelectAddress;

  return (
    <section
      className="rounded-[var(--radius)] bg-[var(--bg-panel)] p-6 shadow-[var(--shadow-default)]"
      aria-labelledby="address-section"
    >
      <h2 id="address-section" className="mb-4 text-lg font-semibold text-text-primary">
        Адрес доставки
      </h2>

      {/* Селектор сохранённых адресов */}
      {showSelector && (
        <div
          className="mb-6"
          role="radiogroup"
          aria-label="Выберите сохранённый адрес"
          data-testid="address-selector"
        >
          <p className="mb-2 text-sm font-medium text-text-secondary">Выберите сохранённый адрес</p>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {addresses!.map(addr => (
              <AddressCardOption
                key={addr.id}
                address={addr}
                selected={addr.id === selectedAddressId}
                onSelect={onSelectAddress!}
              />
            ))}
          </div>
        </div>
      )}

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

        {/* Дом, Корпус и Квартира */}
        <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
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

        {/* Чекбокс «запомнить адрес» */}
        {showSaveCheckbox && (
          <div className="pt-2" data-testid="save-address-checkbox-wrapper">
            <Checkbox
              label="Запомнить этот адрес в профиле"
              checked={saveAddress}
              onChange={e => onToggleSaveAddress?.(e.target.checked)}
            />
          </div>
        )}
      </div>
    </section>
  );
}
