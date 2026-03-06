/**
 * FavoritesList Component - Список избранных товаров
 * Story 16.3: Управление избранными товарами (AC: 4)
 *
 * Отображает:
 * - Grid карточек избранных товаров
 * - Пустое состояние
 */

'use client';

import React from 'react';
import { Heart } from 'lucide-react';
import Link from 'next/link';
import { cn } from '@/utils/cn';
import { FavoriteProductCard } from '../FavoriteProductCard';
import type { FavoriteWithAvailability } from '@/types/favorite';

export interface FavoritesListProps {
  /** Список избранных товаров */
  favorites: FavoriteWithAvailability[];
  /** Callback добавления в корзину */
  onAddToCart: (favorite: FavoriteWithAvailability) => void;
  /** Callback удаления из избранного */
  onRemoveFavorite: (favoriteId: number) => void;
  /** ID товара в процессе добавления в корзину */
  addingToCartId?: number | null;
  /** ID товара в процессе удаления */
  removingId?: number | null;
  /** Флаг загрузки */
  isLoading?: boolean;
}

/**
 * Компонент списка избранных товаров
 */
export const FavoritesList: React.FC<FavoritesListProps> = ({
  favorites,
  onAddToCart,
  onRemoveFavorite,
  addingToCartId = null,
  removingId = null,
  isLoading = false,
}) => {
  // Пустое состояние
  if (!isLoading && favorites.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-16 px-4">
        <div className="w-16 h-16 rounded-full bg-[var(--color-neutral-200)] flex items-center justify-center mb-4">
          <Heart className="w-8 h-8 text-[var(--color-text-muted)]" />
        </div>
        <h3 className="text-[20px] leading-[28px] font-semibold text-[var(--color-text-primary)] mb-2">
          Избранное пусто
        </h3>
        <p className="text-[16px] leading-[24px] text-[var(--color-text-muted)] text-center mb-6 max-w-md">
          Добавляйте понравившиеся товары в избранное, чтобы не потерять их
        </p>
        <Link
          href="/catalog"
          className={cn(
            'flex items-center gap-2 px-6 py-3',
            'bg-[var(--color-primary)] text-white',
            'rounded-md font-medium',
            'hover:bg-[var(--color-primary-hover)]',
            'transition-colors duration-150'
          )}
        >
          Перейти в каталог
        </Link>
      </div>
    );
  }

  // Скелетон загрузки
  if (isLoading) {
    return (
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6">
        {[1, 2, 3, 4].map(i => (
          <div
            key={i}
            className="bg-white rounded-[16px] overflow-hidden shadow-[0_8px_24px_rgba(15,23,42,0.08)] animate-pulse"
          >
            <div className="aspect-square bg-[var(--color-neutral-300)]" />
            <div className="p-4">
              <div className="h-5 bg-[var(--color-neutral-300)] rounded w-3/4 mb-2" />
              <div className="h-3 bg-[var(--color-neutral-300)] rounded w-1/2 mb-3" />
              <div className="h-6 bg-[var(--color-neutral-300)] rounded w-1/3 mb-4" />
              <div className="h-10 bg-[var(--color-neutral-300)] rounded w-full" />
            </div>
          </div>
        ))}
      </div>
    );
  }

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6">
      {favorites.map(favorite => (
        <FavoriteProductCard
          key={favorite.id}
          favorite={favorite}
          onAddToCart={() => onAddToCart(favorite)}
          onRemoveFavorite={() => onRemoveFavorite(favorite.id)}
          isAddingToCart={addingToCartId === favorite.id}
          isRemoving={removingId === favorite.id}
        />
      ))}
    </div>
  );
};

FavoritesList.displayName = 'FavoritesList';

export default FavoritesList;
