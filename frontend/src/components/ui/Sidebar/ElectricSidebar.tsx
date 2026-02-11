/**
 * Electric Orange Sidebar Widget Component
 *
 * Sidebar panel with filters for catalog page
 * Features:
 * - Skewed headers (-12deg)
 * - Skewed checkboxes
 * - Price range slider with skew
 * - Dark theme styling
 *
 * @see docs/4-ux-design/00-design-system-migration/02-component-specs.md#sidebar
 */

'use client';

import React, { useState } from 'react';
import { cn } from '@/utils/cn';
import { PriceRangeSlider } from '@/components/ui/PriceRangeSlider/PriceRangeSlider';

// ============================================
// Types
// ============================================

export interface FilterOption {
  id: string;
  label: string;
  count?: number;
}

export interface FilterGroup {
  id: string;
  title: string;
  options: FilterOption[];
  type: 'checkbox' | 'price' | 'link-list';
}

export interface PriceRange {
  min: number;
  max: number;
}

export interface ElectricSidebarProps {
  /** Filter groups to display */
  filterGroups: FilterGroup[];
  /** Selected filter IDs */
  selectedFilters?: Record<string, string[]>;
  /** Price range */
  priceRange?: PriceRange;
  /** Current price values */
  currentPrice?: PriceRange;
  /** Callback when filters change */
  onFilterChange?: (groupId: string, optionId: string, checked: boolean) => void;
  /** Callback when price changes */
  onPriceChange?: (range: PriceRange) => void;
  /** Callback when apply button clicked */
  onApply?: () => void;
  /** Additional class names */
  className?: string;
}

// ============================================
// Sidebar Component
// ============================================

export function ElectricSidebar({
  filterGroups,
  selectedFilters = {},
  priceRange = { min: 1000, max: 50000 },
  currentPrice,
  onFilterChange,
  onPriceChange,
  onApply,
  className,
}: ElectricSidebarProps) {
  const [localPrice, setLocalPrice] = useState<PriceRange>(
    currentPrice || { min: priceRange.min, max: priceRange.max }
  );

  // Local state for checkboxes when no external onFilterChange is provided
  const [localSelectedFilters, setLocalSelectedFilters] =
    useState<Record<string, string[]>>(selectedFilters);

  const handleCheckboxChange = (groupId: string, optionId: string, checked: boolean) => {
    if (onFilterChange) {
      // Use external handler if provided
      onFilterChange(groupId, optionId, checked);
    } else {
      // Use local state
      setLocalSelectedFilters(prev => {
        const currentGroup = prev[groupId] || [];
        if (checked) {
          return { ...prev, [groupId]: [...currentGroup, optionId] };
        } else {
          return { ...prev, [groupId]: currentGroup.filter(id => id !== optionId) };
        }
      });
    }
  };

  const isChecked = (groupId: string, optionId: string): boolean => {
    const filters = onFilterChange ? selectedFilters : localSelectedFilters;
    return filters[groupId]?.includes(optionId) || false;
  };

  return (
    <aside
      className={cn(
        'bg-[var(--bg-card)] p-6 border border-[var(--border-default)]',
        'w-full h-fit',
        className
      )}
    >
      {filterGroups.map(group => (
        <div key={group.id} className="mb-8 last:mb-0">
          {/* Filter Title - Skewed */}
          <h3
            className="text-xl mb-5 pb-3 border-b border-[var(--border-default)] w-full block uppercase tracking-wide"
            style={{
              fontFamily: "'Roboto Condensed', sans-serif",
              fontWeight: 900,
              transform: 'skewX(-12deg)',
              transformOrigin: 'left',
            }}
          >
            <span style={{ transform: 'skewX(12deg)', display: 'inline-block' }}>
              {group.title}
            </span>
          </h3>

          {group.type === 'checkbox' && (
            <div className="space-y-3">
              {group.options.map(option => (
                <CheckboxRow
                  key={option.id}
                  option={option}
                  checked={isChecked(group.id, option.id)}
                  onChange={checked => handleCheckboxChange(group.id, option.id, checked)}
                />
              ))}
            </div>
          )}

          {group.type === 'link-list' && (
            <div className="space-y-1">
              {group.options.map(option => (
                <CategoryLink
                  key={option.id}
                  option={option}
                  isActive={
                    selectedFilters && selectedFilters[group.id]
                      ? selectedFilters[group.id].includes(option.id)
                      : false
                  }
                  onClick={
                    onFilterChange ? () => onFilterChange(group.id, option.id, true) : undefined
                  }
                />
              ))}
            </div>
          )}

          {group.type === 'link-list' && (
            <div className="space-y-1">
              {group.options.map(option => (
                <CategoryLink
                  key={option.id}
                  option={option}
                  isActive={
                    selectedFilters && selectedFilters[group.id]
                      ? selectedFilters[group.id].includes(option.id)
                      : false
                  }
                  onClick={
                    onFilterChange ? () => onFilterChange(group.id, option.id, true) : undefined
                  }
                />
              ))}
            </div>
          )}

          {group.type === 'price' && (
            <div>
              {/* Price Range Slider (Electric Orange) */}
              <PriceRangeSlider
                min={priceRange.min}
                max={priceRange.max}
                value={[localPrice.min, localPrice.max]}
                onChange={([newMin, newMax]) => {
                  const newRange = { min: newMin, max: newMax };
                  setLocalPrice(newRange);
                  onPriceChange?.(newRange);
                }}
              />
            </div>
          )}
        </div>
      ))}

      {/* Apply Button */}
      {onApply && (
        <button
          onClick={onApply}
          className="w-full h-12 bg-[var(--color-primary)] text-black font-bold uppercase tracking-wide transition-all hover:bg-white hover:text-[var(--color-primary)]"
          style={{
            fontFamily: "'Roboto Condensed', sans-serif",
            transform: 'skewX(-12deg)',
          }}
        >
          <span style={{ transform: 'skewX(12deg)', display: 'inline-block' }}>Применить</span>
        </button>
      )}
    </aside>
  );
}

