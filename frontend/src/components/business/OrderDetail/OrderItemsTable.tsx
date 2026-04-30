/**
 * OrderItemsTable Component
 * Таблица товаров в заказе
 * Story 16.2 - AC: 2
 */

'use client';

import React from 'react';
import { cn } from '@/utils/cn';
import type { OrderItem } from '@/types/order';

export interface OrderItemsTableProps {
  items: OrderItem[];
  className?: string;
}

/**
 * Форматирует цену в рубли
 */
function formatPrice(price: string): string {
  const num = parseFloat(price);
  if (isNaN(num)) return price;
  return new Intl.NumberFormat('ru-RU', {
    style: 'currency',
    currency: 'RUB',
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(num);
}

/**
 * Таблица товаров заказа
 */
export const OrderItemsTable: React.FC<OrderItemsTableProps> = ({ items, className }) => {
  if (!items || items.length === 0) {
    return <p className="text-body-m text-text-muted py-4">Нет товаров в заказе</p>;
  }

  return (
    <div className={cn('w-full', className)}>
      {/* Desktop table */}
      <div className="hidden md:block overflow-x-auto">
        <table className="w-full">
          <thead>
            <tr className="border-b border-neutral-300">
              <th className="text-left py-3 px-2 text-body-s font-semibold text-text-secondary">
                Товар
              </th>
              <th className="text-left py-3 px-2 text-body-s font-semibold text-text-secondary">
                Артикул
              </th>
              <th className="text-center py-3 px-2 text-body-s font-semibold text-text-secondary">
                Кол-во
              </th>
              <th className="text-right py-3 px-2 text-body-s font-semibold text-text-secondary">
                Цена
              </th>
              <th className="text-right py-3 px-2 text-body-s font-semibold text-text-secondary">
                Сумма
              </th>
            </tr>
          </thead>
          <tbody>
            {items.map(item => (
              <tr key={item.id} className="border-b border-neutral-200 last:border-b-0">
                <td className="py-4 px-2">
                  <span className="text-body-m text-text-primary">{item.product_name}</span>
                </td>
                <td className="py-4 px-2">
                  <span className="text-body-s text-text-muted">{item.product_sku}</span>
                </td>
                <td className="py-4 px-2 text-center">
                  <span className="text-body-m text-text-primary">{item.quantity}</span>
                </td>
                <td className="py-4 px-2 text-right">
                  <span className="text-body-m text-text-secondary">
                    {formatPrice(item.unit_price)}
                  </span>
                </td>
                <td className="py-4 px-2 text-right">
                  <span className="text-body-m font-semibold text-text-primary">
                    {formatPrice(item.total_price)}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Mobile cards */}
      <div className="md:hidden space-y-4">
        {items.map(item => (
          <div key={item.id} className="p-4 bg-neutral-200 rounded-md">
            <div className="flex justify-between items-start mb-2">
              <div className="flex-1 pr-4">
                <h4 className="text-body-m font-medium text-text-primary">{item.product_name}</h4>
                <p className="text-body-s text-text-muted mt-0.5">Артикул: {item.product_sku}</p>
              </div>
              <span className="text-body-m font-semibold text-text-primary">
                {formatPrice(item.total_price)}
              </span>
            </div>
            <div className="flex justify-between items-center text-body-s text-text-secondary">
              <span>Кол-во: {item.quantity}</span>
              <span>× {formatPrice(item.unit_price)}</span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};

OrderItemsTable.displayName = 'OrderItemsTable';

export default OrderItemsTable;
