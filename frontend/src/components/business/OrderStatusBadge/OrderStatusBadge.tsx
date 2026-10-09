/**
 * OrderStatusBadge Component
 * Бейдж для отображения статуса заказа с цветовой кодировкой
 * Story 16.2 - AC: 1, 3
 */

import React from 'react';
import { cn } from '@/utils/cn';
import { Clock, CheckCircle2, Truck, Package, XCircle, RotateCcw, FileText } from 'lucide-react';
import type { OrderStatus } from '@/types/order';

export interface OrderStatusBadgeProps {
  status: OrderStatus;
  className?: string;
}

/**
 * Конфигурация для каждого статуса заказа
 */
const statusConfig: Record<
  OrderStatus,
  {
    bg: string;
    text: string;
    label: string;
    icon: React.ReactNode;
  }
> = {
  pending: {
    bg: 'bg-[#FFF1CC]',
    text: 'text-[#B07600]',
    label: 'Новый',
    icon: <Clock className="w-3 h-3" aria-hidden="true" />,
  },
  confirmed: {
    bg: 'bg-[#E7F3FF]',
    text: 'text-primary',
    label: 'Подтверждён',
    icon: <FileText className="w-3 h-3" aria-hidden="true" />,
  },
  processing: {
    bg: 'bg-[#E1F5FF]',
    text: 'text-secondary',
    label: 'В обработке',
    icon: <Package className="w-3 h-3" aria-hidden="true" />,
  },
  shipped: {
    bg: 'bg-[#F0E7FF]',
    text: 'text-[#7C3AED]',
    label: 'Отправлен',
    icon: <Truck className="w-3 h-3" aria-hidden="true" />,
  },
  delivered: {
    bg: 'bg-[#E0F5E8]',
    text: 'text-accent-success',
    label: 'Доставлен',
    icon: <CheckCircle2 className="w-3 h-3" aria-hidden="true" />,
  },
  cancelled: {
    bg: 'bg-[#FFE1E8]',
    text: 'text-accent-danger',
    label: 'Отменён',
    icon: <XCircle className="w-3 h-3" aria-hidden="true" />,
  },
  refunded: {
    bg: 'bg-neutral-200',
    text: 'text-neutral-700',
    label: 'Возвращён',
    icon: <RotateCcw className="w-3 h-3" aria-hidden="true" />,
  },
};

/**
 * Компонент для отображения статуса заказа
 */
export const OrderStatusBadge: React.FC<OrderStatusBadgeProps> = ({ status, className }) => {
  const config = statusConfig[status];

  if (!config) {
    return (
      <span
        className={cn(
          'inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] leading-[14px] font-medium bg-neutral-200 text-neutral-700',
          className
        )}
      >
        {status}
      </span>
    );
  }

  return (
    <span
      className={cn(
        'inline-flex items-center gap-1',
        'px-2 py-0.5 rounded-full',
        'text-[11px] leading-[14px] font-medium',
        config.bg,
        config.text,
        className
      )}
    >
      {config.icon}
      {config.label}
    </span>
  );
};

OrderStatusBadge.displayName = 'OrderStatusBadge';

export default OrderStatusBadge;
