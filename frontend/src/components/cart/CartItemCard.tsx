'use client';

/**
 * CartItemCard - компонент карточки товара в корзине
 *
 * Отображает информацию о товаре с возможностью изменения количества и удаления.
 * Поддерживает Optimistic Updates через cartStore.
 *
 * @see Story 26.2: Cart Item Card Component
 */

import Image from 'next/image';
import { Package, Trash2 } from 'lucide-react';
import { toast } from 'react-hot-toast';
import type { CartItem } from '@/types/cart';
import { formatPrice } from '@/utils/pricing';
import { QuantitySelector } from './QuantitySelector';

/**
 * Props для CartItemCard
 */
interface CartItemCardProps {
  /** Элемент корзины с данными о товаре */
  item: CartItem;
  /** Callback при изменении количества */
  onQuantityChange?: (
    id: number,
    quantity: number
  ) => Promise<{ success: boolean; error?: string }>;
  /** Callback при удалении товара */
  onRemove?: (id: number) => Promise<{ success: boolean; error?: string }>;
  /** Индикатор загрузки (обновление в процессе) */
  isUpdating?: boolean;
}

/**
 * Компонент карточки товара в корзине
 *
 * Функции:
 * - Отображение изображения товара (88x88px) с fallback placeholder
 * - Отображение названия, артикула (SKU), цвета, размера
 * - Отображение цены за единицу и суммы по позиции
 * - Кнопки +/- для изменения количества с debounce
 * - Кнопка удаления товара с Toast уведомлением
 * - Optimistic Updates при изменении quantity
 */
export function CartItemCard({
  item,
  onQuantityChange,
  onRemove,
  isUpdating = false,
}: CartItemCardProps) {
  /**
   * Обработчик изменения количества товара
   * Вызывает onQuantityChange с Optimistic Update
   */
  const handleQuantityChange = async (newQuantity: number) => {
    if (!onQuantityChange) return;

    const result = await onQuantityChange(item.id, newQuantity);

    if (!result.success) {
      toast.error('Не удалось обновить количество');
    }
  };

  /**
   * Обработчик удаления товара из корзины
   * Показывает Toast уведомление при успехе/ошибке
   */
  const handleRemove = async () => {
    if (!onRemove) return;

    const result = await onRemove(item.id);

    if (result.success) {
      toast.success('Товар удалён из корзины');
    } else {
      toast.error('Не удалось удалить товар');
    }
  };

  // Парсинг цен из string (Decimal from backend) в number
  const unitPrice = parseFloat(item.unit_price);
  const totalPrice = parseFloat(item.total_price);

  return (
    <div
      className="flex gap-4 p-6 bg-[var(--bg-panel)] rounded-[var(--radius-md)] shadow-[var(--shadow-default)]"
      data-testid="cart-item-card"
    >
      {/* Изображение товара */}
      <div className="flex-shrink-0">
        {item.product.image ? (
          <Image
            src={item.product.image}
            alt={item.product.name}
            width={88}
            height={88}
            className="rounded-[var(--radius)] object-cover"
            data-testid="cart-item-image"
            onError={e => {
              // Fallback при ошибке загрузки изображения
              const target = e.currentTarget as HTMLImageElement;
              target.style.display = 'none';
              const parent = target.parentElement;
              if (parent) {
                const placeholder = document.createElement('div');
                placeholder.className =
                  'w-[88px] h-[88px] rounded-[var(--radius)] bg-[var(--color-neutral-300)] flex items-center justify-center';
                placeholder.innerHTML =
                  '<svg xmlns="http://www.w3.org/2000/svg" width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="text-[var(--color-text-secondary)]"><path d="m7.5 4.27 9 5.15"/><path d="M21 8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16Z"/><path d="m3.3 7 8.7 5 8.7-5"/><path d="M12 22V12"/></svg>';
                parent.appendChild(placeholder);
              }
            }}
          />
        ) : (
          // Image placeholder при отсутствии изображения
          <div
            className="w-[88px] h-[88px] rounded-[var(--radius)] bg-[var(--color-neutral-300)] flex items-center justify-center"
            data-testid="cart-item-image-placeholder"
          >
            <Package size={32} className="text-[var(--color-text-secondary)]" />
          </div>
        )}
      </div>

      {/* Информация о товаре */}
      <div className="flex-1 flex flex-col justify-between">
        <div>
          {/* Название товара */}
          <h3
            className="text-body-l font-semibold text-[var(--color-text-primary)]"
            data-testid="cart-item-name"
          >
            {item.product.name}
          </h3>

          {/* SKU, цвет, размер */}
          <p className="text-body-s text-[var(--color-text-secondary)]" data-testid="cart-item-sku">
            Арт: {item.variant.sku}
            {item.variant.color_name && ` | Цвет: ${item.variant.color_name}`}
            {item.variant.size_value && ` | Размер: ${item.variant.size_value}`}
          </p>
        </div>

        {/* Quantity + Price Row */}
        <div className="flex items-center justify-between mt-4">
          <QuantitySelector
            value={item.quantity}
            min={1}
            max={99}
            onChange={handleQuantityChange}
            isLoading={isUpdating}
          />

          {/* Price Display */}
          <div className="text-right">
            <p
              className="text-body-s text-[var(--color-text-secondary)]"
              data-testid="cart-item-unit-price"
            >
              {formatPrice(unitPrice)} × {item.quantity}
            </p>
            <p
              className="text-title-m font-bold text-[var(--color-text-primary)]"
              data-testid="cart-item-total-price"
            >
              {formatPrice(totalPrice)}
            </p>
          </div>
        </div>
      </div>

      {/* Delete Button */}
      <button
        onClick={handleRemove}
        disabled={isUpdating}
        className="flex-shrink-0 p-2 text-[var(--color-text-secondary)] hover:text-[var(--color-accent-danger)] transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
        aria-label="Удалить товар"
        data-testid="remove-item-button"
      >
        <Trash2 size={20} />
      </button>
    </div>
  );
}
