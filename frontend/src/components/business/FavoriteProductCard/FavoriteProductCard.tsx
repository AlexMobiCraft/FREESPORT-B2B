/**
 * FavoriteProductCard Component - Карточка товара в избранном
 * Story 16.3: Управление избранными товарами (AC: 4, 5, 6, 7)
 *
 * Отображает:
 * - Изображение товара
 * - Название и SKU
 * - Цена
 * - Бейдж "Нет в наличии" (AC: 7)
 * - Кнопка "В корзину" (AC: 5)
 * - Кнопка удаления из избранного (AC: 6)
 */

'use client';

import React from 'react';
import Image from 'next/image';
import Link from 'next/link';
import { Heart } from 'lucide-react';
import { cn } from '@/utils/cn';
import { Button } from '@/components/ui';
import type { FavoriteWithAvailability } from '@/types/favorite';

// Формирование полного URL для изображений
const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? '';
const MEDIA_BASE_URL =
  process.env.NEXT_PUBLIC_MEDIA_URL ||
  (API_BASE_URL ? API_BASE_URL.replace(/\/api(?:\/v\d+)?\/?$/, '') : '');

const resolveImageUrl = (path?: string | null): string | null => {
  if (!path) return null;
  if (/^(data|blob):/i.test(path)) {
    return path;
  }

  const publicBase = MEDIA_BASE_URL || '';

  if (/^https?:\/\//i.test(path)) {
    if (path.startsWith('http://backend:8000')) {
      return path.replace('http://backend:8000', publicBase);
    }
    if (path.startsWith('http://nginx')) {
      return path.replace('http://nginx', publicBase);
    }
    return path;
  }

  // Путь относительный — добавляем публичный базовый URL
  if (publicBase) {
    // Добавляем /media/ если путь не начинается с /
    if (path.startsWith('/')) {
      return `${publicBase}${path}`;
    }
    return `${publicBase}/media/${path}`;
  }

  return path;
};

export interface FavoriteProductCardProps {
  /** Данные избранного товара */
  favorite: FavoriteWithAvailability;
  /** Callback добавления в корзину */
  onAddToCart: () => void;
  /** Callback удаления из избранного */
  onRemoveFavorite: () => void;
  /** Флаг загрузки добавления в корзину */
  isAddingToCart?: boolean;
  /** Флаг удаления */
  isRemoving?: boolean;
}

/**
 * Компонент карточки товара в избранном
 */
export const FavoriteProductCard: React.FC<FavoriteProductCardProps> = ({
  favorite,
  onAddToCart,
  onRemoveFavorite,
  isAddingToCart = false,
  isRemoving = false,
}) => {
  const { isAvailable } = favorite;

  return (
    <div
      className={cn(
        'bg-white rounded-[16px] overflow-hidden',
        'shadow-[0_8px_24px_rgba(15,23,42,0.08)]',
        'hover:shadow-[0_10px_32px_rgba(15,23,42,0.12)]',
        'transition-all duration-200',
        isRemoving && 'opacity-50 pointer-events-none'
      )}
      data-testid="favorite-card"
    >
      {/* Изображение */}
      <Link href={`/product/${favorite.product_slug}`} className="block relative">
        <div className="aspect-square relative bg-[var(--color-neutral-200)]">
          {resolveImageUrl(favorite.product_image) ? (
            <Image
              src={resolveImageUrl(favorite.product_image)!}
              alt={favorite.product_name}
              fill
              className="object-cover"
              sizes="(max-width: 768px) 100vw, (max-width: 1024px) 50vw, 33vw"
            />
          ) : (
            <div className="absolute inset-0 flex items-center justify-center">
              <span className="text-[var(--color-text-muted)]">Нет фото</span>
            </div>
          )}

          {/* Бейдж "Нет в наличии" (AC: 7) */}
          {!isAvailable && (
            <div
              className={cn(
                'absolute top-3 left-3',
                'px-3 py-1 rounded-full',
                'bg-[var(--color-accent-danger-bg)] text-[var(--color-accent-danger)]',
                'text-[12px] font-medium'
              )}
              data-testid="out-of-stock-badge"
            >
              Нет в наличии
            </div>
          )}

          {/* Кнопка удаления из избранного (AC: 6) */}
          <button
            onClick={e => {
              e.preventDefault();
              e.stopPropagation();
              onRemoveFavorite();
            }}
            className={cn(
              'absolute top-3 right-3',
              'w-10 h-10 rounded-full',
              'bg-white/90 backdrop-blur-sm',
              'flex items-center justify-center',
              'hover:bg-white hover:scale-110',
              'transition-all duration-150',
              'shadow-[0_2px_8px_rgba(0,0,0,0.1)]'
            )}
            aria-label="Удалить из избранного"
            disabled={isRemoving}
          >
            <Heart className="w-5 h-5 text-[var(--color-accent-danger)] fill-[var(--color-accent-danger)]" />
          </button>
        </div>
      </Link>

      {/* Контент */}
      <div className="p-4">
        {/* Название */}
        <Link href={`/product/${favorite.product_slug}`}>
          <h3 className="text-[16px] leading-[24px] font-medium text-[var(--color-text-primary)] mb-1 line-clamp-2 min-h-[48px] hover:text-[var(--color-primary)] transition-colors">
            {favorite.product_name}
          </h3>
        </Link>

        {/* SKU */}
        <p className="text-[12px] leading-[16px] text-[var(--color-text-muted)] mb-3">
          Артикул: {favorite.product_sku || '—'}
        </p>

        {/* Цена */}
        <p className="text-[20px] leading-[28px] font-semibold text-[var(--color-text-primary)] mb-4">
          {favorite.product_price
            ? `${parseFloat(favorite.product_price).toLocaleString('ru-RU')} ₽`
            : 'Цена не указана'}
        </p>

        {/* Кнопка "В корзину" (AC: 5) */}
        {isAvailable ? (
          <Button
            variant="primary"
            size="medium"
            className="w-full"
            onClick={onAddToCart}
            loading={isAddingToCart}
            disabled={isAddingToCart}
          >
            В корзину
          </Button>
        ) : (
          <Button variant="secondary" size="medium" className="w-full" disabled>
            Сообщить о поступлении
          </Button>
        )}
      </div>
    </div>
  );
};

FavoriteProductCard.displayName = 'FavoriteProductCard';

export default FavoriteProductCard;
