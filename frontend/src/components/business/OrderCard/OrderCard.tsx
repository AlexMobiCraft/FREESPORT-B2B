/**
 * OrderCard Component
 * Карточка заказа для списка заказов в личном кабинете
 * Story 16.2 - AC: 1, 2
 */

'use client';

import React from 'react';
import Link from 'next/link';
import { cn } from '@/utils/cn';
import { Card } from '@/components/ui';
import { OrderStatusBadge } from '@/components/business/OrderStatusBadge';
import { ShoppingBag, Calendar, ChevronRight } from 'lucide-react';
import type { Order } from '@/types/order';

export interface OrderCardProps {
  order: Order;
  className?: string;
}

/**
 * Форматирует дату в локализованный формат
 */
function formatDate(dateString: string): string {
  try {
    const date = new Date(dateString);
    return date.toLocaleDateString('ru-RU', {
      day: 'numeric',
      month: 'long',
      year: 'numeric',
    });
  } catch {
    return dateString;
  }
}

/**
 * Форматирует сумму в рубли
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
 * Склонение слова "товар" в зависимости от количества
 */
function getItemsLabel(count: number): string {
  const lastDigit = count % 10;
  const lastTwoDigits = count % 100;

  if (lastTwoDigits >= 11 && lastTwoDigits <= 19) {
    return 'товаров';
  }
  if (lastDigit === 1) {
    return 'товар';
  }
  if (lastDigit >= 2 && lastDigit <= 4) {
    return 'товара';
  }
  return 'товаров';
}

/**
 * Компонент карточки заказа
 */
export const OrderCard: React.FC<OrderCardProps> = ({ order, className }) => {
  const itemsCount = order.total_items || order.items?.length || 0;

  return (
    <Link href={`/profile/orders/${order.id}`} className={cn('block', className)}>
      <Card hover className="group">
        <div className="flex items-start justify-between mb-4">
          <div>
            <h3 className="text-title-m font-semibold text-text-primary">
              Заказ №{order.order_number}
            </h3>
            <div className="flex items-center gap-1.5 mt-1 text-body-s text-text-muted">
              <Calendar className="w-4 h-4" aria-hidden="true" />
              <span>{formatDate(order.created_at)}</span>
            </div>
          </div>
          <OrderStatusBadge status={order.status} />
        </div>

        <div className="flex items-center justify-between pt-4 border-t border-neutral-300">
          <div className="flex items-center gap-1.5 text-body-s text-text-secondary">
            <ShoppingBag className="w-4 h-4" aria-hidden="true" />
            <span>
              {itemsCount} {getItemsLabel(itemsCount)}
            </span>
          </div>

          <div className="flex items-center gap-2">
            <span className="text-title-m font-bold text-text-primary">
              {formatPrice(order.total_amount)}
            </span>
            <ChevronRight
              className="w-5 h-5 text-neutral-400 group-hover:text-primary transition-colors"
              aria-hidden="true"
            />
          </div>
        </div>
      </Card>
    </Link>
  );
};

OrderCard.displayName = 'OrderCard';

export default OrderCard;
