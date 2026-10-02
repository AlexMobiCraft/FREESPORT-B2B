/**
 * SortSelect Component
 * Select для сортировки товаров согласно Design System v2.0
 *
 * @see docs/stories/epic-12/12.5.story.md#AC7
 */

import React from 'react';
import { ElectricSelect, ElectricSelectOption } from '../Select/ElectricSelect';

export interface SortOption {
  value: string;
  label: string;
  direction: 'asc' | 'desc';
}

export interface SortSelectProps {
  /** Опции сортировки */
  options: SortOption[];
  /** Текущее значение */
  value: string;
  /** Callback при изменении */
  onChange: (value: string) => void;
  /** Режим B2C/B2B */
  mode?: 'b2c' | 'b2b';
  /** Дополнительные классы */
  className?: string;
}

/**
 * Опции сортировки товаров
 * Значения соответствуют Django ordering API format: field или -field
 * Доступные поля сортировки API: name, min_retail_price, created_at, total_stock
 */
export const SORT_OPTIONS: SortOption[] = [
  { value: 'price_asc', label: 'Цена: по возрастанию', direction: 'asc' },
  { value: 'price_desc', label: 'Цена: по убыванию', direction: 'desc' },
  { value: 'stock_desc', label: 'По наличию', direction: 'desc' },
  { value: 'brand_asc', label: 'По бренду (А-Я)', direction: 'asc' },
  { value: 'name_asc', label: 'По названию (А-Я)', direction: 'asc' },
  { value: 'new_first', label: 'Новинки', direction: 'desc' },
];

/**
 * SortSelect - компонент для сортировки товаров
 * Использует SelectDropdown как базу
 */
export const SortSelect = React.forwardRef<HTMLDivElement, SortSelectProps>(
  ({ options = SORT_OPTIONS, value, onChange, mode = 'b2c', className }, ref) => {
    // Преобразуем SortOption в ElectricSelectOption
    const selectOptions: ElectricSelectOption[] = options.map(opt => ({
      value: opt.value,
      label: opt.label,
    }));

    const labelText = mode === 'b2b' ? 'Сортировка (B2B)' : 'Сортировка';

    return (
      <ElectricSelect
        ref={ref}
        options={selectOptions}
        value={value}
        placeholder={labelText}
        onChange={onChange}
        className={className}
      />
    );
  }
);

SortSelect.displayName = 'SortSelect';
