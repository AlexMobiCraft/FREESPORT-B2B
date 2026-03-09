/**
 * SidebarFilters Component
 * Боковая панель фильтров для каталога товаров согласно Design System v2.0
 *
 * @see docs/stories/epic-12/12.5.story.md#AC1
 */

import React, { useMemo, useCallback } from 'react';
import { cn } from '@/utils/cn';
import { FilterGroup } from '../../ui/FilterGroup';
import { Checkbox } from '../../ui/Checkbox';
import { Toggle } from '../../ui/Toggle';
import { PriceRangeSlider } from '../../ui/PriceRangeSlider';
import { Chip } from '../../ui/Chip';
import { Button } from '../../ui/Button';

export interface Category {
  id: string;
  name: string;
  children?: Category[];
}

export interface Brand {
  id: string;
  name: string;
}

export interface Color {
  name: string;
  hex: string;
}

export interface FilterValues {
  categories: string[];
  brands: string[];
  priceRange: [number, number];
  sizes: string[];
  colors: string[];
  inStock?: boolean;
}

export interface SidebarFiltersProps {
  /** Список категорий */
  categories: Category[];
  /** Список брендов */
  brands: Brand[];
  /** Диапазон цен (min, max) */
  priceRange: { min: number; max: number };
  /** Доступные размеры */
  sizes: string[];
  /** Доступные цвета */
  colors: Color[];
  /** Текущие выбранные фильтры */
  selectedFilters: FilterValues;
  /** Callback при изменении фильтров */
  onFilterChange: (filters: FilterValues) => void;
  /** Callback при применении фильтров */
  onApply: () => void;
  /** Callback при сбросе фильтров */
  onReset: () => void;
  /** Дополнительные классы */
  className?: string;
}

/**
 * SidebarFilters - боковая панель с фильтрами товаров
 */
