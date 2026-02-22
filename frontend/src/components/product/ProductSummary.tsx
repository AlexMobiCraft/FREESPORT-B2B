/**
 * ProductSummary Component (Story 12.3, 13.5a, 13.5b)
 * Компонент-обёртка для ProductInfo и ProductOptions
 * Управляет состоянием выбранного варианта товара и добавлением в корзину
 *
 * @see docs/stories/epic-12/12.3.add-to-cart.md
 * @see docs/stories/epic-13/13.5a.productoptions-ui-msw-mock.md
 * @see docs/stories/epic-13/13.5b.productoptions-api-integration.md
 */

'use client';

import React, { useState, useCallback, useMemo, useEffect, useRef } from 'react';
import type { ProductDetail } from '@/types/api';
import type { UserRole } from '@/utils/pricing';
import { useCartStore } from '@/stores/cartStore';
import { useAuthStore } from '@/stores/authStore';
import { useFavoritesStore } from '@/stores/favoritesStore';
import { useToast } from '@/components/ui/Toast';
import { formatPrice } from '@/utils/pricing';
import ProductInfo from './ProductInfo';
import { ProductOptions, type SelectedOptions } from './ProductOptions';
import { QuantitySelector } from '@/components/cart/QuantitySelector';
import type { ProductVariant } from '@/types/api';
import { Heart } from 'lucide-react';
import { cn } from '@/utils/cn';

/**
 * Расширенный интерфейс товара с вариантами
 */
export interface ProductDetailWithVariants extends ProductDetail {
  variants?: ProductVariant[];
}

/**
 * Результат валидации опций
 */
export interface ValidationResult {
  valid: boolean;
  message?: string;
}

/**
 * Валидирует выбранные опции товара
 * @param selectedOptions - текущие выбранные опции
 * @param variants - доступные варианты товара
 * @returns результат валидации с сообщением об ошибке
 */
export function validateOptions(
  selectedOptions: SelectedOptions,
  variants: ProductVariant[]
): ValidationResult {
  // Извлечь уникальные опции
  const sizes = [...new Set(variants.map(v => v.size_value).filter(Boolean))];
  const colors = [...new Set(variants.map(v => v.color_name).filter(Boolean))];

  // Проверить обязательные опции
  if (sizes.length > 0 && !selectedOptions.size) {
    return {
      valid: false,
      message: 'Пожалуйста, выберите размер',
    };
  }

  if (colors.length > 0 && !selectedOptions.color) {
    return {
      valid: false,
      message: 'Пожалуйста, выберите цвет',
    };
  }

  return { valid: true };
}

/**
 * Props компонента ProductSummary
 */
interface ProductSummaryProps {
  /** Данные товара (с опциональными вариантами) */
  product: ProductDetailWithVariants;
  /** Роль пользователя для отображения цены */
  userRole?: UserRole;
  /** Callback при добавлении в корзину */
  onAddToCart?: (variantId?: number) => void;
  /** Callback при изменении выбранного варианта (для интеграции с ProductGallery) */
  onVariantChange?: (variant: ProductVariant | null) => void;
}

/**
 * ProductSummary - компонент сводки товара с выбором вариантов
 *
 * Объединяет ProductInfo и ProductOptions, управляя состоянием
 * выбранного варианта и обновляя отображаемую цену.
 */
