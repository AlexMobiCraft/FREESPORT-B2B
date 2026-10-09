/**
 * Zod схема валидации для формы адреса
 * Story 16.3: Управление адресами доставки
 */

import { z } from 'zod';

/**
 * Схема валидации адреса
 * Соответствует backend модели Address (max_length=12 для phone)
 */
export const addressSchema = z.object({
  address_type: z.enum(['shipping', 'legal'], {
    message: 'Выберите тип адреса',
  }),
  full_name: z
    .string()
    .min(2, 'Имя должно содержать минимум 2 символа')
    .max(255, 'Имя слишком длинное'),
  phone: z.string().regex(/^\+7\d{10}$/, 'Формат телефона: +79001234567'),
  city: z
    .string()
    .min(2, 'Название города должно содержать минимум 2 символа')
    .max(100, 'Название города слишком длинное'),
  street: z
    .string()
    .min(2, 'Название улицы должно содержать минимум 2 символа')
    .max(255, 'Название улицы слишком длинное'),
  building: z.string().min(1, 'Номер дома обязателен').max(20, 'Номер дома слишком длинный'),
  building_section: z
    .string()
    .max(20, 'Корпус/строение слишком длинное')
    .optional()
    .or(z.literal('')),
  apartment: z.string().max(20, 'Номер квартиры слишком длинный').optional().or(z.literal('')),
  postal_code: z.string().regex(/^\d{6}$/, 'Почтовый индекс должен содержать 6 цифр'),
  is_default: z.boolean().default(false),
});

export type AddressSchemaType = z.infer<typeof addressSchema>;

/**
 * Значения формы по умолчанию
 */
export const defaultAddressFormValues: AddressSchemaType = {
  address_type: 'shipping',
  full_name: '',
  phone: '',
  city: '',
  street: '',
  building: '',
  building_section: '',
  apartment: '',
  postal_code: '',
  is_default: false,
};
