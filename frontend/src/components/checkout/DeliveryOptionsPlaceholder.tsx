'use client';

import { UseFormReturn } from 'react-hook-form';
import { CheckoutFormData, CheckoutFormInput } from '@/schemas/checkoutSchema';

export interface DeliveryOptionsPlaceholderProps {
  form: UseFormReturn<CheckoutFormInput, unknown, CheckoutFormData>;
}

/**
 * Placeholder для компонента выбора способа доставки
 *
 * Story 15.1: Checkout страница и упрощённая форма
 *
 * ВАЖНО: Это временный placeholder!
 * Полная реализация будет в Story 15.3
 *
 * Текущая функциональность:
 * - Статический список способов доставки
 * - Регистрация поля deliveryMethod в форме
 * - БЕЗ расчёта стоимости доставки
 * - БЕЗ интеграции с API CDEK/Boxberry
 */
export function DeliveryOptionsPlaceholder({ form }: DeliveryOptionsPlaceholderProps) {
  const {
    register,
    formState: { errors },
  } = form;

  const deliveryOptions = [
    { id: 'courier', label: 'Курьерская доставка', description: 'Доставка до двери' },
    { id: 'pickup', label: 'Самовывоз', description: 'Забрать из пункта выдачи' },
    { id: 'transport', label: 'Транспортная компания', description: 'Отправка ТК' },
  ];

  return (
    <section className="rounded-lg bg-white p-6 shadow-sm" aria-labelledby="delivery-section">
      <h2 id="delivery-section" className="mb-4 text-lg font-semibold text-gray-900">
        Способ доставки
      </h2>

      <div className="space-y-3">
        {deliveryOptions.map(option => (
          <label
            key={option.id}
            className={`
              flex cursor-pointer items-start rounded-lg border-2 p-4
              transition-colors duration-200
              hover:border-primary/50 hover:bg-primary-subtle
              ${errors.deliveryMethod ? 'border-red-300' : 'border-gray-200'}
            `}
          >
            <input
              {...register('deliveryMethod')}
              type="radio"
              value={option.id}
              className="mt-1 h-4 w-4 border-gray-300 text-primary focus:ring-2 focus:ring-primary"
              aria-describedby={`${option.id}-description`}
            />
            <div className="ml-3 flex-1">
              <span className="block text-sm font-medium text-gray-900">{option.label}</span>
              <span id={`${option.id}-description`} className="block text-xs text-gray-600">
                {option.description}
              </span>
              <span className="mt-1 block text-xs text-gray-500">
                Стоимость: Уточняется администратором
              </span>
            </div>
          </label>
        ))}

        {errors.deliveryMethod && (
          <p className="text-sm text-red-600" role="alert">
            {errors.deliveryMethod.message}
          </p>
        )}
      </div>

      {/* Информационное сообщение о placeholder */}
      <div className="mt-4 rounded-md bg-primary-subtle p-3">
        <p className="text-xs text-text-primary">
          <strong>Обратите внимание:</strong> Стоимость доставки будет рассчитана и уточнена
          администратором после оформления заказа.
        </p>
      </div>
    </section>
  );
}
