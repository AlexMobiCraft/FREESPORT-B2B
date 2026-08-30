/**
 * CartPage Component
 *
 * Главный компонент страницы корзины:
 * - Интеграция с cartStore для данных корзины
 * - Hydration-safe паттерн для Zustand persist + SSR
 * - Loading/Error/Empty states
 * - Responsive двухколоночный layout
 */

'use client';

import { useEffect, useState } from 'react';
import { useCartStore } from '@/stores/cartStore';
import { Breadcrumb } from '@/components/ui';
import { EmptyCart } from './EmptyCart';
import { CartSkeleton } from './CartSkeleton';
import { CartError } from './CartError';
import { CartItemCard } from './CartItemCard';
import { CartSummary } from './CartSummary';

const breadcrumbItems = [{ label: 'Главная', href: '/' }, { label: 'Корзина' }];

export const CartPage = () => {
  const [mounted, setMounted] = useState(false);
  const { items, isLoading, error, fetchCart, updateQuantity, removeItem } = useCartStore();

  // Hydration: ждём монтирования на клиенте
  useEffect(() => {
    setMounted(true);
  }, []);

  // Загружаем корзину при монтировании (всегда синхронизируем с сервером)
  // ВАЖНО: Нельзя полагаться только на localStorage, т.к. там могут быть
  // устаревшие ID (optimistic updates), что приведёт к 404 при операциях
  useEffect(() => {
    if (mounted) {
      fetchCart();
    }
  }, [mounted, fetchCart]);

  // SSR: показываем skeleton до hydration
  if (!mounted) {
    return <CartSkeleton />;
  }

  // Loading state (только при первой загрузке, когда items пустые)
  if (isLoading && items.length === 0) {
    return <CartSkeleton />;
  }

  // Error state
  if (error) {
    return <CartError error={error} onRetry={fetchCart} />;
  }

  // Empty state
  if (items.length === 0) {
    return <EmptyCart />;
  }

  // Main content
  return (
    <main className="max-w-[1280px] mx-auto px-4 lg:px-6 py-6" data-testid="cart-page" role="main">
      <Breadcrumb items={breadcrumbItems} className="mb-6" data-testid="cart-breadcrumb" />

      <h1 className="text-display-m font-bold text-text-primary mb-8">Ваша корзина</h1>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Список товаров - 2 колонки на desktop */}
        <section
          className="lg:col-span-2 space-y-4"
          aria-label="Товары в корзине"
          data-testid="cart-items-list"
        >
          {items.map(item => (
            <CartItemCard
              key={item.id}
              item={item}
              onQuantityChange={updateQuantity}
              onRemove={removeItem}
            />
          ))}
        </section>

        {/* Итоги - 1 колонка, sticky на desktop */}
        <div className="lg:col-span-1">
          <CartSummary />
        </div>
      </div>
    </main>
  );
};

CartPage.displayName = 'CartPage';
