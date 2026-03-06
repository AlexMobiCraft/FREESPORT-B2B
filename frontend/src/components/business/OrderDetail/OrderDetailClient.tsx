/**
 * OrderDetail Client Component
 * Клиентская часть страницы детального просмотра заказа
 * Story 16.2 - SSR: Интерактивность (повторить заказ, экспорт PDF)
 */

'use client';

import React, { useState, useCallback } from 'react';
import { OrderDetail } from './OrderDetail';
import { useToast } from '@/components/ui';
import { useCartStore } from '@/stores/cartStore';
import { authSelectors } from '@/stores/authStore';
import { generateOrderPdf } from '@/utils/orderPdfExport';
import type { Order } from '@/types/order';

interface OrderDetailClientProps {
  order: Order;
}

/**
 * Клиентский компонент для интерактивных действий с заказом
 * Получает данные заказа из Server Component (SSR)
 */
export function OrderDetailClient({ order }: OrderDetailClientProps) {
  const toast = useToast();

  const isB2BUser = authSelectors.useIsB2BUser();
  const addItem = useCartStore(state => state.addItem);

  const [isRepeatLoading, setIsRepeatLoading] = useState(false);
  const [isExportLoading, setIsExportLoading] = useState(false);

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
