'use client';

import { useEffect, useState } from 'react';
import { UseFormReturn } from 'react-hook-form';
import { CheckoutFormData, CheckoutFormInput } from '@/schemas/checkoutSchema';
import deliveryService from '@/services/deliveryService';
import type { DeliveryMethod } from '@/types/delivery';

export interface DeliveryOptionsProps {
  form: UseFormReturn<CheckoutFormInput, unknown, CheckoutFormData>;
}

/**
 * Компонент выбора способа доставки
 *
 * Story 15.3b: Frontend DeliveryOptions Component
 *
 * Функциональность:
 * - Загрузка списка способов доставки через deliveryService
 * - Radio group для выбора способа доставки
 * - Отображение icon, name и description каждого метода
 * - Стоимость отображается как "Уточняется администратором"
 * - Интеграция с React Hook Form
 * - Обработка loading и error состояний
 * - WCAG 2.1 AA accessibility
 */
export function DeliveryOptions({ form }: DeliveryOptionsProps) {
  const [methods, setMethods] = useState<DeliveryMethod[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const {
    register,
    formState: { errors },
  } = form;

  useEffect(() => {
    const fetchMethods = async () => {
      try {
        setIsLoading(true);
        const data = await deliveryService.getDeliveryMethods();
        setMethods(data);
        setError(null);
      } catch (err) {
        setError('Не удалось загрузить способы доставки');
        console.error('Failed to fetch delivery methods:', err);
      } finally {
        setIsLoading(false);
      }
    };

    fetchMethods();
  }, []);

  // Loading state
  if (isLoading) {
    return (
      <section className="rounded-lg bg-white p-6 shadow-sm" aria-labelledby="delivery-section">
        <h2 id="delivery-section" className="mb-4 text-lg font-semibold text-gray-900">
          Способ доставки
        </h2>
        <div className="animate-pulse" role="status" aria-label="Загрузка способов доставки">
          <div className="space-y-3">
            <div className="h-20 rounded-lg bg-gray-200"></div>
            <div className="h-20 rounded-lg bg-gray-200"></div>
            <div className="h-20 rounded-lg bg-gray-200"></div>
          </div>
        </div>
      </section>
    );
  }

  // Error state
  if (error) {
    return (
      <section className="rounded-lg bg-white p-6 shadow-sm" aria-labelledby="delivery-section">
        <h2 id="delivery-section" className="mb-4 text-lg font-semibold text-gray-900">
          Способ доставки
        </h2>
        <div className="rounded-lg border border-red-300 bg-red-50 p-4 text-red-600" role="alert">
          {error}
        </div>
      </section>
    );
  }

  const errorId = 'delivery-method-error';

  return (
    <section className="rounded-lg bg-white p-6 shadow-sm" aria-labelledby="delivery-section">
      <h2 id="delivery-section" className="mb-4 text-lg font-semibold text-gray-900">
        Способ доставки
      </h2>

      <div
        className="space-y-3"
        role="radiogroup"
        aria-label="Выбор способа доставки"
        aria-describedby={errors.deliveryMethod ? errorId : undefined}
      >
        {methods.map(method => (
          <label
            key={method.id}
            className={`
              flex cursor-pointer items-start rounded-lg border-2 p-4
              transition-colors duration-200
              hover:border-primary/50 hover:bg-primary-subtle
              ${!method.is_available ? 'cursor-not-allowed opacity-50' : ''}
              ${errors.deliveryMethod ? 'border-red-300' : 'border-gray-200'}
            `}
          >
            <input
              {...register('deliveryMethod')}
              type="radio"
              value={method.id}
              disabled={!method.is_available}
              className="mt-1 h-4 w-4 border-gray-300 text-primary focus:ring-2 focus:ring-primary"
              aria-describedby={`${method.id}-description`}
            />
            <div className="ml-3 flex-1">
              <span className="block text-sm font-medium text-gray-900">
                {method.icon && <span className="mr-2">{method.icon}</span>}
                {method.name}
              </span>
              <span id={`${method.id}-description`} className="block text-xs text-gray-600">
                {method.description}
              </span>
              <span className="mt-1 block text-xs text-gray-500">
                Стоимость: <span className="font-medium">Уточняется администратором</span>
              </span>
            </div>
          </label>
        ))}
      </div>

      {errors.deliveryMethod && (
        <p id={errorId} className="mt-2 text-sm text-red-600" role="alert">
          {errors.deliveryMethod.message}
        </p>
      )}

      {/* Информационное сообщение */}
      <div className="mt-4 rounded-md bg-primary-subtle p-3">
        <p className="text-xs text-text-primary">
          <strong>Обратите внимание:</strong> Стоимость доставки будет рассчитана и уточнена
          администратором после оформления заказа.
        </p>
      </div>
    </section>
  );
}

export default DeliveryOptions;
