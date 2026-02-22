/**
 * Order Detail Page
 * Страница детального просмотра заказа
 * Story 16.2 - AC: 2, 4, 5, 6
 */

'use client';

import React, { useEffect, useState, useCallback } from 'react';
import { useParams, useRouter, notFound } from 'next/navigation';
import { OrderDetail } from '@/components/business/OrderDetail';
import { Spinner, useToast } from '@/components/ui';
import ordersService from '@/services/ordersService';
import { useCartStore } from '@/stores/cartStore';
import { authSelectors } from '@/stores/authStore';
import { generateOrderPdf } from '@/utils/orderPdfExport';
import type { Order } from '@/types/order';

/**
 * Страница детального просмотра заказа
 */
export default function OrderDetailPage() {
  const params = useParams();
  const router = useRouter();
  const toast = useToast();

  const orderId = params.id as string;

  const isB2BUser = authSelectors.useIsB2BUser();

  const addItem = useCartStore(state => state.addItem);

  const [order, setOrder] = useState<Order | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isRepeatLoading, setIsRepeatLoading] = useState(false);
  const [isExportLoading, setIsExportLoading] = useState(false);

  /**
   * Загрузка данных заказа
   */
  const fetchOrder = useCallback(async () => {
    if (!orderId) return;

    setIsLoading(true);
    setError(null);

    try {
      const data = await ordersService.getById(orderId);
      setOrder(data);
    } catch (err: unknown) {
      console.error('Failed to fetch order:', err);

      if (err && typeof err === 'object' && 'response' in err) {
        const axiosError = err as { response?: { status?: number } };
        if (axiosError.response?.status === 403) {
          setError('У вас нет доступа к этому заказу');
          return;
        }
        if (axiosError.response?.status === 404) {
          notFound();
          return;
        }
      }

      setError('Не удалось загрузить данные заказа');
    } finally {
      setIsLoading(false);
    }
  }, [orderId]);

  useEffect(() => {
    fetchOrder();
  }, [fetchOrder]);

  /**
   * Повторить заказ - добавить все товары в корзину
   * ВАЖНО: cartStore.addItem требует variant_id, не product_id
   */
  const handleRepeatOrder = useCallback(async () => {
    if (!order?.items || order.items.length === 0) {
      toast.warning('В заказе нет товаров для добавления в корзину', 'Пустой заказ');
      return;
    }

    setIsRepeatLoading(true);

    let successCount = 0;
    let failedCount = 0;
    const failedItems: string[] = [];
    const unavailableItems: string[] = [];

    try {
      for (const item of order.items) {
        // Проверяем наличие варианта и его активность
        if (!item.variant) {
          failedCount++;
          unavailableItems.push(item.product_name);
          continue;
        }

        // Проверяем is_active варианта (AC5: предупреждение о недоступных товарах)
        if (!item.variant.is_active) {
          failedCount++;
          unavailableItems.push(item.product_name);
          continue;
        }

        try {
          // Используем variant.id вместо product id (CART-001 fix)
          const result = await addItem(item.variant.id, item.quantity);

          if (result.success) {
            successCount++;
          } else {
            failedCount++;
            failedItems.push(item.product_name);
          }
        } catch {
          failedCount++;
          failedItems.push(item.product_name);
        }
      }

      // Формируем сообщения
      if (failedCount === 0) {
        toast.success(`Все ${successCount} товаров добавлены в корзину`, 'Товары добавлены');
      } else if (successCount > 0) {
        const unavailableMsg =
          unavailableItems.length > 0
            ? `Недоступны: ${unavailableItems.slice(0, 2).join(', ')}${unavailableItems.length > 2 ? '...' : ''}`
            : `Ошибка добавления: ${failedItems.slice(0, 2).join(', ')}${failedItems.length > 2 ? '...' : ''}`;
        toast.warning(
          `Добавлено ${successCount} из ${order.items.length} товаров. ${unavailableMsg}`,
          'Частично добавлено'
        );
      } else {
        toast.error('Все товары из заказа недоступны для повторного заказа', 'Ошибка');
      }
    } catch (err) {
      console.error('Failed to repeat order:', err);
      toast.error('Не удалось добавить товары в корзину', 'Ошибка');
    } finally {
      setIsRepeatLoading(false);
    }
  }, [order, addItem, toast]);

  /**
   * Экспорт заказа в PDF (AC6: только для B2B пользователей)
   */
  const handleExportPDF = useCallback(async () => {
    if (!order) return;

    setIsExportLoading(true);

    try {
      generateOrderPdf(order);
      toast.success(`Заказ №${order.order_number} экспортирован в PDF`, 'Экспорт завершён');
    } catch (err) {
      console.error('Failed to export PDF:', err);
      toast.error('Не удалось экспортировать заказ в PDF', 'Ошибка');
    } finally {
      setIsExportLoading(false);
    }
  }, [order, toast]);

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-16">
        <Spinner size="large" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="text-center py-16">
        <h2 className="text-title-m font-semibold text-text-primary mb-2">Ошибка</h2>
        <p className="text-body-m text-text-secondary mb-4">{error}</p>
        <button
          onClick={() => router.push('/profile/orders')}
          className="text-primary hover:underline"
        >
          Вернуться к списку заказов
        </button>
      </div>
    );
  }

  if (!order) {
    return (
      <div className="text-center py-16">
        <h2 className="text-title-m font-semibold text-text-primary mb-2">Заказ не найден</h2>
        <button
          onClick={() => router.push('/profile/orders')}
          className="text-primary hover:underline"
        >
          Вернуться к списку заказов
        </button>
      </div>
    );
  }

  return (
    <OrderDetail
      order={order}
      showExportPDF={isB2BUser}
      onRepeatOrder={handleRepeatOrder}
      onExportPDF={handleExportPDF}
      isRepeatLoading={isRepeatLoading}
      isExportLoading={isExportLoading}
    />
  );
}
