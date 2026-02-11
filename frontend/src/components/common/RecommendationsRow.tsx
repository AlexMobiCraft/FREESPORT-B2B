/**
 * RecommendationsRow Component
 *
 * Горизонтальная лента товаров с прокруткой (Story 11.2).
 * Используется для блоков "Хиты продаж" и "Новинки" на главной странице.
 *
 * Features:
 * - Горизонтальная прокрутка с scroll-snap
 * - Автоматическое отображение бейджей через ProductBadge
 * - Responsive дизайн (mobile, tablet, desktop)
 * - Hover эффекты на карточках
 *
 * @see frontend/docs/design-system.json#components.RecommendationsRow
 *
 * @example
 * ```tsx
 * <RecommendationsRow title="Хиты продаж" items={products} />
 * ```
 */

'use client';

import React from 'react';
import Link from 'next/link';
import Image from 'next/image';
import { Card } from '@/components/ui';
import { ProductBadge } from './ProductBadge';
import type { Product } from '@/types/api';
import { cn } from '@/utils/cn';

export interface RecommendationsRowProps {
  /** Заголовок секции */
  title: string;
  /** Массив товаров для отображения */
  items: Product[];
  /** Дополнительные CSS классы */
  className?: string;
}

/**
 * Компонент для отображения горизонтального ряда рекомендаций товаров
 */
export const RecommendationsRow: React.FC<RecommendationsRowProps> = ({
  title,
  items,
  className,
}) => {
  // Edge Case: Пустые данные - не отображаем блок
  if (!items || items.length === 0) {
    return null;
  }

  return (
    <section className={cn('py-12', className)} aria-labelledby={`${title}-heading`}>
      {/* Заголовок секции */}
      <h2 id={`${title}-heading`} className="text-title-m font-semibold mb-6 text-text-primary">
        {title}
      </h2>

      {/* Контейнер с горизонтальной прокруткой */}
      <div
        className={cn(
          // Горизонтальная прокрутка
          'flex gap-4 overflow-x-auto pb-4',
          // Scroll snap для плавной прокрутки
          'scroll-smooth snap-x snap-mandatory',
          // Скрыть scrollbar
          'scrollbar-hide',
          // Keyboard navigation support
          'focus-within:outline-none'
        )}
        role="list"
      >
        {items.map(product => (
          <Link
            key={product.id}
            href={`/products/${product.slug}`}
            className={cn(
              // Фиксированная ширина карточки
              'w-[180px] flex-shrink-0',
              // Scroll snap alignment
              'snap-start',
              // Focus ring для accessibility
              'focus:outline-none focus:ring-2 focus:ring-primary-500 focus:ring-offset-2 rounded-lg'
            )}
            role="listitem"
          >
            <Card hover className="h-full flex flex-col">
              {/* Изображение товара */}
              <div className="relative w-full h-[180px] mb-3 bg-neutral-100 rounded-md overflow-hidden">
                {/* Бейдж */}
                <div className="absolute top-2 left-2 z-10">
                  <ProductBadge product={product} />
                </div>

                {/* Изображение с fallback */}
                {product.images && product.images.length > 0 ? (
                  <Image
                    src={
                      product.images.find(img => img.is_primary)?.image || product.images[0].image
                    }
                    alt={product.name}
                    fill
                    sizes="180px"
                    className="object-cover"
                    loading="lazy"
                  />
                ) : (
                  // Edge Case: Товар без изображения - placeholder
                  <div className="w-full h-full flex items-center justify-center text-neutral-400">
                    <svg
                      xmlns="http://www.w3.org/2000/svg"
                      width="48"
                      height="48"
                      viewBox="0 0 24 24"
                      fill="none"
                      stroke="currentColor"
                      strokeWidth="2"
                      strokeLinecap="round"
                      strokeLinejoin="round"
                    >
                      <rect x="3" y="3" width="18" height="18" rx="2" ry="2"></rect>
                      <circle cx="8.5" cy="8.5" r="1.5"></circle>
                      <polyline points="21 15 16 10 5 21"></polyline>
                    </svg>
                  </div>
                )}
              </div>

              {/* Информация о товаре */}
              <div className="flex flex-col flex-1">
                {/* Название товара с обрезкой */}
                <h3
                  className={cn(
                    'text-body-s font-medium text-text-primary mb-2',
                    // Edge Case: Длинные названия - обрезать до 2 строк
                    'line-clamp-2'
                  )}
                  title={product.name}
                >
                  {product.name}
                </h3>

                {/* Цена */}
                <div className="mt-auto">
                  <p className="text-title-s font-semibold text-primary-600">
                    {product.retail_price.toLocaleString('ru-RU')} ₽
                  </p>

                  {/* Статус наличия */}
                  {!product.is_in_stock && (
                    <p className="text-caption text-text-secondary mt-1">Нет в наличии</p>
                  )}
                </div>
              </div>
            </Card>
          </Link>
        ))}
      </div>
    </section>
  );
};

RecommendationsRow.displayName = 'RecommendationsRow';
