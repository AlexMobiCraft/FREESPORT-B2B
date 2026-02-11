/**
 * OrderSuccessView Component
 * Отображение успешно оформленного заказа
 * Story 15.4: Страница подтверждения заказа
 *
 * Features:
 * - Иконка успеха
 * - Номер и статус заказа
 * - Список товаров
 * - Адрес и способ доставки
 * - Информационный блок "Что дальше?"
 * - Кнопки навигации
 */

import React from 'react';
import Link from 'next/link';
import { CheckCircle } from 'lucide-react';
import { Button } from '@/components/ui/Button/Button';
import { InfoPanel } from '@/components/ui/InfoPanel/InfoPanel';
import type { Order } from '@/types/order';

export interface OrderSuccessViewProps {
  order: Order;
}

/**
 * Маппинг статуса заказа на русский язык (backend статусы)
 */
const statusLabels: Record<string, string> = {
  pending: 'Новый',
  confirmed: 'Подтверждён',
  processing: 'В обработке',
  shipped: 'Отправлен',
  delivered: 'Доставлен',
  cancelled: 'Отменён',
  refunded: 'Возвращён',
};

/**
 * Маппинг способов доставки на русский язык
 */
const deliveryMethodLabels: Record<string, string> = {
  pickup: 'Самовывоз',
  courier: 'Курьерская доставка',
  post: 'Почтовая доставка',
  transport: 'Транспортная компания',
};

/**
 * Парсинг Decimal строки в число для форматирования
 */
function parseDecimal(value: string | number | undefined): number {
  if (value === undefined || value === null) return 0;
  if (typeof value === 'number') return value;
  return parseFloat(value) || 0;
}

/**
 * Компонент отображения успешно оформленного заказа
 */
export const OrderSuccessView: React.FC<OrderSuccessViewProps> = ({ order }) => {
  const statusLabel = statusLabels[order.status] || order.status;

  return (
    <div className="container mx-auto px-4 py-8 max-w-3xl">
      {/* Success Icon */}
      <div className="text-center mb-6">
        <div className="inline-flex items-center justify-center w-16 h-16 bg-green-100 rounded-full">
          <CheckCircle className="w-10 h-10 text-green-600" aria-hidden="true" />
        </div>
        <h1 className="text-3xl font-bold mt-4">Заказ успешно оформлен!</h1>
        <p className="text-gray-600 mt-2">
          Номер заказа: <span className="font-semibold">{order.order_number}</span>
        </p>
      </div>

      {/* Order Details */}
      <div className="bg-white rounded-lg shadow p-6 mb-6">
        <div className="border-b pb-4 mb-4">
          <h2 className="text-xl font-semibold">Детали заказа</h2>
          <p className="text-sm text-gray-600">
            Статус: <span className="text-green-600 font-medium">{statusLabel}</span>
          </p>
        </div>

        {/* Items List */}
        {order.items && order.items.length > 0 ? (
          <div className="mb-4">
            <h3 className="font-semibold mb-2">Товары:</h3>
            {order.items.map(item => (
              <div
                key={item.id || `${item.product}-${item.product_sku}`}
                className="flex justify-between py-2 border-b border-gray-100 last:border-0"
              >
                <span className="text-gray-800">
                  {item.product_name} × {item.quantity}
                </span>
                <span className="font-medium">
                  {parseDecimal(item.total_price).toLocaleString('ru-RU')} ₽
                </span>
              </div>
            ))}
          </div>
        ) : (
          <div className="mb-4">
            <p className="text-amber-600 text-sm">Информация о товарах недоступна</p>
          </div>
        )}

        {/* Delivery Address */}
        {order.delivery_address && (
          <div className="mb-4">
            <h3 className="font-semibold mb-2">Адрес доставки:</h3>
            <p className="text-gray-700">{order.delivery_address}</p>
          </div>
        )}

        {/* Delivery Method */}
        {order.delivery_method && (
          <div className="mb-4">
            <h3 className="font-semibold mb-2">Способ доставки:</h3>
            <p className="text-gray-700">
              {deliveryMethodLabels[order.delivery_method] || order.delivery_method}
            </p>
            {parseDecimal(order.delivery_cost) > 0 && (
              <p className="text-sm text-gray-500 mt-1">
                Стоимость: {parseDecimal(order.delivery_cost).toLocaleString('ru-RU')} ₽
              </p>
            )}
            {parseDecimal(order.delivery_cost) === 0 && (
              <p className="text-sm text-gray-500 mt-1">Стоимость: Уточняется администратором</p>
            )}
          </div>
        )}

        {/* Total */}
        <div className="border-t pt-4">
          <div className="flex justify-between text-lg font-bold">
            <span>Итого:</span>
            <span>{parseDecimal(order.total_amount).toLocaleString('ru-RU')} ₽</span>
          </div>
        </div>
      </div>

      {/* Info Panel */}
      <InfoPanel variant="info" className="mb-6">
        <h3 className="font-semibold">Что дальше?</h3>
        <p className="mt-1">Администратор свяжется с вами в течение 24 часов для уточнения:</p>
        <ul className="list-disc ml-5 mt-2 space-y-1">
          <li>Способа оплаты</li>
          <li>Точной стоимости доставки</li>
          <li>Времени доставки</li>
        </ul>
      </InfoPanel>

      {/* Action Buttons */}
      <div className="flex flex-col sm:flex-row gap-4 justify-center">
        <Link href="/catalog">
          <Button variant="secondary" size="large" className="w-full sm:w-auto">
            Продолжить покупки
          </Button>
        </Link>
        <Link href="/profile/orders">
          <Button variant="primary" size="large" className="w-full sm:w-auto">
            Личный кабинет
          </Button>
        </Link>
      </div>
    </div>
  );
};

export default OrderSuccessView;
