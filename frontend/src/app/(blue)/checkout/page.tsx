import { Metadata } from 'next';
import { CheckoutPageClient } from './CheckoutPageClient';

/**
 * Метаданные для страницы оформления заказа
 * Оптимизированы для SEO
 */
export const metadata: Metadata = {
  title: 'Оформление заказа | FREESPORT',
  description:
    'Оформите заказ на спортивные товары с удобной формой доставки. Быстрое оформление с автозаполнением данных.',
  robots: 'noindex, nofollow', // Checkout страницы не индексируются
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
