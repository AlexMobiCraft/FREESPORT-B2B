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

// noindex не ставится: адрес закрыт Disallow в robots.txt, а такие адреса
// meta noindex не несут (решение D4) — робот страницу не читает и тег не увидит.
export const metadata: Metadata = {
  title: 'Корзина | OPTISPORT',
  description: 'Ваша корзина покупок. Просмотрите добавленные товары и оформите заказ.',
};

export default function CartPageRoute() {
  return <CartPage />;
}
