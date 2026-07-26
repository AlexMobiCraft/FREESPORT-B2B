/**
 * Auth Validation Schemas (Zod)
 * Story 28.1 - Базовая аутентификация и регистрация B2C
 * Story 28.2 - Поток регистрации B2B
 *
 * Schemas для валидации форм логина и регистрации
 */

import { z } from 'zod';
import { validateINN, validateOGRN } from '@/utils/validators/b2b-validators';

const PDP_CONSENT_REQUIRED_MESSAGE = 'Необходимо согласие на обработку персональных данных.';

const pdpConsentSchema = z
  .boolean({ error: PDP_CONSENT_REQUIRED_MESSAGE })
  .pipe(z.literal(true, { error: PDP_CONSENT_REQUIRED_MESSAGE }));

/**
 * Login Schema
 * Валидация формы входа
 *
 * AC 3: Email format validation, password min 8 chars, 1 digit, 1 uppercase
 */
export const loginSchema = z.object({
  email: z.string().min(1, 'Email обязателен').email('Неверный формат email'),
  password: z
    .string()
    .min(8, 'Пароль должен содержать минимум 8 символов')
    .regex(/[0-9]/, 'Пароль должен содержать хотя бы 1 цифру')
    .regex(/[A-Z]/, 'Пароль должен содержать хотя бы 1 заглавную букву'),
});

/**
 * Register Schema
 * Валидация формы регистрации
 *
 * Story 28.1: AC 2, 3 - Name, Email, Password, Confirm Password validation
 * Story 29.1: AC 1, 8 - Role selection с условными B2B полями
 */
export const registerSchema = z
  .object({
    first_name: z
      .string()
      .min(1, 'Имя обязательно')
      .max(150, 'Имя не должно превышать 150 символов'),
    email: z.string().min(1, 'Email обязателен').email('Неверный формат email'),
    password: z
      .string()
      .min(8, 'Пароль должен содержать минимум 8 символов')
      .regex(/[0-9]/, 'Пароль должен содержать хотя бы 1 цифру')
      .regex(/[A-Z]/, 'Пароль должен содержать хотя бы 1 заглавную букву'),
    confirmPassword: z.string().min(1, 'Подтверждение пароля обязательно'),
    // Story 29.1: Role selection
    role: z.enum(['retail', 'trainer', 'wholesale_level1', 'federation_rep']).default('retail'),
    // Story 29.1: Условные B2B поля
    company_name: z.string().optional(),
    tax_id: z.string().optional(),
    // Страна регистрации B2B — по ней (или коду субъекта РФ из ИНН) заявка
    // маршрутизируется на регионального менеджера. Показывается для B2B-ролей.
    country: z.enum(['Россия', 'Беларусь', 'Казахстан']).default('Россия'),
    pdp_consent: pdpConsentSchema,
    marketing_consent: z.boolean().default(false),
  })
  .refine(data => data.password === data.confirmPassword, {
    message: 'Пароли не совпадают',
    path: ['confirmPassword'],
  })
  .refine(
    data => {
      // Story 29.1: AC 8 - company_name обязательно для всех B2B ролей
      if (data.role !== 'retail' && (!data.company_name || data.company_name.trim() === '')) {
        return false;
      }
      return true;
    },
    {
      message: 'Название компании обязательно для B2B регистрации',
      path: ['company_name'],
    }
  )
  .refine(
    data => {
      // tax_id обязателен для всех B2B ролей, включая trainer: без ИНН
      // бэкенд не может найти существующего клиента из 1С и создает дубль.
      if (data.role !== 'retail' && (!data.tax_id || data.tax_id.trim() === '')) {
        return false;
      }
      return true;
    },
    {
      message: 'ИНН обязателен для B2B регистрации',
      path: ['tax_id'],
    }
  )
  .refine(
    data => {
      // Маска российского ИНН применима только к клиентам из РФ:
      // у Беларуси УНП — 9 цифр, у Казахстана БИН/ИИН — 12.
      const taxId = data.tax_id?.trim();
      if (data.role === 'retail' || !taxId) {
        return true;
      }
      return data.country === 'Россия' ? validateINN(taxId) : /^\d{8,12}$/.test(taxId);
    },
    {
      message:
        'ИНН должен содержать 10 цифр (юр. лицо) или 12 цифр (ИП); для Беларуси и Казахстана — от 8 до 12 цифр',
      path: ['tax_id'],
    }
  );