export const SidebarFilters = React.forwardRef<HTMLDivElement, SidebarFiltersProps>(
  (
    {
      categories,
      brands,
      priceRange,
      sizes,
      colors,
      selectedFilters,
      onFilterChange,
      onApply,
      onReset,
      className,
    },
    ref
  ) => {
    // Обработчики изменения фильтров
    const handleCategoryChange = useCallback(
      (categoryId: string, checked: boolean) => {
        const newCategories = checked
          ? [...selectedFilters.categories, categoryId]
          : selectedFilters.categories.filter(id => id !== categoryId);

        onFilterChange({ ...selectedFilters, categories: newCategories });
      },
      [onFilterChange, selectedFilters]
    );

    const handleBrandChange = (brandId: string, checked: boolean) => {
      const newBrands = checked
        ? [...selectedFilters.brands, brandId]
        : selectedFilters.brands.filter(id => id !== brandId);

      onFilterChange({ ...selectedFilters, brands: newBrands });
    };

    const handlePriceChange = (newRange: [number, number]) => {
      onFilterChange({ ...selectedFilters, priceRange: newRange });
    };

    const handleSizeToggle = (size: string) => {
      const isSelected = selectedFilters.sizes.includes(size);
      const newSizes = isSelected
        ? selectedFilters.sizes.filter(s => s !== size)
        : [...selectedFilters.sizes, size];

      onFilterChange({ ...selectedFilters, sizes: newSizes });
    };

    const handleColorToggle = (colorName: string) => {
      const isSelected = selectedFilters.colors.includes(colorName);
      const newColors = isSelected
        ? selectedFilters.colors.filter(c => c !== colorName)
        : [...selectedFilters.colors, colorName];

      onFilterChange({ ...selectedFilters, colors: newColors });
    };

    const handleInStockChange = (checked: boolean) => {
      onFilterChange({ ...selectedFilters, inStock: checked });
    };

    // Рендер категорий (включая вложенные) с мемоизацией для оптимизации больших списков
    const renderCategories = useMemo(() => {
      const render = (cats: Category[], level = 0): React.ReactNode[] => {
        return cats.map(category => (
          <div
            key={category.id}
            className={cn(
              level === 1 && 'pl-4', // 16px для уровня 1
              level === 2 && 'pl-8', // 32px для уровня 2
              level >= 3 && 'pl-12' // 48px для уровня 3+
            )}
          >
            <Checkbox
              checked={selectedFilters.categories.includes(category.id)}
              onChange={(event: React.ChangeEvent<HTMLInputElement>) =>
                handleCategoryChange(category.id, event.target.checked)
              }
              label={category.name}
            />
            {category.children && category.children.length > 0 && (
              <div className="mt-2">{render(category.children, level + 1)}</div>
            )}
          </div>
        ));
      };

      return render(categories, 0);
    }, [categories, selectedFilters.categories, handleCategoryChange]);

    return (
      <div
        ref={ref}
        className={cn(
          'w-[280px]', // Design System v2.0: 280px width
          'bg-white',
          'flex flex-col',
          className
        )}
      >
        {/* Фильтры */}
        <div className="flex-1 space-y-6 overflow-y-auto">
          {' '}
          {/* 24px spacing между секциями */}
          {/* Категории */}
          <FilterGroup title="Категории" defaultExpanded={false}>
            <div className="space-y-2">{renderCategories}</div>
          </FilterGroup>
          {/* Бренды */}
          <FilterGroup title="Бренды" defaultExpanded={true}>
            <div className="space-y-2">
              {brands.map(brand => (
                <Checkbox
                  key={brand.id}
                  checked={selectedFilters.brands.includes(brand.id)}
                  onChange={event => handleBrandChange(brand.id, event.target.checked)}
                  label={brand.name}
                />
              ))}
            </div>
          </FilterGroup>
          {/* Цена */}
          <FilterGroup title="Цена" defaultExpanded={true}>
            <PriceRangeSlider
              min={priceRange.min}
              max={priceRange.max}
              value={selectedFilters.priceRange}
              onChange={handlePriceChange}
            />
          </FilterGroup>
          {/* Размер */}
          {sizes.length > 0 && (
            <FilterGroup title="Размер" defaultExpanded={true}>
              <div className="flex flex-wrap gap-2">
                {sizes.map(size => (
                  <Chip
                    key={size}
                    selected={selectedFilters.sizes.includes(size)}
                    onClick={() => handleSizeToggle(size)}
                  >
                    {size}
                  </Chip>
                ))}
              </div>
            </FilterGroup>
          )}
          {/* Цвет */}
          {colors.length > 0 && (
            <FilterGroup title="Цвет" defaultExpanded={true}>
              <div className="flex flex-wrap gap-2">
                {colors.map(color => (
                  <button
                    key={color.name}
                    type="button"
                    onClick={() => handleColorToggle(color.name)}
                    className={cn(
                      'w-8 h-8 rounded-full',
                      'border-2 transition-all duration-[180ms]',
                      selectedFilters.colors.includes(color.name)
                        ? 'border-primary scale-110'
                        : 'border-neutral-300 hover:border-neutral-400'
                    )}
                    style={{ backgroundColor: color.hex }}
                    title={color.name}
                    aria-label={color.name}
                  />
                ))}
              </div>
            </FilterGroup>
          )}
          {/* Только в наличии */}
          <div className="pt-2">
            <Toggle
              checked={selectedFilters.inStock || false}
              onChange={(e: React.ChangeEvent<HTMLInputElement>) =>
                handleInStockChange(e.target.checked)
              }
              label="Только в наличии"
            />
          </div>
        </div>

        {/* Кнопки действий */}
        <div className="pt-6 space-y-3 border-t border-[#E3E8F2]">
          <Button variant="primary" size="medium" onClick={onApply} className="w-full">
            Применить
          </Button>

          <Button variant="tertiary" size="medium" onClick={onReset} className="w-full">
            Сбросить
          </Button>
        </div>
      </div>
    );
  }
);

SidebarFilters.displayName = 'SidebarFilters';