export default function ProductSummary({
  product,
  userRole = 'guest',
  onAddToCart,
  onVariantChange,
}: ProductSummaryProps) {
  // Состояние выбранных опций
  const [selectedOptions, setSelectedOptions] = useState<SelectedOptions>({});
  // Состояние ошибки валидации
  const [validationError, setValidationError] = useState<string>('');
  // Состояние количества
  const [quantity, setQuantity] = useState<number>(1);

  // Hooks для работы с корзиной и уведомлениями
  const { addItem, isLoading } = useCartStore();
  const { success, error: toastError } = useToast();

  // Favorites logic
  const { isAuthenticated } = useAuthStore();
  const favorites = useFavoritesStore(state => state.favorites);
  const { toggleFavorite, fetchFavorites } = useFavoritesStore();

  const isFavorite = useMemo(
    () => favorites.some(f => f.product === product.id),
    [favorites, product.id]
  );

  // Fetch favorites on mount if authenticated
  useEffect(() => {
    if (isAuthenticated) {
      fetchFavorites();
    }
  }, [isAuthenticated, fetchFavorites]);

  const handleToggleFavorite = useCallback(async () => {
    if (!isAuthenticated) {
      toastError('Пожалуйста, авторизуйтесь для добавления в избранное');
      return;
    }
    try {
      await toggleFavorite(product.id);
    } catch {
      // handled in store
      toastError('Не удалось обновить избранное');
    }
  }, [isAuthenticated, toggleFavorite, product.id, toastError]);

  // Варианты товара (если есть) - мемоизируем для стабильности ссылки
  const variants = useMemo(() => product.variants || [], [product.variants]);

  // RRP видят только оптовики (1-3), тренеры и админы
  const canSeeRrp = useMemo(
    () =>
      ['wholesale_level1', 'wholesale_level2', 'wholesale_level3', 'trainer', 'admin'].includes(
        userRole
      ),
    [userRole]
  );

  // Ref для callback чтобы избежать лишних перерендеров
  const onVariantChangeRef = useRef(onVariantChange);
  onVariantChangeRef.current = onVariantChange;

  // Флаг инициализации для предотвращения повторного автовыбора
  const isInitializedRef = useRef(false);

  /**
   * Извлекает уникальные размеры и цвета из вариантов
   */
  const { sizes, colors } = useMemo(() => {
    const sizeSet = new Set<string>();
    const colorSet = new Set<string>();
    variants.forEach(v => {
      if (v.size_value) sizeSet.add(v.size_value);
      if (v.color_name) colorSet.add(v.color_name);
    });
    return {
      sizes: Array.from(sizeSet),
      colors: Array.from(colorSet),
    };
  }, [variants]);

  /**
   * Автоматически выбирает первый доступный вариант при загрузке
   */
  useEffect(() => {
    // Пропускаем если уже инициализировано или нет вариантов
    if (isInitializedRef.current || variants.length === 0) return;

    // Находим первый доступный вариант (в наличии)
    const firstAvailable = variants.find(v => v.is_in_stock) || variants[0];
    if (!firstAvailable) return;

    // Формируем начальные опции из первого варианта
    const initialOptions: SelectedOptions = {};

    if (sizes.length > 0 && firstAvailable.size_value) {
      initialOptions.size = firstAvailable.size_value;
    }

    if (colors.length > 0 && firstAvailable.color_name) {
      initialOptions.color = firstAvailable.color_name;
    }

    // Устанавливаем начальные опции только если они не пустые
    if (initialOptions.size || initialOptions.color) {
      isInitializedRef.current = true;
      setSelectedOptions(initialOptions);

      // Уведомляем родительский компонент о выбранном варианте (через ref)
      if (onVariantChangeRef.current) {
        onVariantChangeRef.current(firstAvailable);
      }
    }
  }, [variants, sizes.length, colors.length]);

  /**
   * Находит вариант по выбранным опциям
   */
  const selectedVariant = useMemo((): ProductVariant | null => {
    if (variants.length === 0) return null;

    // Если есть опции для выбора, но ничего не выбрано - возвращаем null
    // Если опций нет (простой товар с вариантом), пропускаем эту проверку
    if (
      (sizes.length > 0 || colors.length > 0) &&
      !selectedOptions.size &&
      !selectedOptions.color
    ) {
      return null;
    }

    // Ищем вариант, соответствующий выбранным опциям
    return (
      variants.find(v => {
        const sizeMatch = !selectedOptions.size || v.size_value === selectedOptions.size;
        const colorMatch = !selectedOptions.color || v.color_name === selectedOptions.color;
        return sizeMatch && colorMatch;
      }) || null
    );
  }, [variants, selectedOptions, sizes.length, colors.length]);

  /**
   * Обработчик изменения выбора опций
   * Уведомляет родительский компонент об изменении варианта
   */
  const handleSelectionChange = useCallback(
    (newOptions: SelectedOptions) => {
      setSelectedOptions(newOptions);
      setValidationError(''); // Сбрасываем ошибку при изменении выбора
      setQuantity(1); // Сбрасываем количество при смене варианта

      // Найти новый вариант и уведомить родителя
      if (onVariantChange && variants.length > 0) {
        const newVariant =
          variants.find(v => {
            const sizeMatch = !newOptions.size || v.size_value === newOptions.size;
            const colorMatch = !newOptions.color || v.color_name === newOptions.color;
            return sizeMatch && colorMatch;
          }) || null;
        onVariantChange(newVariant);
      }
    },
    [onVariantChange, variants]
  );

  /**
   * Обработчик добавления в корзину с валидацией
   */
  const handleAddToCart = useCallback(async () => {
    // Валидация перед добавлением в корзину
    if (variants.length > 0) {
      const validation = validateOptions(selectedOptions, variants);
      if (!validation.valid) {
        setValidationError(validation.message || 'Пожалуйста, выберите все опции товара');
        toastError(validation.message || 'Пожалуйста, выберите все опции товара');
        return;
      }

      if (!selectedVariant) {
        const msg = 'Пожалуйста, выберите все опции товара';
        setValidationError(msg);
        toastError(msg);
        return;
      }

      if (!selectedVariant.is_in_stock) {
        const msg = 'Выбранный вариант недоступен';
        setValidationError(msg);
        toastError(msg);
        return;
      }
    }

    setValidationError('');

    // Добавляем в корзину через cartStore
    const variantId = selectedVariant?.id;
    if (!variantId) {
      toastError('Не удалось определить вариант товара');
      return;
    }

    const result = await addItem(variantId, quantity);

    if (result.success) {
      success('Товар добавлен в корзину');
      // Сбрасываем количество после успешного добавления
      setQuantity(1);

      // Вызываем внешний callback если он есть
      if (onAddToCart) {
        onAddToCart(variantId);
      }
    } else {
      toastError(result.error || 'Ошибка при добавлении в корзину');
    }
  }, [
    addItem,
    quantity,
    selectedVariant,
    selectedOptions,
    variants,
    onAddToCart,
    success,
    toastError,
  ]);

  /**
   * Проверяет, можно ли добавить товар в корзину
   */
  const canAddToCart = useMemo(() => {
    // Если нет вариантов - проверяем базовый товар
    if (variants.length === 0) {
      return product.is_in_stock || product.can_be_ordered;
    }

    // Если есть варианты - нужно выбрать доступный вариант
    if (!selectedVariant) return false;

    return selectedVariant.is_in_stock;
  }, [variants, product, selectedVariant]);

  /**
   * Текст кнопки добавления в корзину
   */
  const addToCartButtonText = useMemo(() => {
    if (variants.length > 0 && !selectedVariant) {
      return 'Выберите вариант';
    }

    if (!canAddToCart) {
      return 'Нет в наличии';
    }

    return 'Добавить в корзину';
  }, [variants, selectedVariant, canAddToCart]);

  return (
    <div className="space-y-4" data-testid="product-summary">
      {/* Основная информация о товаре */}
      <ProductInfo product={product} userRole={userRole} selectedVariant={selectedVariant} />

      {/* Выбор вариантов (если есть) */}
      {variants.length > 0 && (
        <div className="pt-4 border-t border-neutral-200">
          <ProductOptions
            variants={variants}
            selectedOptions={selectedOptions}
            onSelectionChange={handleSelectionChange}
          />
        </div>
      )}

      {/* Информация о выбранном варианте */}
      {selectedVariant && (
        <div className="p-3 bg-neutral-50 rounded-lg" data-testid="selected-variant-info">
          <div className="flex items-center justify-between text-sm mb-1">
            <span className="text-neutral-600">Артикул:</span>
            <span className="font-medium text-neutral-900">{selectedVariant.sku}</span>
          </div>
          <div className="flex items-center justify-between text-sm mt-1">
            <span className="text-neutral-600">В наличии:</span>
            <span
              className={`font-medium ${selectedVariant.is_in_stock ? 'text-green-600' : 'text-red-600'}`}
            >
              {selectedVariant.is_in_stock
                ? selectedVariant.stock_range || 'В наличии'
                : 'Нет в наличии'}
            </span>
          </div>
        </div>
      )}

      {/* Сообщение об ошибке валидации */}
      {validationError && (
        <div
          className="p-3 bg-red-50 border border-red-200 rounded-lg text-red-600 text-sm"
          data-testid="validation-error"
          role="alert"
        >
          {validationError}
        </div>
      )}

      {/* Выбор количества */}
      {canAddToCart && (variants.length === 0 || selectedVariant) && (
        <div
          className="flex items-center justify-between py-3 border-t border-neutral-200"
          data-testid="quantity-selector-wrapper"
        >
          <span className="text-base font-medium text-neutral-700">Количество:</span>
          <QuantitySelector
            value={quantity}
            min={1}
            max={selectedVariant?.available_quantity || 99}
            onChange={setQuantity}
            isLoading={isLoading}
          />
        </div>
      )}

      {/* Кнопки действий */}
      <div className="flex gap-3">
        {/* Кнопка добавления в корзину */}
        <button
          type="button"
          onClick={handleAddToCart}
          disabled={!canAddToCart || (variants.length > 0 && !selectedVariant) || isLoading}
          className={cn(
            'flex-1 h-14 px-6 text-lg font-medium rounded-2xl transition-all duration-150',
            'focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-primary/60',
            'flex items-center justify-center gap-2',
            canAddToCart && (variants.length === 0 || selectedVariant) && !isLoading
              ? 'bg-primary text-white hover:bg-primary-hover active:bg-primary-active shadow-md'
              : 'bg-neutral-200 text-neutral-400 cursor-not-allowed'
          )}
          data-testid="add-to-cart-button"
        >
          {isLoading && (
            <svg
              className="animate-spin h-5 w-5"
              xmlns="http://www.w3.org/2000/svg"
              fill="none"
              viewBox="0 0 24 24"
            >
              <circle
                className="opacity-25"
                cx="12"
                cy="12"
                r="10"
                stroke="currentColor"
                strokeWidth="4"
              ></circle>
              <path
                className="opacity-75"
                fill="currentColor"
                d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
              ></path>
            </svg>
          )}
          {isLoading ? 'Добавление...' : addToCartButtonText}
        </button>

        {/* Кнопка избранного */}
        <button
          type="button"
          onClick={handleToggleFavorite}
          className={cn(
            'h-14 w-14 rounded-2xl border border-neutral-200 flex items-center justify-center transition-colors shrink-0',
            'hover:bg-neutral-50 active:bg-neutral-100',
            'focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-primary/60'
          )}
          title={isFavorite ? 'Удалить из избранного' : 'Добавить в избранное'}
          aria-label={isFavorite ? 'Удалить из избранного' : 'Добавить в избранное'}
        >
          <Heart
            className={cn(
              'w-6 h-6 transition-colors duration-200',
              isFavorite ? 'fill-accent-danger text-accent-danger' : 'text-neutral-400'
            )}
          />
        </button>
      </div>

      {/* Описание товара (перемещено вниз) */}
      {product.description && (
        <div className="pt-4 border-t border-neutral-200">
          <h3 className="text-lg font-semibold text-neutral-900 mb-2">Описание</h3>
          <p className="text-base text-neutral-700 leading-relaxed">{product.description}</p>
        </div>
      )}
    </div>
  );
}
