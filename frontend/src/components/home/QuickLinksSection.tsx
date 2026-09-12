/**
 * QuickLinksSection Component
 *
 * Горизонтальная секция быстрых ссылок на главной странице.
 * Первые 3 элемента (Новинки, Хиты, Скидки) — фиксированные.
 * Категории товаров — горизонтально прокручиваемые.
 *
 * Дизайн: иконки в цветных кружках + текст рядом, без видимых границ кнопок.
 *
 * @example
 * ```tsx
 * <QuickLinksSection />
 * ```
 */

'use client';

import React, { useState, useEffect, useRef, useCallback } from 'react';
import NextImage from 'next/image';
import Link from 'next/link';
import { ChevronLeft, ChevronRight } from 'lucide-react';
import categoriesService from '@/services/categoriesService';
import type { Category, CategoryTree } from '@/types/api';
import { STATIC_QUICK_LINKS } from '@/config/quickLinks';

import { normalizeImageUrl } from '@/utils/media';

export const QuickLinksSection: React.FC = () => {
  const [categories, setCategories] = useState<(Category | CategoryTree)[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const scrollRef = useRef<HTMLDivElement>(null);
  const [canScrollLeft, setCanScrollLeft] = useState(false);
  const [canScrollRight, setCanScrollRight] = useState(false);

  // Загрузка публичного дерева категорий
  useEffect(() => {
    const loadCategories = async () => {
      try {
        const tree = await categoriesService.getTree();
        setCategories(tree);
      } catch {
        setCategories([]);
      } finally {
        setIsLoading(false);
      }
    };
    loadCategories();
  }, []);

  // Обновление состояния кнопок скролла (только для категорий)
  const updateScrollButtons = useCallback(() => {
    const el = scrollRef.current;
    if (!el) return;
    setCanScrollLeft(el.scrollLeft > 0);
    setCanScrollRight(el.scrollLeft + el.clientWidth < el.scrollWidth - 1);
  }, []);

  useEffect(() => {
    const el = scrollRef.current;
    if (!el) return;

    updateScrollButtons();
    el.addEventListener('scroll', updateScrollButtons, { passive: true });
    window.addEventListener('resize', updateScrollButtons);

    return () => {
      el.removeEventListener('scroll', updateScrollButtons);
      window.removeEventListener('resize', updateScrollButtons);
    };
  }, [isLoading, categories, updateScrollButtons]);

  const scroll = (direction: 'left' | 'right') => {
    scrollRef.current?.scrollBy({
      left: direction === 'left' ? -300 : 300,
      behavior: 'smooth',
    });
  };

  return (
    <section
      className="relative max-w-[1280px] mx-auto px-3 md:px-4 lg:px-6 py-4 md:py-6"
      aria-label="Быстрые ссылки"
    >
      <div className="flex items-center gap-1 overflow-x-auto md:overflow-visible scrollbar-hide md:scrollbar-default snap-x snap-mandatory md:snap-none">
        {/* Фиксированные быстрые ссылки */}
        <div
          className="flex items-center gap-1 flex-shrink-0 snap-start md:snap-align-none"
          role="list"
          aria-label="Быстрые фильтры"
        >
          {STATIC_QUICK_LINKS.map(item => (
            <Link
              key={item.variant}
              href={item.link}
              role="listitem"
              className="
                                flex-shrink-0 inline-flex items-center gap-2
                                px-3 py-2 rounded-xl
                                text-sm font-medium text-[var(--color-text-primary,#1a1a1a)]
                                hover:bg-neutral-100 transition-colors duration-200
                            "
            >
              <span
                className={`
                                    flex items-center justify-center
                                    w-8 h-8 rounded-full
                                    ${item.color} text-white
                                `}
                aria-hidden="true"
              >
                {item.icon}
              </span>
              <span>{item.label}</span>
            </Link>
          ))}
        </div>

        {/* Разделитель */}
        <div className="w-px h-8 bg-neutral-200 flex-shrink-0 mx-1" aria-hidden="true" />

        {/* Прокручиваемые категории */}
        <div className="relative shrink-0 md:shrink md:flex-1 md:min-w-0 group">
          {/* Стрелка влево */}
          {canScrollLeft && (
            <button
              type="button"
              onClick={() => scroll('left')}
              className="hidden md:flex absolute left-0 top-1/2 -translate-y-1/2 -translate-x-1 z-10 w-8 h-8 items-center justify-center rounded-full bg-white shadow-md hover:shadow-lg transition-shadow border border-neutral-200"
              aria-label="Прокрутить влево"
            >
              <ChevronLeft className="w-4 h-4 text-neutral-600" />
            </button>
          )}

          <div
            ref={scrollRef}
            className="flex gap-1 overflow-visible md:overflow-x-auto md:snap-x md:snap-mandatory scrollbar-hide"
            role="list"
            aria-label="Категории товаров"
          >
            {/* Loading skeleton */}
            {isLoading &&
              [...Array(4)].map((_, i) => (
                <div
                  key={`skeleton-${i}`}
                  className="flex-shrink-0 snap-start flex items-center gap-2 px-3 py-2"
                  role="listitem"
                  aria-hidden="true"
                >
                  <div className="w-8 h-8 rounded-full bg-neutral-200 animate-pulse" />
                  <div className="w-16 h-4 rounded bg-neutral-200 animate-pulse" />
                </div>
              ))}

            {/* Динамические категории */}
            {!isLoading &&
              categories.map(category => (
                <Link
                  key={category.id}
                  href={`/catalog?category=${category.slug}`}
                  role="listitem"
                  className="
                                        flex-shrink-0 snap-start inline-flex items-center gap-2
                                        px-3 py-2 rounded-xl
                                        text-sm font-medium text-[var(--color-text-primary,#1a1a1a)]
                                        hover:bg-neutral-100 transition-colors duration-200
                                    "
                >
                  {category.icon && (
                    <span
                      className="flex items-center justify-center w-8 h-8 rounded-full bg-neutral-100 text-base flex-shrink-0"
                      aria-hidden="true"
                    >
                      <NextImage
                        src={normalizeImageUrl(category.icon)}
                        alt=""
                        width={20}
                        height={20}
                        unoptimized
                        className="w-5 h-5 object-contain"
                        onError={(e: React.SyntheticEvent<HTMLImageElement>) => {
                          // Fallback if image fails to load (maybe it WAS an emoji?)
                          const target = e.currentTarget;
                          if (category.icon && !category.icon.includes('/')) {
                            target.parentElement!.innerText = category.icon;
                            target.remove();
                          }
                        }}
                      />
                    </span>
                  )}
                  <span>{category.name}</span>
                </Link>
              ))}
          </div>

          {/* Стрелка вправо */}
          {canScrollRight && (
            <button
              type="button"
              onClick={() => scroll('right')}
              className="hidden md:flex absolute right-0 top-1/2 -translate-y-1/2 translate-x-1 z-10 w-8 h-8 items-center justify-center rounded-full bg-white shadow-md hover:shadow-lg transition-shadow border border-neutral-200"
              aria-label="Прокрутить вправо"
            >
              <ChevronRight className="w-4 h-4 text-neutral-600" />
            </button>
          )}
        </div>
      </div>
    </section>
  );
};

QuickLinksSection.displayName = 'QuickLinksSection';
