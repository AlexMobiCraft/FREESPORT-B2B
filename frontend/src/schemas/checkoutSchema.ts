import { z } from 'zod';

/**
 * Zod схема валидации формы оформления заказа
 *
 * Включает все необходимые поля для checkout процесса:
 * - Контактные данные (email, телефон, имя, фамилия)
 * - Адрес доставки (город, улица, дом, квартира, индекс)
 * - Способ доставки (placeholder для Story 15.3)
 * - Комментарий к заказу (опционально)
 */
export const checkoutSchema = z.object({
  // ========== Контактные данные ==========
  email: z.string().min(1, 'Email обязателен').email('Некорректный формат email'),

  phone: z.string().regex(/^\+7\d{10}$/, 'Формат: +7XXXXXXXXXX (например, +79001234567)'),

  firstName: z.string().min(2, 'Минимум 2 символа').max(50, 'Максимум 50 символов'),

  lastName: z.string().min(2, 'Минимум 2 символа').max(50, 'Максимум 50 символов'),

  // ========== Адрес доставки ==========
  city: z.string().min(2, 'Минимум 2 символа').max(100, 'Максимум 100 символов'),

  street: z.string().min(3, 'Минимум 3 символа').max(200, 'Максимум 200 символов'),

  house: z.string().min(1, 'Обязательное поле').max(20, 'Максимум 20 символов'),

  buildingSection: z.string().max(20, 'Максимум 20 символов').optional(),

  apartment: z.string().max(20, 'Максимум 20 символов').optional(),

  postalCode: z
    .string()
    .regex(/^\d{6}$/, 'Индекс должен содержать ровно 6 цифр (например, 123456)'),

  // ========== Способ доставки ==========
  // Placeholder для Story 15.3 - полная реализация будет позже
  deliveryMethod: z.string().min(1, 'Выберите способ доставки'),

  // ========== Способ оплаты ==========
  paymentMethod: z.string().default('payment_on_delivery'),

  // ========== Комментарий к заказу ==========
  comment: z.string().max(500, 'Максимум 500 символов').optional().default(''),
});

/**
 * TypeScript тип, автоматически выведенный из Zod схемы
 * Используется для типизации данных формы
 */
export type CheckoutFormInput = z.input<typeof checkoutSchema>;
export type CheckoutFormData = z.infer<typeof checkoutSchema>;

/**
 * Значения по умолчанию для пустой формы
 * Используется для неавторизованных пользователей
 */
export const defaultCheckoutFormValues: CheckoutFormData = {
  email: '',
  phone: '',
  firstName: '',
  lastName: '',
  city: '',
  street: '',
  house: '',
  buildingSection: '',
  apartment: '',
  postalCode: '',
  deliveryMethod: '',
  paymentMethod: 'payment_on_delivery',
  comment: '',
};
