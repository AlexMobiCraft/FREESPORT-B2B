/**
 * CategoriesSection Component
 *
 * Блок "Популярные категории" на главной странице (Story 11.2).
 * Отображает до 6 корневых категорий с использованием API.
 *
 * Features:
 * - API integration через categoriesService
 * - Loading skeleton
 * - Error state с retry функциональностью
 * - Responsive grid layout
 *
 * @example
 * ```tsx
 * <CategoriesSection />
 * ```
 */

'use client';

import React, { useState, useEffect } from 'react';
import categoriesService from '@/services/categoriesService';
import type { Category } from '@/types/api';

/**
 * Loading Skeleton для категорий
 */
const CategoriesSkeleton: React.FC = () => (
  <div aria-label="Загрузка категорий" role="status" aria-live="polite">
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6" role="list">
      {[...Array(6)].map((_, index) => (
        <div
          key={index}
          className="bg-neutral-100 rounded-lg animate-pulse"
          role="listitem"
          aria-hidden="true"
        >
          <div className="aspect-square bg-neutral-200 rounded-t-lg" />
          <div className="p-4 space-y-3">
            <div className="h-5 bg-neutral-200 rounded w-3/4 mx-auto" />
            <div className="h-4 bg-neutral-200 rounded w-1/2 mx-auto" />
          </div>
        </div>
      ))}
    </div>
  </div>
);

/**
 * Error State с retry кнопкой
 */
interface ErrorStateProps {
  onRetry: () => void;
}

const ErrorState: React.FC<ErrorStateProps> = ({ onRetry }) => (
  <div className="text-center py-12">
    <p className="text-body text-text-secondary mb-4">Не удалось загрузить категории</p>
    <button
      onClick={onRetry}
      className="px-6 py-2 bg-primary text-white rounded-lg hover:bg-primary-hover transition-colors"
      type="button"
    >
      Повторить попытку
    </button>
  </div>
);

/**
 * Компонент блока "Популярные категории"
 */
export const CategoriesSection: React.FC = () => {
  const [categories, setCategories] = useState<Category[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  const loadCategories = async () => {
    try {
      setIsLoading(true);
      setError(null);
      const data = await categoriesService.getCategories({
        parent_id__isnull: true,
        limit: 6,
      });
      setCategories(data);
    } catch (err) {
      setError(err instanceof Error ? err : new Error('Failed to load categories'));
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    loadCategories();
  }, []);

  // Не рендерим секцию если нет категорий и не идет загрузка
  if (!isLoading && !error && (!categories || categories.length === 0)) {
    return null;
  }

  return (
    <section
      className="max-w-[1280px] mx-auto px-3 md:px-4 lg:px-6 mb-16"
      aria-labelledby="categories-heading"
    >
      {/* Заголовок секции */}
      <h2 id="categories-heading" className="text-3xl font-bold mb-8 text-text-primary">
        Популярные категории
      </h2>

      {/* Loading State */}
      {isLoading && <CategoriesSkeleton />}

      {/* Error State */}
      {error && !isLoading && <ErrorState onRetry={loadCategories} />}

      {/* Success State - Grid с категориями */}
      {!isLoading && !error && categories.length > 0 && (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6" role="list">
          {categories.map(category => (
            <a
              key={category.id}
              href={`/catalog/${category.slug}`}
              role="listitem"
              className="block bg-white rounded-lg shadow-default hover:shadow-hover transition-shadow p-6 text-center"
            >
              {/* Иконка категории */}
              {category.icon && (
                <div className="text-5xl mb-4" aria-hidden="true">
                  {category.icon}
                </div>
              )}

              {/* Название категории */}
              <h3 className="text-xl font-semibold text-text-primary mb-2">{category.name}</h3>

              {/* Количество товаров */}
              {category.products_count !== undefined && (
                <p className="text-sm text-text-secondary">{category.products_count} товаров</p>
              )}
            </a>
          ))}
        </div>
      )}
    </section>
  );
};

CategoriesSection.displayName = 'CategoriesSection';
