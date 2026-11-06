/**
 * ProductGrid Component
 *
 * Обертка для отображения карточек товаров в grid или list layout.
 * Поддерживает адаптивные стили согласно Design System v2.0.
 *
 * @see docs/stories/epic-12/12.4.story.md#task-8
 *
 * @example
 * ```tsx
 * <ProductGrid layout="grid">
 *   {products.map(product => (
 *     <ProductCard key={product.id} product={product} layout="grid" />
 *   ))}
 * </ProductGrid>
 * ```
 */

'use client';

import React from 'react';
import { cn } from '@/utils/cn';

export interface ProductGridProps {
  /** Вариант отображения */
  layout?: 'grid' | 'list';
  /** Дочерние элементы (ProductCard компоненты) */
  children: React.ReactNode;
  /** Дополнительные CSS классы */
  className?: string;
}

/**
 * Компонент ProductGrid
 */
export const ProductGrid: React.FC<ProductGridProps> = ({
  layout = 'grid',
  children,
  className,
}) => {
  if (layout === 'list') {
    return (
      <div className={cn('flex flex-col gap-4', className)} role="list">
        {children}
      </div>
    );
  }

  // Grid layout (адаптивный)
  return (
    <div
      className={cn(
        'grid gap-4',
        // Mobile: 2 карточки в ряд
        'grid-cols-2',
        // Tablet: 3 карточки в ряд
        'md:grid-cols-3',
        // Desktop: 4 карточки в ряд
        'lg:grid-cols-4',
        className
      )}
      role="list"
    >
      {children}
    </div>
  );
};

ProductGrid.displayName = 'ProductGrid';
