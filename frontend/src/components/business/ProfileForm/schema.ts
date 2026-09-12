/**
 * Profile Form Validation Schema
 * Zod схема валидации для формы профиля
 * Story 16.1 - AC: 2
 */

import { z } from 'zod';

/**
 * Базовая схема профиля (общие поля для всех пользователей)
 */
const baseProfileSchema = z.object({
  email: z.string().email('Некорректный формат email'),
  first_name: z
    .string()
    .min(1, 'Имя обязательно для заполнения')
    .max(50, 'Имя не должно превышать 50 символов'),
  last_name: z
    .string()
    .min(1, 'Фамилия обязательна для заполнения')
    .max(50, 'Фамилия не должна превышать 50 символов'),
  phone: z.string().regex(/^\+7\d{10}$/, 'Телефон должен быть в формате +79001234567'),
});

/**
 * Схема B2B полей (для оптовых покупателей, тренеров, федераций)
 */
const b2bFieldsSchema = z.object({
  company_name: z
    .string()
    .max(100, 'Название компании не должно превышать 100 символов')
    .optional()
    .or(z.literal('')),
  tax_id: z
    .string()
    .regex(/^(\d{10}|\d{12})?$/, 'ИНН должен содержать 10 или 12 цифр')
    .optional()
    .or(z.literal('')),
});

/**
 * Полная схема профиля (базовые + B2B поля)
 */
export const profileSchema = baseProfileSchema.merge(b2bFieldsSchema);

/**
 * Тип данных формы профиля
 */
export type ProfileFormData = z.infer<typeof profileSchema>;

/**
 * Дефолтные значения для формы
 */
export const defaultProfileValues: ProfileFormData = {
  email: '',
  first_name: '',
  last_name: '',
  phone: '',
  company_name: '',
  tax_id: '',
};
