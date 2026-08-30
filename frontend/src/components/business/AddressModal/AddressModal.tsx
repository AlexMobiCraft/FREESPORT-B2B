/**
 * AddressModal Component - Модальное окно для добавления/редактирования адреса
 * Story 16.3: Управление адресами доставки (AC: 1, 2)
 *
 * Форма с валидацией через React Hook Form + Zod
 */

'use client';

import React, { useEffect } from 'react';
import { useForm, Controller } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import type { z } from 'zod';
import { Modal } from '@/components/ui/Modal/Modal';
import { Input, PhoneInput } from '@/components/ui';
import { Button } from '@/components/ui';
import { addressSchema, defaultAddressFormValues } from '@/schemas/addressSchema';
import type { Address } from '@/types/address';

type AddressFormValues = z.input<typeof addressSchema>;

export interface AddressModalProps {
  /** Открыт ли модал */
  isOpen: boolean;
  /** Callback закрытия */
  onClose: () => void;
  /** Адрес для редактирования (если передан - режим редактирования) */
  address?: Address;
  /** Callback создания нового адреса */
  onCreate?: (data: AddressFormValues) => Promise<void>;
  /** Callback обновления адреса */
  onUpdate?: (id: number, data: AddressFormValues) => Promise<void>;
  /** Флаг состояния сохранения */
  isSaving?: boolean;
}

/**
 * Модальное окно для создания/редактирования адреса
 */
export const AddressModal: React.FC<AddressModalProps> = ({
  isOpen,
  onClose,
  address,
  onCreate,
  onUpdate,
  isSaving = false,
}) => {
  const isEditMode = !!address;

  const {
    control,
    handleSubmit,
    reset,
    formState: { errors, isValid },
  } = useForm<AddressFormValues>({
    resolver: zodResolver(addressSchema),
    mode: 'onBlur',
    reValidateMode: 'onChange',
    defaultValues: defaultAddressFormValues,
  });

  // Сброс формы при открытии/закрытии или смене адреса
  useEffect(() => {
    if (isOpen) {
      if (address) {
        reset({
          address_type: address.address_type,
          full_name: address.full_name,
          phone: address.phone,
          city: address.city,
          street: address.street,
          building: address.building,
          building_section: address.building_section || '',
          apartment: address.apartment || '',
          postal_code: address.postal_code,
          is_default: address.is_default,
        });
      } else {
        reset(defaultAddressFormValues);
      }
    }
  }, [isOpen, address, reset]);

  /**
   * Обработчик отправки формы
   */
  const onSubmit = async (data: AddressFormValues) => {
    try {
      if (isEditMode && address && onUpdate) {
        await onUpdate(address.id, data);
      } else if (onCreate) {
        await onCreate(data);
      }
      onClose();
    } catch (error) {
      // Ошибка обрабатывается в родительском компоненте
      console.error('Address save error:', error);
    }
  };

  const handleClose = () => {
    if (!isSaving) {
      onClose();
    }
  };

  return (
    <Modal
      isOpen={isOpen}
      onClose={handleClose}
      title={isEditMode ? 'Редактировать адрес' : 'Новый адрес'}
      size="md"
      closeOnBackdrop={!isSaving}
      closeOnEscape={!isSaving}
    >
      <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
        {/* Тип адреса */}
        <Controller
          name="address_type"
          control={control}
          render={({ field }) => (
            <div>
              <label className="block text-[14px] font-medium text-[var(--color-text-primary)] mb-2">
                Тип адреса
              </label>
              <div className="flex gap-4">
                <label className="flex items-center gap-2 cursor-pointer">
                  <input
                    type="radio"
                    {...field}
                    value="shipping"
                    checked={field.value === 'shipping'}
                    className="w-4 h-4 text-[var(--color-primary)]"
                  />
                  <span className="text-[14px] text-[var(--color-text-primary)]">
                    Адрес доставки
                  </span>
                </label>
                <label className="flex items-center gap-2 cursor-pointer">
                  <input
                    type="radio"
                    {...field}
                    value="legal"
                    checked={field.value === 'legal'}
                    className="w-4 h-4 text-[var(--color-primary)]"
                  />
                  <span className="text-[14px] text-[var(--color-text-primary)]">
                    Юридический адрес
                  </span>
                </label>
              </div>
              {errors.address_type && (
                <p className="text-[12px] text-[var(--color-accent-danger)] mt-1">
                  {errors.address_type.message}
                </p>
              )}
            </div>
          )}
        />

        {/* Полное имя */}
        <Controller
          name="full_name"
          control={control}
          render={({ field }) => (
            <Input
              label="Полное имя получателя"
              placeholder="Иван Иванов"
              error={errors.full_name?.message}
              {...field}
            />
          )}
        />

        {/* Телефон */}
        <Controller
          name="phone"
          control={control}
          render={({ field }) => (
            <PhoneInput
              label="Телефон"
              placeholder="+79001234567"
              error={errors.phone?.message}
              {...field}
            />
          )}
        />

        {/* Город и Индекс */}
        <div className="grid grid-cols-2 gap-4">
          <Controller
            name="city"
            control={control}
            render={({ field }) => (
              <Input label="Город" placeholder="Москва" error={errors.city?.message} {...field} />
            )}
          />
          <Controller
            name="postal_code"
            control={control}
            render={({ field }) => (
              <Input
                label="Почтовый индекс"
                placeholder="123456"
                error={errors.postal_code?.message}
                {...field}
              />
            )}
          />
        </div>

        {/* Улица */}
        <Controller
          name="street"
          control={control}
          render={({ field }) => (
            <Input label="Улица" placeholder="Тверская" error={errors.street?.message} {...field} />
          )}
        />

        {/* Дом, Корпус и Квартира */}
        <div className="grid grid-cols-3 gap-4">
          <Controller
            name="building"
            control={control}
            render={({ field }) => (
              <Input label="Дом" placeholder="12" error={errors.building?.message} {...field} />
            )}
          />
          <Controller
            name="building_section"
            control={control}
            render={({ field }) => (
              <Input
                label="Корпус"
                placeholder="А"
                error={errors.building_section?.message}
                {...field}
              />
            )}
          />
          <Controller
            name="apartment"
            control={control}
            render={({ field }) => (
              <Input
                label="Кв./офис"
                placeholder="45"
                error={errors.apartment?.message}
                {...field}
              />
            )}
          />
        </div>

        {/* Адрес по умолчанию */}
        <Controller
          name="is_default"
          control={control}
          render={({ field }) => (
            <label className="flex items-center gap-2 cursor-pointer">
              <input
                type="checkbox"
                checked={field.value}
                onChange={field.onChange}
                className="w-4 h-4 rounded text-[var(--color-primary)]"
              />
              <span className="text-[14px] text-[var(--color-text-primary)]">
                Использовать как адрес по умолчанию
              </span>
            </label>
          )}
        />

        {/* TODO: Add DaData autocomplete in future iteration */}

        {/* Кнопки */}
        <div className="flex justify-end gap-3 pt-4 border-t border-[var(--color-neutral-300)]">
          <Button type="button" variant="secondary" onClick={handleClose} disabled={isSaving}>
            Отмена
          </Button>
          <Button
            type="submit"
            variant="primary"
            loading={isSaving}
            disabled={!isValid || isSaving}
          >
            {isEditMode ? 'Сохранить' : 'Добавить'}
          </Button>
        </div>
      </form>
    </Modal>
  );
};

AddressModal.displayName = 'AddressModal';

export default AddressModal;
