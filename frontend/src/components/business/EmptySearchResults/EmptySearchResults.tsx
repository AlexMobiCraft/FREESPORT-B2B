/**
 * EmptySearchResults Component
 *
 * Компонент для отображения состояния "Ничего не найдено" на странице поиска.
 * Показывает сообщение с рекомендациями для пользователя.
 *
 * Features:
 * - Иконка поиска
 * - Сообщение с запросом пользователя
 * - Подсказки для улучшения поиска
 * - Опциональный блок рекомендованных товаров
 * - WCAG 2.1 AA accessibility (role="status")
 *
 * @see docs/stories/epic-18/18.2.search-results-page.md
 *
 * @example
 * ```tsx
 * <EmptySearchResults
 *   query="nike running"
 *   recommendedProducts={popularProducts}
 * />
 * ```
 */

'use client';

import React from 'react';
import { Search } from 'lucide-react';
import { ProductCard } from '@/components/business/ProductCard';
import type { Product } from '@/types/api';

export interface EmptySearchResultsProps {
  /** Поисковый запрос пользователя */
  query: string;
  /** Опциональный список рекомендованных товаров */
  recommendedProducts?: Product[];
  /** Callback при клике на рекомендованный товар */
  onRecommendationClick?: (product: Product) => void;
}

/**
 * Компонент EmptySearchResults
 */
export const EmptySearchResults: React.FC<EmptySearchResultsProps> = ({
  query,
  recommendedProducts = [],
}) => {
  return (
    <div className="w-full py-12" role="status" aria-live="polite">
      {/* Основное сообщение */}
      <div className="flex flex-col items-center justify-center py-16 px-6 text-center">
        {/* Иконка поиска */}
        <div className="w-20 h-20 rounded-3xl bg-secondary-subtle flex items-center justify-center mb-6">
          <Search className="w-12 h-12 text-secondary" aria-hidden="true" />
        </div>

        {/* Заголовок */}
        <h2 className="text-title-m font-semibold text-primary mb-2">
          По запросу «{query}» ничего не найдено
        </h2>

        {/* Подсказки */}
        <div className="text-body-m text-secondary max-w-md mb-8">
          <p className="mb-4">Попробуйте:</p>
          <ul className="text-left space-y-2">
            <li>• Изменить поисковый запрос</li>
            <li>• Проверить правильность написания</li>
            <li>• Использовать более общие термины</li>
            <li>• Воспользоваться фильтрами в каталоге</li>
          </ul>
        </div>
      </div>

      {/* Рекомендованные товары */}
      {recommendedProducts.length > 0 && (
        <section className="mt-12" aria-labelledby="recommended-products-heading">
          <h3
            id="recommended-products-heading"
            className="text-title-m font-semibold text-primary mb-6 text-center"
          >
            Популярные товары
          </h3>

          <div className="grid gap-4 grid-cols-2 md:grid-cols-3 lg:grid-cols-4">
            {recommendedProducts.slice(0, 4).map(product => (
              <ProductCard key={product.id} product={product} layout="grid" userRole="retail" />
            ))}
          </div>
        </section>
      )}
    </div>
  );
};

EmptySearchResults.displayName = 'EmptySearchResults';
