/**
 * Order Detail Page - SSR Version
 * Страница детального просмотра заказа с SSR для первичной загрузки
 * Story 16.2 - AC: 2, 4, 5, 6
 *
 * Гибридный подход:
 * - Server Component загружает данные заказа (SSR)
 * - OrderDetailClient обрабатывает интерактивность (CSR)
 *
 * ПРИМЕЧАНИЕ: Для активации SSR переименуйте этот файл в page.tsx
 * и удалите текущий page.tsx (CSR версию)
 */

import { notFound } from 'next/navigation';
import { Suspense } from 'react';
import { OrderDetailClient } from '@/components/business/OrderDetail';
import { Spinner } from '@/components/ui';
import { getOrderByIdServer } from '@/services/ordersService.server';

interface OrderDetailPageProps {
  params: Promise<{ id: string }>;
}

/**
 * Server Component - загружает данные заказа на сервере
 */
async function OrderDetailContent({ orderId }: { orderId: string }) {
  const order = await getOrderByIdServer(orderId);

  if (!order) {
    notFound();
  }

  return <OrderDetailClient order={order} />;
}

/**
 * SSR страница детального просмотра заказа
 * Данные загружаются на сервере для быстрого первичного рендера
 */
export default async function OrderDetailPage({ params }: OrderDetailPageProps) {
  const { id } = await params;

  return (
    <Suspense
      fallback={
        <div className="flex items-center justify-center py-16">
          <Spinner size="large" />
        </div>
      }
    >
      <OrderDetailContent orderId={id} />
    </Suspense>
  );
}

/**
 * Metadata для SEO (опционально)
 */
export async function generateMetadata({ params }: OrderDetailPageProps) {
  const { id } = await params;

  return {
    title: `Заказ #${id} | FREESPORT`,
    description: 'Детальная информация о заказе',
  };
}
