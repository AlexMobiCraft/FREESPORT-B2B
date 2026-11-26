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
import { normalizeImageUrl } from '@/utils/media';

const PLACEHOLDER_IMAGE = '/images/category-placeholder.png';
const CARD_LAYOUT_CLASSES = 'flex-shrink-0 w-[calc(50%-4px)] md:w-[200px]';

/**
 * Loading Skeleton для карусели категорий
 */
const CategoriesSkeleton: React.FC = () => (
  <div aria-label="Загрузка категорий" role="status" aria-live="polite">
    <div className="flex gap-2 overflow-x-auto snap-x snap-mandatory scrollbar-hide py-2 lg:mx-4">
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
  const isIcon = Boolean(category.icon);
  const rawImageSrc = category.icon || category.image;
  const imageSrc = rawImageSrc ? normalizeImageUrl(rawImageSrc) : PLACEHOLDER_IMAGE;

  return (
    <Link
      href={`/catalog?category=${category.slug}`}
      className="block w-full rounded-lg overflow-hidden shadow-default hover:shadow-hover transition-shadow bg-white group flex flex-col"
      data-testid="category-card"
    >
      <div className="aspect-[4/3] overflow-hidden bg-neutral-100 flex-shrink-0 relative">
        <Image
          src={imageSrc}
          alt={category.name}
          fill
          className={`${isIcon ? 'object-contain p-6 group-hover:scale-110 hover:drop-shadow-sm' : 'object-cover group-hover:scale-105'} transition-transform duration-300`}
          sizes="(max-width: 640px) 50vw, 200px"
        />
      </div>
      <div className="p-3 text-center">
        <h3 className="text-sm md:text-base font-semibold text-text-primary line-clamp-2 min-h-[2.5rem] md:min-h-[3rem] flex items-center justify-center">
          {category.name}
        </h3>
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
      className="max-w-[1316px] mx-auto px-3 md:px-4 lg:px-6 mb-16 relative"
      aria-labelledby="categories-heading"
    >
      <h2 id="categories-heading" className="text-3xl font-bold mb-8 text-text-primary">
        Популярные категории
      </h2>

      {/* Loading State */}
      {isLoading && <CategoriesSkeleton />}

      {/* Error State */}
      {error && !isLoading && <ErrorState onRetry={loadCategories} />}

      {/* Стрелка влево (desktop only) */}
      {canScrollLeft && !isLoading && !error && categories.length > 0 && (
        <button
          type="button"
          onClick={() => scroll('left')}
          className="absolute left-0 top-1/2 -translate-y-1/2 z-10 hidden lg:flex items-center justify-center w-12 h-12 bg-transparent text-primary focus:outline-none hover:opacity-80 transition-opacity"
          aria-label="Прокрутить влево"
        >
          <ChevronLeft className="w-7 h-7" />
        </button>
      )}

      {/* Стрелка вправо (desktop only) */}
      {canScrollRight && !isLoading && !error && categories.length > 0 && (
        <button
          type="button"
          onClick={() => scroll('right')}
          className="absolute right-0 top-1/2 -translate-y-1/2 z-10 hidden lg:flex items-center justify-center w-12 h-12 bg-transparent text-primary focus:outline-none hover:opacity-80 transition-opacity"
          aria-label="Прокрутить вправо"
        >
          <ChevronRight className="w-7 h-7" />
        </button>
      )}

      {/* Success State — Carousel */}
      {!isLoading && !error && categories.length > 0 && (
        <div
          ref={scrollRef}
          className="flex gap-2 overflow-x-auto snap-x snap-mandatory scrollbar-hide py-2 lg:mx-4"
          role="list"
          aria-label="Карусель категорий"
        >
          {categories.map(category => (
            <div key={category.id} role="listitem" className={`${CARD_LAYOUT_CLASSES} snap-start`}>
              <CategoryCard category={category} />
            </div>
          ))}
        </div>
      )}
    </section>
  );
};

CategoriesSection.displayName = 'CategoriesSection';