// ============================================
// Checkbox Row Component
// ============================================

interface CheckboxRowProps {
  option: FilterOption;
  checked: boolean;
  onChange: (checked: boolean) => void;
}

function CheckboxRow({ option, checked, onChange }: CheckboxRowProps) {
  return (
    <label className="flex items-center cursor-pointer select-none group">
      <input
        type="checkbox"
        checked={checked}
        onChange={e => onChange(e.target.checked)}
        className="hidden"
      />

      {/* Skewed Checkbox */}
      <span
        className={cn(
          'w-5 h-5 border-2 mr-4 flex items-center justify-center transition-all',
          checked
            ? 'bg-[var(--color-primary)] border-[var(--color-primary)]'
            : 'border-[var(--border-default)] group-hover:border-[var(--color-primary)]'
        )}
        style={{ transform: 'skewX(-12deg)' }}
      >
        {checked && (
          <span className="text-black text-xs font-bold" style={{ transform: 'skewX(12deg)' }}>
            ✓
          </span>
        )}
      </span>

      {/* Label */}
      <span className="text-[var(--color-text-secondary)] text-sm transition-colors group-hover:text-[var(--color-text-primary)]">
        {option.label}
        {option.count !== undefined && (
          <span className="text-[var(--color-text-muted)] ml-2">({option.count})</span>
        )}
      </span>
    </label>
  );
}

// ============================================
// Exports
// ============================================

// ============================================
// Category Link Component
// ============================================

interface CategoryLinkProps {
  option: FilterOption;
  isActive: boolean;
  onClick?: () => void;
}

function CategoryLink({ option, isActive, onClick }: CategoryLinkProps) {
  return (
    <button
      onClick={onClick}
      className={cn(
        'w-full text-left py-1.5 px-2 text-sm transition-colors duration-200 block',
        'hover:text-[var(--color-primary)]',
        isActive
          ? 'text-[var(--color-primary)] font-medium pl-3 border-l-2 border-[var(--color-primary)]'
          : 'text-[var(--color-text-secondary)] border-l-2 border-transparent hover:border-[var(--color-text-muted)]'
      )}
    >
      {option.label}
      {option.count !== undefined && (
        <span className="text-[var(--color-text-muted)] text-xs ml-2">({option.count})</span>
      )}
    </button>
  );
}

export default ElectricSidebar;