/**
 * B2B Register Schema
 * Story 28.2 - Валидация формы регистрации B2B
 *
 * AC 1, 2: Поля B2B регистрации с валидацией ИНН/ОГРН
 */
export const b2bRegisterSchema = z
  .object({
    // Персональные данные контактного лица
    first_name: z
      .string()
      .min(1, 'Имя обязательно')
      .max(150, 'Имя не должно превышать 150 символов'),
    last_name: z
      .string()
      .min(1, 'Фамилия обязательна')
      .max(150, 'Фамилия не должна превышать 150 символов'),
    email: z.string().min(1, 'Email обязателен').email('Неверный формат email'),
    phone: z
      .string()
      .min(1, 'Телефон обязателен')
      .regex(/^[\d\s\+\-\(\)]+$/, 'Неверный формат телефона'),

    // Пароль
    password: z
      .string()
      .min(8, 'Пароль должен содержать минимум 8 символов')
      .regex(/[0-9]/, 'Пароль должен содержать хотя бы 1 цифру')
      .regex(/[A-Z]/, 'Пароль должен содержать хотя бы 1 заглавную букву'),
    confirmPassword: z.string().min(1, 'Подтверждение пароля обязательно'),

    // Реквизиты компании
    company_name: z
      .string()
      .min(1, 'Название компании обязательно')
      .max(255, 'Название компании не должно превышать 255 символов'),
    tax_id: z.string().min(1, 'ИНН обязателен').refine(validateINN, {
      message: 'ИНН должен содержать 10 цифр (юр. лицо) или 12 цифр (ИП)',
    }),
    ogrn: z.string().min(1, 'ОГРН обязателен').refine(validateOGRN, {
      message: 'ОГРН должен содержать 13 цифр (юр. лицо) или 15 цифр (ОГРНИП)',
    }),
    legal_address: z
      .string()
      .min(1, 'Юридический адрес обязателен')
      .max(500, 'Юридический адрес не должен превышать 500 символов'),

    // Страна регистрации — по ней (или коду субъекта РФ из ИНН) заявка
    // маршрутизируется на регионального менеджера.
    country: z.enum(['Россия', 'Беларусь', 'Казахстан']).default('Россия'),

    // Роль B2B (опционально, может задаваться при выборе)
    role: z.enum([
      'wholesale_level1',
      'wholesale_level2',
      'wholesale_level3',
      'trainer',
      'federation_rep',
    ]),
    pdp_consent: pdpConsentSchema,
    marketing_consent: z.boolean().default(false),
  })
  .refine(data => data.password === data.confirmPassword, {
    message: 'Пароли не совпадают',
    path: ['confirmPassword'],
  });

/**
 * Password Reset Request Schema
 * Story 28.3 - Восстановление пароля
 *
 * AC 1, 4: Email validation для запроса сброса пароля
 */
export const passwordResetRequestSchema = z.object({
  email: z.string().min(1, 'Email обязателен').email('Введите корректный email'),
});

/**
 * Password Reset Confirm Schema
 * Story 28.3 - Восстановление пароля
 *
 * AC 2, 4: Валидация нового пароля и подтверждения
 * Password strength requirements: минимум 8 символов, 1 цифра, 1 заглавная буква
 */
export const passwordResetConfirmSchema = z
  .object({
    password: z
      .string()
      .min(8, 'Пароль должен содержать минимум 8 символов')
      .regex(/[0-9]/, 'Пароль должен содержать хотя бы 1 цифру')
      .regex(/[A-Z]/, 'Пароль должен содержать хотя бы 1 заглавную букву'),
    confirmPassword: z.string().min(1, 'Подтверждение пароля обязательно'),
  })
  .refine(data => data.password === data.confirmPassword, {
    message: 'Пароли не совпадают',
    path: ['confirmPassword'],
  });

/**
 * TypeScript Types (инференция из Zod schemas)
 */
export type LoginFormData = z.infer<typeof loginSchema>;
export type RegisterFormInput = z.input<typeof registerSchema>;
export type RegisterFormData = z.output<typeof registerSchema>;
export type B2BRegisterFormInput = z.input<typeof b2bRegisterSchema>;
export type B2BRegisterFormData = z.output<typeof b2bRegisterSchema>;
export type PasswordResetRequestFormData = z.infer<typeof passwordResetRequestSchema>;
export type PasswordResetConfirmFormData = z.infer<typeof passwordResetConfirmSchema>;
