/**
 * Orders Page
 * Страница списка заказов пользователя
 * Story 16.2 - AC: 1, 2, 3
 */

'use client';

import React, { useEffect, useState, useCallback, Suspense } from 'react';
import { useSearchParams, useRouter } from 'next/navigation';
import { OrdersList } from '@/components/business/OrdersList';
import { Spinner } from '@/components/ui';
import Button from '@/components/ui/Button';
import ordersService from '@/services/ordersService';
import type { Order, OrderStatus } from '@/types/order';

const PAGE_SIZE = 20;

/**
 * Валидирует и возвращает статус фильтра из URL
 */
function parseStatusFilter(value: string | null): OrderStatus | 'all' {
  const validStatuses: (OrderStatus | 'all')[] = [
    'all',
    'pending',
    'confirmed',
    'processing',
    'shipped',
    'delivered',
    'cancelled',
    'refunded',
  ];
  return validStatuses.includes(value as OrderStatus | 'all')
    ? (value as OrderStatus | 'all')
    : 'all';
}

/**
 * Валидирует и возвращает номер страницы из URL
 */
function parsePageNumber(value: string | null): number {
  const page = parseInt(value || '1', 10);
  return isNaN(page) || page < 1 ? 1 : page;
}

/**
 * Внутренний компонент страницы с использованием useSearchParams
 */
function OrdersPageContent() {
  const router = useRouter();
  const searchParams = useSearchParams();

  const statusFilter = parseStatusFilter(searchParams.get('status'));
  const currentPage = parsePageNumber(searchParams.get('page'));

  const [orders, setOrders] = useState<Order[]>([]);
  const [totalPages, setTotalPages] = useState(1);
  const [totalCount, setTotalCount] = useState(0);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  /**
   * Загрузка заказов с API
   */
  const fetchOrders = useCallback(async () => {
    setIsLoading(true);
    setError(null);

    try {
      const filters = {
        page: currentPage,
        page_size: PAGE_SIZE,
        ...(statusFilter !== 'all' && { status: statusFilter }),
      };

      const response = await ordersService.getAll(filters);

      setOrders(response.results);
      setTotalCount(response.count);
      setTotalPages(Math.ceil(response.count / PAGE_SIZE));
    } catch (err) {
      console.error('Failed to fetch orders:', err);
      setError('Не удалось загрузить заказы. Попробуйте обновить страницу.');
      setOrders([]);
    } finally {
      setIsLoading(false);
    }
  }, [currentPage, statusFilter]);

  useEffect(() => {
    fetchOrders();
  }, [fetchOrders]);

  /**
   * Обновление URL при изменении фильтра статуса
   */
  const handleStatusFilterChange = useCallback(
    (status: OrderStatus | 'all') => {
      const params = new URLSearchParams(searchParams.toString());
      params.set('page', '1');

      if (status === 'all') {
        params.delete('status');
      } else {
        params.set('status', status);
      }

      router.push(`/profile/orders?${params.toString()}`, { scroll: false });
    },
    [router, searchParams]
  );

  /**
   * Обновление URL при изменении страницы
   */
  const handlePageChange = useCallback(
    (page: number) => {
      const params = new URLSearchParams(searchParams.toString());
      params.set('page', page.toString());
      router.push(`/profile/orders?${params.toString()}`, { scroll: false });
    },
    [router, searchParams]
  );

  return (
    <div className="w-full">
      {/* Header */}
      <div className="mb-6">
        <h1 className="text-title-l font-bold text-text-primary">Мои заказы</h1>
        <p className="text-body-m text-text-secondary mt-1">История ваших заказов и их статусы</p>
      </div>

      {/* Error state */}
      {error && (
        <div className="p-4 mb-6 bg-accent-danger/10 border border-accent-danger rounded-md">
          <p className="text-body-m text-accent-danger">{error}</p>
          <Button variant="tertiary" size="small" onClick={fetchOrders} className="mt-2">
            Попробовать снова
          </Button>
        </div>
      )}

      {/* Orders list */}
      <OrdersList
        orders={orders}
        currentPage={currentPage}
        totalPages={totalPages}
        totalCount={totalCount}
        onPageChange={handlePageChange}
        statusFilter={statusFilter}
        onStatusFilterChange={handleStatusFilterChange}
        isLoading={isLoading}
      />
    </div>
  );
}

/**
 * Страница заказов с Suspense для useSearchParams
 */
export default function OrdersPage() {
  return (
    <Suspense
      fallback={
        <div className="flex items-center justify-center py-16">
          <Spinner size="large" />
        </div>
      }
    >
      <OrdersPageContent />
    </Suspense>
  );
}
