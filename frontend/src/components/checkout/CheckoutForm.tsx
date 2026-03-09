'use client';

import { useEffect } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { useRouter } from 'next/navigation';
import { User } from '@/types/api';
import {
  checkoutSchema,
  CheckoutFormData,
  CheckoutFormInput,
  defaultCheckoutFormValues,
} from '@/schemas/checkoutSchema';
import { useOrderStore } from '@/stores/orderStore';
import { useCartStore } from '@/stores/cartStore';
import { ContactSection } from './ContactSection';
import { AddressSection } from './AddressSection';
import { DeliveryOptions } from './DeliveryOptions';
import { OrderCommentSection } from './OrderCommentSection';
import { OrderSummary } from './OrderSummary';
import { InfoPanel } from '@/components/ui';

/**
 * Расширенный тип User с полем addresses для автозаполнения
 * ВАЖНО: Базовый тип User из @/types/api не содержит поле addresses
 */
interface UserAddress {
  city: string;
  street: string;
  house: string;
  apartment?: string;
  postal_code: string;
}

interface UserWithAddresses extends User {
  addresses?: UserAddress[];
}

export interface CheckoutFormProps {
  user: User | null;
}

/**
 * Главная форма оформления заказа
 *
 * Story 15.1: Checkout страница и упрощённая форма
 * Story 15.2: Интеграция с Orders API
 *
 * Функциональность:
 * - React Hook Form для управления формой
 * - Zod валидация через zodResolver
 * - Автозаполнение данных для авторизованных пользователей
 * - Интеграция с orderStore для создания заказа
 * - Адаптивная вёрстка (mobile-first)
 * - Обработка ошибок валидации и отправки
 *
 * Секции:
 * 1. ContactSection - контактные данные
 * 2. AddressSection - адрес доставки
 * 3. DeliveryOptions - способ доставки (Story 15.3b)
 * 4. OrderCommentSection - комментарий к заказу
 * 5. OrderSummary - сводка заказа (sticky sidebar на desktop)
 */
export function CheckoutForm({ user }: CheckoutFormProps) {
  const router = useRouter();

  // Order store для создания заказа
  const { createOrder, isSubmitting, error: orderError, clearOrder } = useOrderStore();

  // Cart store для проверки пустой корзины
  const { items: cartItems } = useCartStore();

  // Типизация user с addresses для автозаполнения
  const userWithAddresses = user as UserWithAddresses | null;

  // Инициализация React Hook Form с автозаполнением
  const form = useForm<CheckoutFormInput, unknown, CheckoutFormData>({
    resolver: zodResolver(checkoutSchema),
    mode: 'onBlur', // Валидация при потере фокуса для лучшего UX
    reValidateMode: 'onChange', // Ре-валидация при изменении
    defaultValues: {
      // Контактные данные - автозаполнение из user
      email: userWithAddresses?.email || defaultCheckoutFormValues.email,
      phone: userWithAddresses?.phone || defaultCheckoutFormValues.phone,
      firstName: userWithAddresses?.first_name || defaultCheckoutFormValues.firstName,
      lastName: userWithAddresses?.last_name || defaultCheckoutFormValues.lastName,

      // Адрес доставки - автозаполнение из user.addresses[0] (если есть)
      city: userWithAddresses?.addresses?.[0]?.city || defaultCheckoutFormValues.city,
      street: userWithAddresses?.addresses?.[0]?.street || defaultCheckoutFormValues.street,
      house: userWithAddresses?.addresses?.[0]?.house || defaultCheckoutFormValues.house,
      apartment:
        userWithAddresses?.addresses?.[0]?.apartment || defaultCheckoutFormValues.apartment,
      postalCode:
        userWithAddresses?.addresses?.[0]?.postal_code || defaultCheckoutFormValues.postalCode,

      // Остальные поля
      deliveryMethod: defaultCheckoutFormValues.deliveryMethod,
      paymentMethod: defaultCheckoutFormValues.paymentMethod,
      comment: defaultCheckoutFormValues.comment,
    },
  });

  // Очистка ошибок заказа при монтировании
  useEffect(() => {
    clearOrder();
  }, [clearOrder]);

  /**
   * Обработчик отправки формы
   * Story 15.2: Интеграция с ordersService через orderStore
   */
  const onSubmit = async (data: CheckoutFormData) => {
    try {
      // Проверка на пустую корзину (edge case)
      if (!cartItems || cartItems.length === 0) {
        useOrderStore.getState().setError('Корзина пуста, невозможно оформить заказ');
        return;
      }

      // Создаём заказ через orderStore
      await createOrder(data);

      // При успехе - получаем ID заказа и перенаправляем на success
      const orderId = useOrderStore.getState().currentOrder?.id;
      if (orderId) {
        router.push(`/checkout/success/${orderId}`);
      }
    } catch (err) {
      // Ошибка уже сохранена в orderStore.error
      console.error('Order creation failed:', err);
    }
  };

  const {
    formState: { errors },
  } = form;

  // Общая ошибка формы (если есть ошибки валидации)
  const hasFormErrors = Object.keys(errors).length > 0;

  // Проверка на пустую корзину
  const isCartEmpty = !cartItems || cartItems.length === 0;

  return (
    <form onSubmit={form.handleSubmit(onSubmit)} noValidate>
      {/* Ошибка пустой корзины */}
      {isCartEmpty && (
        <InfoPanel
          variant="warning"
          title="Корзина пуста"
          message="Добавьте товары в корзину для оформления заказа"
          className="mb-6"
        />
      )}

      {/* Ошибка создания заказа от API */}
      {orderError && (
        <InfoPanel
          variant="error"
          title="Ошибка оформления заказа"
          message={orderError}
          className="mb-6"
        />
      )}

      {/* Общая ошибка валидации */}
      {hasFormErrors && (
        <InfoPanel
          variant="error"
          title="Ошибки в форме"
          message="Пожалуйста, исправьте ошибки в форме перед отправкой"
          className="mb-6"
        />
      )}

      {/* Grid layout: форма + sidebar */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        {/* Левая колонка: секции формы */}
        <div className="space-y-6 lg:col-span-2">
          {/* 1. Контактные данные */}
          <ContactSection form={form} />

          {/* 2. Адрес доставки */}
          <AddressSection form={form} />

          {/* 3. Способ доставки */}
          <DeliveryOptions form={form} />

          {/* 4. Комментарий к заказу */}
          <OrderCommentSection form={form} />
        </div>

        {/* Правая колонка: сводка заказа (sticky на desktop) */}
        <div className="lg:col-span-1">
          <OrderSummary
            isSubmitting={isSubmitting}
            submitError={orderError}
            isCartEmpty={isCartEmpty}
          />
        </div>
      </div>
    </form>
  );
}
