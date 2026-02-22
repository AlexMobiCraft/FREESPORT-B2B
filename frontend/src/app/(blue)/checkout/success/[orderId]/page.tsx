/**
 * Страница подтверждения заказа
 * Story 15.4: Страница успешного оформления заказа
 *
 * Features:
 * - Client-side загрузка деталей заказа (для корректной аутентификации)
 * - Статические metadata (страница не индексируется)
 * - Обработка edge cases (404, ошибки загрузки)
 */

'use client';

import { useEffect, useState } from 'react';
import { useParams, notFound, useRouter } from 'next/navigation';
import OrderSuccessView from '@/components/checkout/OrderSuccessView';
import ordersService from '@/services/ordersService';
import Button from '@/components/ui/Button';
import type { Order } from '@/types/order';

/**
 * Client-side страница подтверждения заказа
 * Использует client-side fetch для корректной передачи cookies/токенов
 */
export default function SuccessPage() {
  const params = useParams();
  const orderId = params?.orderId as string;

  const [order, setOrder] = useState<Order | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [is404, setIs404] = useState(false);

  useEffect(() => {
    if (!orderId) return;

    const fetchOrder = async () => {
      try {
        setLoading(true);
        setError(null);
        const data = await ordersService.getById(orderId);

        if (!data || !data.id) {
          setIs404(true);
          return;
        }

        setOrder(data);
      } catch (err) {
        console.error(`[SuccessPage] Failed to load order ${orderId}:`, err);

        if (err instanceof Error && err.message.includes('404')) {
          setIs404(true);
          return;
        }

        setError(err instanceof Error ? err.message : 'Ошибка загрузки заказа');
      } finally {
        setLoading(false);
      }
    };

    fetchOrder();
  }, [orderId]);

  // 404 - заказ не найден
  if (is404) {
    notFound();
  }

  // Loading state
  if (loading) {
    return <OrderLoadingView />;
  }

  // Error state
  if (error || !order) {
    return <OrderErrorView orderId={orderId} />;
  }

  return <OrderSuccessView order={order} />;
}

/**
 * Компонент загрузки
 */
function OrderLoadingView() {
  return (
    <div className="container mx-auto px-4 py-8 max-w-3xl">
      <div className="text-center">
        <div className="inline-flex items-center justify-center w-16 h-16 bg-gray-100 rounded-full mb-4 animate-pulse">
          <div className="w-10 h-10 bg-gray-200 rounded-full" />
        </div>
        <div className="h-8 bg-gray-200 rounded w-64 mx-auto mb-4 animate-pulse" />
        <div className="h-4 bg-gray-200 rounded w-48 mx-auto animate-pulse" />
      </div>
    </div>
  );
}

/**
 * Компонент отображения ошибки загрузки заказа
 */
function OrderErrorView({ orderId }: { orderId: string }) {
  const router = useRouter();

  return (
    <div className="container mx-auto px-4 py-8 max-w-3xl">
      <div className="text-center">
        <div className="inline-flex items-center justify-center w-16 h-16 bg-red-100 rounded-full mb-4">
          <svg
            className="w-10 h-10 text-red-600"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
            aria-hidden="true"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
            />
          </svg>
        </div>
        <h1 className="text-2xl font-bold text-gray-900 mb-2">Ошибка загрузки заказа</h1>
        <p className="text-gray-600 mb-6">
          Не удалось загрузить информацию о заказе #{orderId}. Попробуйте обновить страницу.
        </p>
        <div className="flex flex-col sm:flex-row gap-4 justify-center">
          <Button onClick={() => window.location.reload()} variant="secondary">
            Повторить попытку
          </Button>
          <Button onClick={() => router.push('/catalog')} variant="primary">
            Перейти в каталог
          </Button>
        </div>
      </div>
    </div>
  );
}
