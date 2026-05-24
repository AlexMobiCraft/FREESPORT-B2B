/**
 * CartSkeleton Component
 *
 * Skeleton loader для страницы корзины:
 * - Отображается при загрузке данных
 * - Имитирует layout страницы: 3 карточки товаров + блок итогов
 * - Использует animate-pulse для shimmer эффекта
 */

'use client';

import { Skeleton } from '@/components/ui/Skeleton';

/**
 * Skeleton для карточки товара в корзине
 */
const CartItemSkeleton = () => (
  <div className="bg-white rounded-[var(--radius-md)] p-6 shadow-[var(--shadow-default)]">
    <div className="flex gap-4">
      {/* Image skeleton */}
      <Skeleton className="w-20 h-20 rounded-[var(--radius-sm)]" />

      {/* Content skeleton */}
      <div className="flex-1 space-y-2">
        <Skeleton className="h-5 w-3/4" />
        <Skeleton className="h-4 w-1/2" />
        <Skeleton className="h-4 w-1/3" />
      </div>

      {/* Price skeleton */}
      <div className="text-right space-y-2">
        <Skeleton className="h-5 w-24 ml-auto" />
        <Skeleton className="h-4 w-20 ml-auto" />
      </div>
    </div>
  </div>
);

/**
 * Skeleton для блока итогов
 */
const CartSummarySkeleton = () => (
  <div className="bg-white rounded-[var(--radius-md)] p-6 shadow-[var(--shadow-default)]">
    <Skeleton className="h-6 w-24 mb-4" />
    <div className="space-y-3">
      <div className="flex justify-between">
        <Skeleton className="h-4 w-20" />
        <Skeleton className="h-4 w-16" />
      </div>
      <div className="flex justify-between">
        <Skeleton className="h-4 w-16" />
        <Skeleton className="h-4 w-24" />
      </div>
      <hr className="border-neutral-200" />
      <div className="flex justify-between">
        <Skeleton className="h-5 w-20" />
        <Skeleton className="h-5 w-28" />
      </div>
    </div>
    <Skeleton className="h-12 w-full mt-6 rounded-[var(--radius-sm)]" />
  </div>
);

export const CartSkeleton = () => {
  return (
    <main
      className="max-w-[1280px] mx-auto px-4 lg:px-6 py-6"
      data-testid="cart-skeleton"
      role="main"
      aria-label="Загрузка корзины"
      aria-busy="true"
    >
      {/* Breadcrumb skeleton */}
      <div className="flex items-center gap-2 mb-6">
        <Skeleton className="h-4 w-16" />
        <Skeleton className="h-4 w-4" />
        <Skeleton className="h-4 w-20" />
      </div>

      {/* Title skeleton */}
      <Skeleton className="h-10 w-64 mb-8" />

      {/* Content grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Cart items skeleton - 2 колонки */}
        <div className="lg:col-span-2 space-y-4">
          <CartItemSkeleton />
          <CartItemSkeleton />
          <CartItemSkeleton />
        </div>

        {/* Cart summary skeleton - 1 колонка */}
        <div className="lg:col-span-1">
          <CartSummarySkeleton />
        </div>
      </div>
    </main>
  );
};

CartSkeleton.displayName = 'CartSkeleton';
