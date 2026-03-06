/**
 * OrdersList Component
 * Список заказов с пагинацией и фильтрацией по статусу
 * Story 16.2 - AC: 1, 2, 3
 */

'use client';

import React from 'react';
import { cn } from '@/utils/cn';
import { Pagination, Spinner } from '@/components/ui';
import { OrderCard } from '@/components/business/OrderCard';
import { ShoppingBag } from 'lucide-react';
import type { Order, OrderStatus } from '@/types/order';

export interface OrdersListProps {
  orders: Order[];
  currentPage: number;
  totalPages: number;
  totalCount: number;
  onPageChange: (page: number) => void;
  statusFilter: OrderStatus | 'all';
  onStatusFilterChange: (status: OrderStatus | 'all') => void;
  isLoading?: boolean;
  className?: string;
}

/**
 * Конфигурация табов фильтрации по статусу
 */
const STATUS_TABS: { id: OrderStatus | 'all'; label: string }[] = [
  { id: 'all', label: 'Все' },
  { id: 'pending', label: 'Новые' },
  { id: 'processing', label: 'В обработке' },
  { id: 'shipped', label: 'Отправлены' },
  { id: 'delivered', label: 'Доставлены' },
  { id: 'cancelled', label: 'Отменены' },
];

/**
 * Компонент пустого состояния
 */
const EmptyState: React.FC<{ statusFilter: OrderStatus | 'all' }> = ({ statusFilter }) => {
  const message =
    statusFilter === 'all' ? 'У вас пока нет заказов' : 'Нет заказов с выбранным статусом';

  return (
    <div className="flex flex-col items-center justify-center py-16 text-center">
      <div className="w-16 h-16 rounded-full bg-neutral-200 flex items-center justify-center mb-4">
        <ShoppingBag className="w-8 h-8 text-neutral-400" aria-hidden="true" />
      </div>
      <h3 className="text-title-m font-semibold text-text-primary mb-2">{message}</h3>
      <p className="text-body-s text-text-muted max-w-sm">
        {statusFilter === 'all'
          ? 'После оформления заказа он появится здесь'
          : 'Попробуйте выбрать другой фильтр'}
      </p>
    </div>
  );
};

/**
 * Компонент списка заказов
 */
export const OrdersList: React.FC<OrdersListProps> = ({
  orders,
  currentPage,
  totalPages,
  totalCount,
  onPageChange,
  statusFilter,
  onStatusFilterChange,
  isLoading = false,
  className,
}) => {
  return (
    <div className={cn('w-full', className)}>
      {/* Фильтры по статусу */}
      <div className="flex items-center gap-2 mb-6 overflow-x-auto pt-2 pl-2 pb-2 scrollbar-hide">
        {STATUS_TABS.map(tab => {
          const isActive = tab.id === statusFilter;
          return (
            <button
              key={tab.id}
              onClick={() => onStatusFilterChange(tab.id)}
              className={cn(
                'px-4 py-2 rounded-full text-body-s font-medium whitespace-nowrap',
                'transition-colors duration-short',
                'focus:outline-none focus:ring-2 focus:ring-primary focus:ring-offset-2',
                isActive
                  ? 'bg-primary text-text-inverse'
                  : 'bg-neutral-200 text-text-secondary hover:bg-neutral-300'
              )}
            >
              {tab.label}
            </button>
          );
        })}
      </div>

      {/* Счётчик результатов */}
      {totalCount > 0 && (
        <p className="text-body-s text-text-muted mb-4">Найдено заказов: {totalCount}</p>
      )}

      {/* Loading state */}
      {isLoading && (
        <div className="flex items-center justify-center py-16">
          <Spinner size="large" />
        </div>
      )}

      {/* Empty state */}
      {!isLoading && orders.length === 0 && <EmptyState statusFilter={statusFilter} />}

      {/* Orders grid */}
      {!isLoading && orders.length > 0 && (
        <>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {orders.map(order => (
              <OrderCard key={order.id} order={order} />
            ))}
          </div>

          {/* Pagination */}
          {totalPages > 1 && (
            <div className="mt-8">
              <Pagination
                currentPage={currentPage}
                totalPages={totalPages}
                onPageChange={onPageChange}
                maxVisiblePages={5}
              />
            </div>
          )}
        </>
      )}
    </div>
  );
};

OrdersList.displayName = 'OrdersList';

export default OrdersList;
