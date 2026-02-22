/**
 * SearchResults Component
 *
 * Компонент для отображения результатов поиска товаров в grid-формате.
 * Переиспользует ProductGrid и ProductCard для консистентного отображения.
 *
 * Features:
 * - Grid layout (2 колонки на mobile, 3 на tablet, 4 на desktop)
 * - Loading skeleton во время загрузки
 * - Адаптивный дизайн согласно Design System v2.0
 *
 * @see docs/stories/epic-18/18.2.search-results-page.md
 *
 * @example
 * ```tsx
 * <SearchResults
 *   products={searchResults}
 *   isLoading={isLoadingResults}
 * />
 * ```
 */

'use client';

import React from 'react';
import { ProductGrid } from '@/components/business/ProductGrid';
import { ProductCard } from '@/components/business/ProductCard';
import type { Product } from '@/types/api';

export interface SearchResultsProps {
  /** Список товаров для отображения */
  products: Product[];
  /** Состояние загрузки */
  isLoading?: boolean;
}

/**
 * Компонент SearchResults
 */
export const SearchResults: React.FC<SearchResultsProps> = ({ products, isLoading = false }) => {
  // Loading skeleton
  if (isLoading) {
    return (
      <div
        className="grid gap-4 grid-cols-2 md:grid-cols-3 lg:grid-cols-4"
        role="status"
        aria-label="Загрузка результатов поиска"
      >
        {Array.from({ length: 8 }).map((_, i) => (
          <div
            key={i}
            className="h-80 rounded-default bg-neutral-200 animate-pulse"
            aria-hidden="true"
          />
        ))}
        <span className="sr-only">Загрузка результатов...</span>
      </div>
    );
  }

  // Отображение результатов
  return (
    <ProductGrid layout="grid">
      {products.map(product => (
        <ProductCard key={product.id} product={product} layout="grid" userRole="retail" />
      ))}
    </ProductGrid>
  );
};

SearchResults.displayName = 'SearchResults';
