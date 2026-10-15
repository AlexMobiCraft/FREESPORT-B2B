/**
 * ProductOptions Component (Story 13.5a, 13.5b)
 * Компонент для выбора вариантов товара (размер, цвет)
 *
 * @see docs/stories/epic-13/13.5a.productoptions-ui-msw-mock.md
 * @see docs/stories/epic-13/13.5b.productoptions-api-integration.md
 */

'use client';

import React, { useCallback, useMemo } from 'react';
import { cn } from '@/utils/cn';
import type { ProductVariant } from '@/types/api';

/**
 * Интерфейс выбранных опций
 */
export interface SelectedOptions {
  size?: string;
  color?: string;
}

/**
 * Props компонента ProductOptions
 */
export interface ProductOptionsProps {
  /** Массив вариантов товара */
  variants: ProductVariant[];
  /** Текущие выбранные опции */
  selectedOptions: SelectedOptions;
  /** Callback при изменении выбора */
  onSelectionChange: (options: SelectedOptions) => void;
}

/**
 * Компонент Chip для выбора опции
 * Внутренний компонент с поддержкой accessibility
 */
interface OptionChipProps {
  /** Текст опции */
  label: string;
  /** Выбрана ли опция */
  selected: boolean;
  /** Доступна ли опция */
  disabled: boolean;
  /** Callback при клике */
  onClick: () => void;
  /** HEX цвет для цветового индикатора */
  colorHex?: string | null;
  /** Имя группы для aria */
  groupName: string;
}

/**
 * Внутренний Chip компонент для опций
 */
const OptionChip: React.FC<OptionChipProps> = ({
  label,
  selected,
  disabled,
  onClick,
  colorHex,
  groupName,
}) => {
  /**
   * Обработчик клика с проверкой доступности
   */
  const handleClick = useCallback(() => {
    if (!disabled) {
      onClick();
    }
  }, [disabled, onClick]);

  /**
   * Обработчик клавиатурной навигации
   */
  const handleKeyDown = useCallback(
    (event: React.KeyboardEvent) => {
      if ((event.key === 'Enter' || event.key === ' ') && !disabled) {
        event.preventDefault();
        onClick();
      }
    },
    [disabled, onClick]
  );

  return (
    <button
      type="button"
      role="radio"
      aria-checked={selected}
      aria-disabled={disabled}
      aria-label={`${groupName}: ${label}`}
      tabIndex={disabled ? -1 : 0}
      onClick={handleClick}
      onKeyDown={handleKeyDown}
      className={cn(
        // Базовые стили - Design System v2.0
        'inline-flex items-center gap-2',
        'px-4 py-2 rounded-2xl', // 16px radius
        'text-sm font-medium', // 14px typography
        'transition-colors duration-[180ms]',
        'min-w-[60px]',
        'border',
        // Focus state
        'focus:outline-none focus:ring-2 focus:ring-primary focus:ring-offset-2',

        // Состояния
        selected
          ? 'bg-primary text-white border-primary' // Selected: primary
          : 'bg-neutral-100 border-neutral-400 text-neutral-700', // Default

        // Disabled state
        disabled && 'opacity-50 cursor-not-allowed',

        // Hover state (только для доступных)
        !disabled && !selected && 'hover:border-primary hover:bg-neutral-50',

        // Active state
        !disabled && 'active:scale-95'
      )}
    >
      {/* Цветовой индикатор для цветов */}
      {colorHex && (
        <span
          className="w-4 h-4 rounded-full border-2 border-neutral-400 flex-shrink-0"
          style={{ backgroundColor: colorHex }}
          aria-hidden="true"
        />
      )}

      {/* Текст опции */}
      <span className="truncate">{label}</span>
    </button>
  );
};

/**
 * ProductOptions - компонент выбора вариантов товара
 *
 * Отображает селекторы размеров и цветов на основе доступных вариантов.
 * Поддерживает accessibility (ARIA, keyboard navigation).
 */
export const ProductOptions: React.FC<ProductOptionsProps> = ({
  variants,
  selectedOptions,
  onSelectionChange,
}) => {
  /**
   * Извлекает уникальные размеры из вариантов
   */
  const sizes = useMemo(() => {
    const sizeSet = new Set<string>();
    variants.forEach(v => {
      if (v.size_value) {
        sizeSet.add(v.size_value);
      }
    });
    return Array.from(sizeSet);
  }, [variants]);

  /**
   * Извлекает уникальные цвета из вариантов
   */
  const colors = useMemo(() => {
    const colorMap = new Map<string, string | null>();
    variants.forEach(v => {
      if (v.color_name && !colorMap.has(v.color_name)) {
        colorMap.set(v.color_name, v.color_hex || null);
      }
    });
    return Array.from(colorMap.entries()).map(([name, hex]) => ({ name, hex }));
  }, [variants]);

  /**
   * Проверяет доступность размера (есть ли в наличии)
   */
  const isSizeAvailable = useCallback(
    (size: string): boolean => {
      return variants.some(v => v.size_value === size && v.is_in_stock);
    },
    [variants]
  );

  /**
   * Проверяет доступность цвета (есть ли в наличии)
   */
  const isColorAvailable = useCallback(
    (color: string): boolean => {
      return variants.some(v => v.color_name === color && v.is_in_stock);
    },
    [variants]
  );

  /**
   * Обработчик выбора размера
   */
  const handleSizeClick = useCallback(
    (size: string) => {
      const newOptions: SelectedOptions = { ...selectedOptions, size };
      onSelectionChange(newOptions);
    },
    [selectedOptions, onSelectionChange]
  );

  /**
   * Обработчик выбора цвета
   */
  const handleColorClick = useCallback(
    (color: string) => {
      const newOptions: SelectedOptions = { ...selectedOptions, color };
      onSelectionChange(newOptions);
    },
    [selectedOptions, onSelectionChange]
  );

  // Не рендерим, если нет вариантов
  if (variants.length === 0) {
    return null;
  }

  return (
    <div className="space-y-6" data-testid="product-options">
      {/* Селектор размеров */}
      {sizes.length > 0 && (
        <div className="space-y-2" role="radiogroup" aria-label="Выбор размера">
          <h3 className="text-sm font-semibold font-montserrat text-neutral-900">Размер</h3>
          <div className="flex flex-wrap gap-2">
            {sizes.map(size => {
              const available = isSizeAvailable(size);
              const selected = selectedOptions.size === size;

              return (
                <OptionChip
                  key={size}
                  label={size}
                  selected={selected}
                  disabled={!available}
                  onClick={() => handleSizeClick(size)}
                  groupName="Размер"
                />
              );
            })}
          </div>
        </div>
      )}

      {/* Селектор цветов */}
      {colors.length > 0 && (
        <div className="space-y-2" role="radiogroup" aria-label="Выбор цвета">
          <h3 className="text-sm font-semibold font-montserrat text-neutral-900">Цвет</h3>
          <div className="flex flex-wrap gap-2">
            {colors.map(({ name, hex }) => {
              const available = isColorAvailable(name);
              const selected = selectedOptions.color === name;

              return (
                <OptionChip
                  key={name}
                  label={name}
                  selected={selected}
                  disabled={!available}
                  onClick={() => handleColorClick(name)}
                  colorHex={hex}
                  groupName="Цвет"
                />
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
};

export default ProductOptions;
