/**
 * CategoriesSection Component
 *
 * Блок "Популярные категории" на главной странице.
 * Горизонтальный carousel с карточками корневых категорий,
 * отсортированных по приоритету (sort_order).
 *
 * - Desktop: карточки ~250px, стрелки навигации
 * - Mobile: touch scroll, без стрелок, "peek" эффект
 *
 * @example
 * ```tsx
 * <CategoriesSection />
 * ```
 */

'use client';

import React, { useState, useEffect, useRef, useCallback } from 'react';
import Link from 'next/link';
import Image from 'next/image';
import { ChevronLeft, ChevronRight } from 'lucide-react';
import categoriesService from '@/services/categoriesService';
import type { Category } from '@/types/api';

const PLACEHOLDER_IMAGE = '/images/category-placeholder.png';
const CARD_LAYOUT_CLASSES = 'flex-shrink-0 w-[80vw] sm:w-[40vw] md:w-[250px]';

/**
 * Loading Skeleton для карусели категорий
 */
const CategoriesSkeleton: React.FC = () => (
  <div aria-label="Загрузка категорий" role="status" aria-live="polite">
    <div className="flex gap-4 overflow-hidden">
      {[...Array(5)].map((_, index) => (
        <div
          key={index}
          className={`${CARD_LAYOUT_CLASSES} bg-neutral-100 rounded-lg animate-pulse`}
          aria-hidden="true"
        >
          <div className="aspect-[4/3] bg-neutral-200 rounded-t-lg" />
          <div className="p-3 space-y-2">
            <div className="h-4 bg-neutral-200 rounded w-3/4 mx-auto" />
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
 * Карточка категории
 */
interface CategoryCardProps {
  category: Category;
}

const CategoryCard: React.FC<CategoryCardProps> = ({ category }) => {
  const imageSrc = category.image || PLACEHOLDER_IMAGE;

  return (
    <Link
      href={`/catalog?category=${category.slug}`}
      className={`${CARD_LAYOUT_CLASSES} snap-start block rounded-lg overflow-hidden shadow-default hover:shadow-hover transition-shadow bg-white group`}
      data-testid="category-card"
    >
      <div className="aspect-[4/3] overflow-hidden bg-neutral-100 relative">
        <Image
          src={imageSrc}
          alt={category.name}
          fill
          className="object-cover group-hover:scale-105 transition-transform duration-300"
          sizes="(max-width: 640px) 80vw, (max-width: 768px) 40vw, 250px"
        />
      </div>
      <div className="p-3 text-center">
        <h3 className="text-base font-semibold text-text-primary truncate">{category.name}</h3>
        {category.products_count !== undefined && category.products_count > 0 && (
          <p className="text-xs text-text-secondary mt-1">{category.products_count} товаров</p>
        )}
      </div>
    </Link>
  );
};

/**
 * Компонент-карусель "Популярные категории"
 */
export const CategoriesSection: React.FC = () => {
  const [categories, setCategories] = useState<Category[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);
  const [canScrollLeft, setCanScrollLeft] = useState(false);
  const [canScrollRight, setCanScrollRight] = useState(false);

  const loadCategories = async () => {
    try {
      setIsLoading(true);
      setError(null);
      const data = await categoriesService.getCategories({
        is_homepage: true,
        ordering: 'sort_order',
        limit: 50,
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

  const updateScrollButtons = useCallback(() => {
    const el = scrollRef.current;
    if (!el) return;
    setCanScrollLeft(el.scrollLeft > 0);
    setCanScrollRight(el.scrollLeft + el.clientWidth < el.scrollWidth - 1);
  }, []);

  useEffect(() => {
    const el = scrollRef.current;
    if (!el) return;

    // Initial check
    updateScrollButtons();

    // Add listeners
    el.addEventListener('scroll', updateScrollButtons, { passive: true });
    window.addEventListener('resize', updateScrollButtons);

    return () => {
      el.removeEventListener('scroll', updateScrollButtons);
      window.removeEventListener('resize', updateScrollButtons);
    };
    // updateScrollButtons is stable (useCallback []), so this effect only runs when categories/isLoading change
  }, [isLoading, categories, updateScrollButtons]);

  const scroll = (direction: 'left' | 'right') => {
    scrollRef.current?.scrollBy({
      left: direction === 'left' ? -300 : 300,
      behavior: 'smooth',
    });
  };

  // Не рендерим секцию если нет категорий и не идет загрузка
  if (!isLoading && !error && (!categories || categories.length === 0)) {
    return null;
  }

  return (
    <section
      className="max-w-[1280px] mx-auto px-3 md:px-4 lg:px-6 mb-16"
      aria-labelledby="categories-heading"
    >
      <h2 id="categories-heading" className="text-3xl font-bold mb-8 text-text-primary">
        Популярные категории
      </h2>

      {/* Loading State */}
      {isLoading && <CategoriesSkeleton />}

      {/* Error State */}
      {error && !isLoading && <ErrorState onRetry={loadCategories} />}

      {/* Success State — Carousel */}
      {!isLoading && !error && categories.length > 0 && (
        <div className="relative group">
          {/* Стрелка влево (desktop only) */}
          {canScrollLeft && (
            <button
              type="button"
              onClick={() => scroll('left')}
              className="hidden md:flex absolute -left-3 top-1/2 -translate-y-1/2 z-10 w-10 h-10 items-center justify-center rounded-full bg-white shadow-md hover:shadow-lg transition-shadow border border-neutral-200"
              aria-label="Прокрутить влево"
            >
              <ChevronLeft className="w-5 h-5 text-neutral-600" />
            </button>
          )}

          <div
            ref={scrollRef}
            className="flex gap-4 overflow-x-auto snap-x snap-mandatory scrollbar-hide"
            role="list"
            aria-label="Карусель категорий"
          >
            {categories.map(category => (
              <div key={category.id} role="listitem">
                <CategoryCard category={category} />
              </div>
            ))}
          </div>

          {/* Стрелка вправо (desktop only) */}
          {canScrollRight && (
            <button
              type="button"
              onClick={() => scroll('right')}
              className="hidden md:flex absolute -right-3 top-1/2 -translate-y-1/2 z-10 w-10 h-10 items-center justify-center rounded-full bg-white shadow-md hover:shadow-lg transition-shadow border border-neutral-200"
              aria-label="Прокрутить вправо"
            >
              <ChevronRight className="w-5 h-5 text-neutral-600" />
            </button>
          )}
        </div>
      )}
    </section>
  );
};

CategoriesSection.displayName = 'CategoriesSection';
