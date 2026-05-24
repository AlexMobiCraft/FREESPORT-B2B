/**
 * Страница корзины (/cart)
 *
 * Отображает содержимое корзины пользователя:
 * - Список добавленных товаров
 * - Блок итогов заказа
 * - Пустое состояние при отсутствии товаров
 */

import type { Metadata } from 'next';
import { CartPage } from '@/components/cart';

export const metadata: Metadata = {
  title: 'Корзина | FREESPORT',
  description: 'Ваша корзина покупок. Просмотрите добавленные товары и оформите заказ.',
  robots: {
    index: false,
    follow: true,
  },
};

export default function CartPageRoute() {
  return <CartPage />;
}
