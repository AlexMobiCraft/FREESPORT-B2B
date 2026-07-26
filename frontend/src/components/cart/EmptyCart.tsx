/**
 * EmptyCart Component
 *
 * Отображается когда корзина пуста:
 * - Иконка пустой корзины
 * - Текст "Ваша корзина пуста"
 * - CTA кнопка "В каталог"
 */

'use client';

import Link from 'next/link';
import { ShoppingCart } from 'lucide-react';
import { Breadcrumb } from '@/components/ui';

const breadcrumbItems = [{ label: 'Главная', href: '/' }, { label: 'Корзина' }];

export const EmptyCart = () => {
  return (
    <main className="max-w-[1280px] mx-auto px-4 lg:px-6 py-6" data-testid="empty-cart" role="main">
      <Breadcrumb items={breadcrumbItems} className="mb-6" />

      <h1 className="text-display-m font-bold text-text-primary mb-8">Ваша корзина</h1>

      <div className="flex flex-col items-center justify-center py-16 bg-white rounded-[var(--radius-md)] shadow-[var(--shadow-default)]">
        <ShoppingCart className="w-16 h-16 text-neutral-500 mb-6" aria-hidden="true" />

        <h2 className="text-title-l font-semibold text-text-primary mb-2">Ваша корзина пуста</h2>

        <p className="text-body-m text-text-secondary mb-8">Добавьте товары из каталога</p>

        <Link
          href="/catalog"
          className="h-12 px-8 inline-flex items-center justify-center bg-primary hover:bg-primary-hover text-text-inverse font-medium rounded-[var(--radius-sm)] transition-colors"
          data-testid="go-to-catalog-button"
        >
          В каталог
        </Link>
      </div>
    </main>
  );
};

EmptyCart.displayName = 'EmptyCart';
