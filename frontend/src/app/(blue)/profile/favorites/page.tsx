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

import React, { useState, useEffect, useCallback } from 'react';
import { toast } from 'sonner';
import { FavoritesList } from '@/components/business/FavoritesList';
import Button from '@/components/ui/Button';
import { favoriteService } from '@/services/favoriteService';
import { useCartStore } from '@/stores/cartStore';
import type { Favorite, FavoriteWithAvailability } from '@/types/favorite';

/**
 * Страница избранных товаров
 */
export default function FavoritesPage() {
  // State
  const [favorites, setFavorites] = useState<FavoriteWithAvailability[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Action states
  const [addingToCartId, setAddingToCartId] = useState<number | null>(null);
  const [removingId, setRemovingId] = useState<number | null>(null);

  // Cart store
  const addToCart = useCartStore(state => state.addItem);

  /**
   * Преобразование Favorite в FavoriteWithAvailability
   * ВАЖНО: Проверка доступности на уровне варианта (AC: 7)
   * В текущей реализации используем product_sku для определения доступности
   * TODO: Запросить данные варианта через API для точной проверки stock_quantity
   */
  const transformFavorites = useCallback((items: Favorite[]): FavoriteWithAvailability[] => {
    return items.map(item => ({
      ...item,
      // По умолчанию считаем доступным, если есть product_sku
      // В будущем здесь будет запрос к API вариантов
      isAvailable: !!item.product_sku,
      variantId: undefined, // Будет заполнено при получении данных варианта
      stockQuantity: undefined,
    }));
  }, []);

  /**
   * Загрузка избранных товаров при монтировании
   */
  const fetchFavorites = useCallback(async () => {
    try {
      setIsLoading(true);
      setError(null);
      const data = await favoriteService.getFavorites();
      setFavorites(transformFavorites(data));
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Ошибка загрузки избранного';
      setError(message);
      toast.error(message);
    } finally {
      setIsLoading(false);
    }
  }, [transformFavorites]);

  useEffect(() => {
    fetchFavorites();
  }, [fetchFavorites]);

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
      // Используем product ID для добавления в корзину
      // TODO: Использовать variantId когда он будет доступен
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
    // Сохраняем для отката
    const removedFavorite = favorites.find(f => f.id === favoriteId);

    setRemovingId(favoriteId);

    // Optimistic UI: мгновенно удаляем из списка
    setFavorites(prev => prev.filter(f => f.id !== favoriteId));

    try {
      await favoriteService.removeFavorite(favoriteId);
      toast.success('Удалено из избранного');
    } catch (err) {
      // Откат при ошибке
      if (removedFavorite) {
        setFavorites(prev => [...prev, removedFavorite]);
      }
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
