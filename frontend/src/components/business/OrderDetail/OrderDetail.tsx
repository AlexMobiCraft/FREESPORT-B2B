/**
 * OrderDetail Component
 * Детальный просмотр заказа с секциями информации
 * Story 16.2 - AC: 2, 4, 5, 6
 */

'use client';

import React from 'react';
import Link from 'next/link';
import { cn } from '@/utils/cn';
import { Card, Button } from '@/components/ui';
import { OrderStatusBadge } from '@/components/business/OrderStatusBadge';
import { OrderItemsTable } from './OrderItemsTable';
import {
  ArrowLeft,
  Calendar,
  MapPin,
  CreditCard,
  ShoppingCart,
  Download,
  Truck,
} from 'lucide-react';
import type { Order } from '@/types/order';

export interface OrderDetailProps {
  order: Order;
  showExportPDF?: boolean;
  onRepeatOrder?: () => void;
  onExportPDF?: () => void;
  isRepeatLoading?: boolean;
  isExportLoading?: boolean;
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
      hour: '2-digit',
      minute: '2-digit',
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
 * Маппинг способов доставки
 */
const deliveryMethodLabels: Record<string, string> = {
  pickup: 'Самовывоз',
  courier: 'Курьерская доставка',
  post: 'Почта России',
  transport_company: 'Транспортная компания',
};

/**
 * Маппинг способов оплаты
 */
const paymentMethodLabels: Record<string, string> = {
  card: 'Банковская карта',
  cash: 'Наличными при получении',
  invoice: 'Безналичный расчёт',
  online: 'Онлайн оплата',
};

/**
 * Маппинг статусов оплаты
 */
const paymentStatusLabels: Record<string, { label: string; color: string }> = {
  pending: { label: 'Ожидает оплаты', color: 'text-[#B07600]' },
  paid: { label: 'Оплачен', color: 'text-accent-success' },
  failed: { label: 'Ошибка оплаты', color: 'text-accent-danger' },
  refunded: { label: 'Возврат', color: 'text-text-muted' },
};

/**
 * Компонент секции
 */
const Section: React.FC<{
  title: string;
  icon: React.ReactNode;
  children: React.ReactNode;
  className?: string;
}> = ({ title, icon, children, className }) => (
  <Card className={cn('mb-4', className)}>
    <div className="flex items-center gap-2 mb-4">
      <span className="text-primary">{icon}</span>
      <h2 className="text-title-m font-semibold text-text-primary">{title}</h2>
    </div>
    {children}
  </Card>
);

/**
 * Компонент детального просмотра заказа
 */
export const OrderDetail: React.FC<OrderDetailProps> = ({
  order,
  showExportPDF = false,
  onRepeatOrder,
  onExportPDF,
  isRepeatLoading = false,
  isExportLoading = false,
  className,
}) => {
  const paymentStatus = paymentStatusLabels[order.payment_status] || {
    label: order.payment_status,
    color: 'text-text-secondary',
  };

  return (
    <div className={cn('w-full', className)}>
      {/* Back link */}
      <Link
        href="/profile/orders"
        className="inline-flex items-center gap-2 text-body-m text-primary hover:underline mb-6"
      >
        <ArrowLeft className="w-4 h-4" aria-hidden="true" />
        Вернуться к списку заказов
      </Link>

      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-4 mb-6">
        <div>
          <h1 className="text-title-l font-bold text-text-primary">Заказ №{order.order_number}</h1>
          <div className="flex items-center gap-2 mt-2 text-body-m text-text-muted">
            <Calendar className="w-4 h-4" aria-hidden="true" />
            <span>{formatDate(order.created_at)}</span>
          </div>
        </div>
        <OrderStatusBadge status={order.status} className="self-start" />
      </div>

      {/* Section 1: Товары */}
      <Section title="Товары" icon={<ShoppingCart className="w-5 h-5" />}>
        <OrderItemsTable items={order.items || []} />

        {/* Итоги */}
        <div className="mt-4 pt-4 border-t border-neutral-300 space-y-2">
          <div className="flex justify-between text-body-m">
            <span className="text-text-secondary">Подытог:</span>
            <span className="text-text-primary">{formatPrice(order.subtotal)}</span>
          </div>
          {parseFloat(order.discount_amount) > 0 && (
            <div className="flex justify-between text-body-m">
              <span className="text-text-secondary">Скидка:</span>
              <span className="text-accent-success">-{formatPrice(order.discount_amount)}</span>
            </div>
          )}
          <div className="flex justify-between text-body-m">
            <span className="text-text-secondary">Доставка:</span>
            <span className="text-text-primary">
              {parseFloat(order.delivery_cost) > 0 ? formatPrice(order.delivery_cost) : 'Бесплатно'}
            </span>
          </div>
          <div className="flex justify-between text-title-m font-bold pt-2 border-t border-neutral-300">
            <span className="text-text-primary">Итого:</span>
            <span className="text-text-primary">{formatPrice(order.total_amount)}</span>
          </div>
        </div>
      </Section>

      {/* Section 2: Доставка */}
      <Section title="Доставка" icon={<Truck className="w-5 h-5" />}>
        <div className="space-y-3">
          <div>
            <p className="text-body-s text-text-muted mb-1">Способ доставки</p>
            <p className="text-body-m text-text-primary">
              {deliveryMethodLabels[order.delivery_method] || order.delivery_method}
            </p>
          </div>
          {order.delivery_address && (
            <div>
              <p className="text-body-s text-text-muted mb-1">Адрес доставки</p>
              <div className="flex items-start gap-2">
                <MapPin
                  className="w-4 h-4 text-text-muted mt-0.5 flex-shrink-0"
                  aria-hidden="true"
                />
                <p className="text-body-m text-text-primary">{order.delivery_address}</p>
              </div>
            </div>
          )}
          {order.tracking_number && (
            <div>
              <p className="text-body-s text-text-muted mb-1">Номер отслеживания</p>
              <p className="text-body-m text-primary font-medium">{order.tracking_number}</p>
            </div>
          )}
        </div>
      </Section>

      {/* Section 3: Оплата */}
      <Section title="Оплата" icon={<CreditCard className="w-5 h-5" />}>
        <div className="space-y-3">
          <div>
            <p className="text-body-s text-text-muted mb-1">Способ оплаты</p>
            <p className="text-body-m text-text-primary">
              {paymentMethodLabels[order.payment_method] || order.payment_method}
            </p>
          </div>
          <div>
            <p className="text-body-s text-text-muted mb-1">Статус оплаты</p>
            <p className={cn('text-body-m font-medium', paymentStatus.color)}>
              {paymentStatus.label}
            </p>
          </div>
        </div>
      </Section>

      {/* Section 4: Действия */}
      <Card className="flex flex-col sm:flex-row gap-3">
        <Button onClick={onRepeatOrder} disabled={isRepeatLoading} className="flex-1">
          <ShoppingCart className="w-4 h-4 mr-2" aria-hidden="true" />
          {isRepeatLoading ? 'Добавление...' : 'Повторить заказ'}
        </Button>

        {showExportPDF && (
          <Button
            variant="secondary"
            onClick={onExportPDF}
            disabled={isExportLoading}
            className="flex-1"
          >
            <Download className="w-4 h-4 mr-2" aria-hidden="true" />
            {isExportLoading ? 'Экспорт...' : 'Экспорт в PDF'}
          </Button>
        )}
      </Card>

      {/* Примечания */}
      {order.notes && (
        <Card className="mt-4">
          <h3 className="text-body-m font-semibold text-text-primary mb-2">Примечания</h3>
          <p className="text-body-m text-text-secondary">{order.notes}</p>
        </Card>
      )}
    </div>
  );
};

OrderDetail.displayName = 'OrderDetail';

export default OrderDetail;
