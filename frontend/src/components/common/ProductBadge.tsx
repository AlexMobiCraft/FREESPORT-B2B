/**
 * ProductBadge Component
 *
 * Автоматически определяет и отображает бейдж товара на основе маркетинговых флагов (Story 11.0).
 *
 * Приоритет определения бейджа (от высшего к низшему):
 * 1. sale (распродажа с процентом скидки)
 * 2. promo (акция)
 * 3. new (новинка)
 * 4. hit (хит продаж)
 * 5. premium (премиум товар)
 *
 * @example
 * ```tsx
 * <ProductBadge product={product} />
 * ```
 */

import React from 'react';
import { Badge, type BadgeVariant } from '@/components/ui';
import type { Product } from '@/types/api';

export interface ProductBadgeProps {
  /** Товар с маркетинговыми флагами */
  product: Product;
  /** Дополнительные CSS классы */
  className?: string;
}

/**
 * Определяет вариант бейджа на основе приоритета флагов
 */
function determineBadge(product: Product): { variant: BadgeVariant; label: string } | null {
  // Приоритет 1: Распродажа с процентом скидки
  if (product.is_sale && product.discount_percent) {
    return {
      variant: 'sale',
      label: `${product.discount_percent}% скидка`,
    };
  }

  // Приоритет 2: Акция
  if (product.is_promo) {
    return {
      variant: 'promo',
      label: 'Акция',
    };
  }

  // Приоритет 3: Новинка
  if (product.is_new) {
    return {
      variant: 'new',
      label: 'Новинка',
    };
  }

  // Приоритет 4: Хит продаж
  if (product.is_hit) {
    return {
      variant: 'hit',
      label: 'Хит',
    };
  }

  // Приоритет 5: Премиум
  if (product.is_premium) {
    return {
      variant: 'premium',
      label: 'Премиум',
    };
  }

  // Нет активных бейджей
  return null;
}

export const ProductBadge: React.FC<ProductBadgeProps> = ({ product, className }) => {
  const badge = determineBadge(product);

  if (!badge) {
    return null;
  }

  return (
    <Badge variant={badge.variant} className={className}>
      {badge.label}
    </Badge>
  );
};

ProductBadge.displayName = 'ProductBadge';
