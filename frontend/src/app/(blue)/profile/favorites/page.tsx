/**
 * Favorites Page - Страница избранных товаров
 * Story 16.3: Управление избранными товарами (AC: 4, 5, 6, 7)
 *
 * Функционал:
 * - Отображение списка избранных товаров
 * - Добавление товара в корзину (AC: 5)
 * - Удаление из избранного с optimistic UI (AC: 6)
 * - Отображение бейджа "Нет в наличии" (AC: 7)
 */

'use client';

import React, { useState, useEffect, useMemo } from 'react';
import { toast } from 'sonner';
import { FavoritesList } from '@/components/business/FavoritesList';
import Button from '@/components/ui/Button';
import { useFavoritesStore } from '@/stores/favoritesStore';
import { useCartStore } from '@/stores/cartStore';
import type { FavoriteWithAvailability } from '@/types/favorite';

/**
 * Страница избранных товаров
 */
export default function FavoritesPage() {
  // Zustand store для избранного (тот же store, что используется в каталоге)
  const storeFavorites = useFavoritesStore(state => state.favorites);
  const isLoading = useFavoritesStore(state => state.isLoading);
  const error = useFavoritesStore(state => state.error);
  const fetchFavorites = useFavoritesStore(state => state.fetchFavorites);
  const removeFavorite = useFavoritesStore(state => state.removeFavorite);

  // Action states
  const [addingToCartId, setAddingToCartId] = useState<number | null>(null);
  const [removingId, setRemovingId] = useState<number | null>(null);

  // Cart store
  const addToCart = useCartStore(state => state.addItem);

  // Загрузка избранных при монтировании
  useEffect(() => {
    fetchFavorites();
  }, [fetchFavorites]);

  // Преобразование Favorite в FavoriteWithAvailability (AC: 7)
  const favorites: FavoriteWithAvailability[] = useMemo(
    () =>
      storeFavorites.map(item => ({
        ...item,
        isAvailable: !!item.product_sku,
        variantId: undefined,
        stockQuantity: undefined,
      })),
    [storeFavorites]
  );

  /**
   * Добавить товар в корзину (AC: 5)
   */
  const handleAddToCart = async (favorite: FavoriteWithAvailability) => {
    if (!favorite.isAvailable) {
      toast.error('Товар недоступен');
      return;
    }

    setAddingToCartId(favorite.id);

    try {
      const result = await addToCart(favorite.product, 1);

      if (result.success) {
        toast.success('Товар добавлен в корзину');
      } else {
        toast.error(result.error || 'Не удалось добавить в корзину');
      }
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Ошибка добавления в корзину';
      toast.error(message);
    } finally {
      setAddingToCartId(null);
    }
  };

  /**
   * Удалить из избранного (AC: 6)
   */
  const handleRemoveFavorite = async (favoriteId: number) => {
    const favorite = favorites.find(f => f.id === favoriteId);
    if (!favorite) return;

    setRemovingId(favoriteId);

    try {
      await removeFavorite(favorite.product);
      toast.success('Удалено из избранного');
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Ошибка удаления из избранного';
      toast.error(message);
    } finally {
      setRemovingId(null);
    }
  };

  // Ошибка загрузки
  if (error && !isLoading && favorites.length === 0) {
    return (
      <div className="p-6">
        <h1 className="text-[24px] leading-[32px] font-semibold text-[var(--color-text-primary)] mb-6">
          Избранное
        </h1>
        <div className="bg-[var(--color-accent-danger-bg)] text-[var(--color-accent-danger)] p-4 rounded-lg">
          {error}
          <Button variant="tertiary" size="small" onClick={fetchFavorites} className="ml-4">
            Попробовать снова
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div className="p-6">
      {/* Заголовок страницы */}
      <h1 className="text-[24px] leading-[32px] font-semibold text-[var(--color-text-primary)] mb-6">
        Избранное
        {!isLoading && favorites.length > 0 && (
          <span className="text-[16px] font-normal text-[var(--color-text-muted)] ml-2">
            ({favorites.length})
          </span>
        )}
      </h1>

      {/* Список избранных */}
      <FavoritesList
        favorites={favorites}
        onAddToCart={handleAddToCart}
        onRemoveFavorite={handleRemoveFavorite}
        addingToCartId={addingToCartId}
        removingId={removingId}
        isLoading={isLoading}
      />
    </div>
  );
}
