import { Metadata } from 'next';
import { CheckoutPageClient } from './CheckoutPageClient';

/**
 * Метаданные для страницы оформления заказа
 * Оптимизированы для SEO
 */
// noindex не ставится: адрес закрыт Disallow в robots.txt, а такие адреса
// meta noindex не несут (решение D4) — робот страницу не читает и тег не увидит.
export const metadata: Metadata = {
  title: 'Оформление заказа | OPTISPORT',
  description:
    'Оформите заказ на спортивные товары с удобной формой доставки. Быстрое оформление с автозаполнением данных.',
};

/**
 * Страница оформления заказа (Server Component)
 *
 * Story 15.1: Checkout страница и упрощённая форма
 *
 * Используется Next.js App Router с SSR для:
 * - SEO оптимизации
 * - Автозаполнения данных авторизованного пользователя
 * - Быстрой загрузки страницы
 *
 * Архитектура:
 * - page.tsx (Server Component) - мета-теги и layout
 * - CheckoutPageClient (Client Component) - интерактивная форма
 */
export default function CheckoutPage() {
  return (
    <div className="min-h-screen bg-gray-50">
      <CheckoutPageClient />
    </div>
  );
}
