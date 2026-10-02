/**
 * SearchField Component
 * Компактное поле поиска с иконкой внутри
 *
 * @see frontend/docs/design-system.json#components.SearchField
 */

'use client';

import React, { useState, useRef, useEffect, useId } from 'react';
import { Search, X } from 'lucide-react';
import { cn } from '@/utils/cn';

export interface SearchFieldProps
  extends Omit<React.InputHTMLAttributes<HTMLInputElement>, 'type'> {
  /** Callback при изменении значения */
  onSearch?: (value: string) => void;
  /** Минимальная длина запроса */
  minLength?: number;
  /** Suggestions для автодополнения */
  suggestions?: string[];
  /** Товары для автодополнения */
  products?: Array<{ id: number; name: string; price: number }>;
  /** Debounce delay в миллисекундах */
  debounceMs?: number;
  /** Callback при клике по товару в dropdown */
  onProductClick?: (productId: number) => void;
  /** Показывать loading skeleton */
  isLoading?: boolean;
}

export const SearchField = React.forwardRef<HTMLInputElement, SearchFieldProps>(
  (
    {
      className,
      placeholder = 'Поиск',
      onSearch,
      minLength = 2,
      suggestions = [],
      products = [],
      debounceMs = 300,
      onChange,
      onProductClick,
      isLoading = false,
      ...props
    },
    ref
  ) => {
    const [localValue, setLocalValue] = useState('');
    const [showWarning, setShowWarning] = useState(false);
    const [isOpen, setIsOpen] = useState(false);
    const [debouncedValue, setDebouncedValue] = useState('');
    const [activeIndex, setActiveIndex] = useState(-1);
    const containerRef = useRef<HTMLDivElement>(null);
    const timeoutRef = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);
    const listboxId = useId();

    // Общий список элементов для keyboard navigation
    const allItems = [
      ...suggestions.map((s, i) => ({ type: 'suggestion' as const, value: s, index: i })),
      ...products.map((p, i) => ({
        type: 'product' as const,
        value: p,
        index: suggestions.length + i,
      })),
    ];
    const totalItems = allItems.length;

    // Debounce effect
    useEffect(() => {
      if (timeoutRef.current) {
        clearTimeout(timeoutRef.current);
      }

      timeoutRef.current = setTimeout(() => {
        setDebouncedValue(localValue);
        if (onSearch && localValue.length >= minLength) {
          onSearch(localValue);
        }
      }, debounceMs);

      return () => {
        if (timeoutRef.current) {
          clearTimeout(timeoutRef.current);
        }
      };
    }, [localValue, debounceMs, minLength, onSearch]);

    // Close dropdown on click outside
    useEffect(() => {
      const handleClickOutside = (event: MouseEvent) => {
        if (containerRef.current && !containerRef.current.contains(event.target as Node)) {
          setIsOpen(false);
        }
      };

      if (isOpen) {
        document.addEventListener('mousedown', handleClickOutside);
      }

      return () => {
        document.removeEventListener('mousedown', handleClickOutside);
      };
    }, [isOpen]);

    const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
      const value = e.target.value;
      setLocalValue(value);

      // Показываем dropdown если есть значение
      setIsOpen(value.length > 0);

      // Edge Case: Проверка минимальной длины
      if (value.length > 0 && value.length < minLength) {
        setShowWarning(true);
      } else {
        setShowWarning(false);
      }

      onChange?.(e);
    };

    const handleClear = () => {
      setLocalValue('');
      setDebouncedValue('');
      setIsOpen(false);
      setShowWarning(false);
      if (onSearch) {
        onSearch('');
      }
    };

    const hasResults =
      (suggestions.length > 0 || products.length > 0) && debouncedValue.length >= minLength;

    // Reset activeIndex when dropdown closes or items change
    useEffect(() => {
      if (!isOpen) {
        setActiveIndex(-1);
      }
    }, [isOpen]);

    useEffect(() => {
      setActiveIndex(-1);
    }, [suggestions.length, products.length]);

    /**
     * Keyboard navigation handler for Arrow Up/Down, Enter, Escape
     */
    const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
      if (!isOpen || !hasResults) {
        // Если dropdown закрыт, передаём событие дальше
        props.onKeyDown?.(e);
        return;
      }

      switch (e.key) {
        case 'ArrowDown':
          e.preventDefault();
          setActiveIndex(prev => (prev + 1) % totalItems);
          break;
        case 'ArrowUp':
          e.preventDefault();
          setActiveIndex(prev => (prev <= 0 ? totalItems - 1 : prev - 1));
          break;
        case 'Enter':
          e.preventDefault();
          if (activeIndex >= 0 && activeIndex < totalItems) {
            const item = allItems[activeIndex];
            if (item.type === 'suggestion') {
              setLocalValue(item.value as string);
              setIsOpen(false);
              if (onSearch) {
                onSearch(item.value as string);
              }
            } else {
              const product = item.value as { id: number; name: string; price: number };
              onProductClick?.(product.id);
              setIsOpen(false);
            }
          } else {
            // Если ничего не выбрано, передаём событие дальше
            props.onKeyDown?.(e);
          }
          break;
        case 'Escape':
          e.preventDefault();
          setIsOpen(false);
          setActiveIndex(-1);
          break;
        default:
          props.onKeyDown?.(e);
      }
    };

    return (
      <div ref={containerRef} className="w-full relative">
        <div className="relative">
          {/* Search Icon */}
          <div className="absolute left-3 top-1/2 -translate-y-1/2 text-neutral-600">
            <Search className="w-5 h-5" aria-hidden="true" />
          </div>

          {/* Input */}
          <input
            ref={ref}
            type="text"
            role="combobox"
            aria-expanded={isOpen && hasResults}
            aria-controls={isOpen && hasResults ? listboxId : undefined}
            aria-autocomplete="list"
            className={cn(
              // Базовые стили - Design System v2.0
              'w-full h-10 pl-10 pr-10 rounded-sm', // 40px height, 6px radius
              'text-body-m text-text-primary',
              'bg-white',
              'border border-[#E3E8F2]', // Design System v2.0 border
              'transition-colors duration-[180ms]',
              'placeholder:text-[#7A7A7A]',
              'focus:outline-none focus:border-primary focus:border-[1.5px]', // Design System v2.0 focus

              // Warning state
              showWarning && 'border-accent-warning focus:border-accent-warning',

              className
            )}
            placeholder={placeholder}
            value={localValue}
            onChange={handleChange}
            aria-label="Поиск"
            aria-activedescendant={
              activeIndex >= 0 ? `${listboxId}-option-${activeIndex}` : undefined
            }
            {...props}
            onKeyDown={handleKeyDown}
          />

          {/* Clear Button - Design System v2.0 */}
          {localValue.length > 0 && (
            <button
              type="button"
              onClick={handleClear}
              className={cn(
                'absolute right-3 top-1/2 -translate-y-1/2',
                'w-5 h-5 rounded-full',
                'flex items-center justify-center',
                'text-[#7A7A7A]',
                'hover:bg-[#F5F7FA]',
                'transition-colors duration-[120ms]',
                'focus:outline-none focus:ring-2 focus:ring-primary'
              )}
              aria-label="Очистить поиск"
            >
              <X className="w-4 h-4" />
            </button>
          )}
        </div>

        {/* Loading Skeleton - Design System v2.0 */}
        {isOpen && isLoading && (
          <div
            className={cn(
              'absolute top-full left-0 right-0 mt-1 z-50',
              'bg-white rounded-md',
              'border border-[#E3E8F2]',
              'shadow-lg',
              'p-4'
            )}
            role="status"
            aria-label="Загрузка результатов"
          >
            <div className="space-y-3 animate-pulse">
              <div className="h-4 bg-[#E3E8F2] rounded w-3/4"></div>
              <div className="h-4 bg-[#E3E8F2] rounded w-1/2"></div>
              <div className="h-4 bg-[#E3E8F2] rounded w-2/3"></div>
            </div>
          </div>
        )}

        {/* Autocomplete Dropdown - Design System v2.0 */}
        {isOpen && hasResults && !isLoading && (
          <div
            role="listbox"
            id={listboxId}
            className={cn(
              // Позиционирование
              'absolute top-full left-0 right-0 mt-1 z-50',

              // Стили - Design System v2.0
              'bg-white rounded-md',
              'border border-[#E3E8F2]',
              'shadow-lg',

              // Скролл
              'max-h-80 overflow-y-auto',

              // Анимация
              'animate-in fade-in-0 zoom-in-95 duration-100'
            )}
          >
            {/* Suggestions Section */}
            {suggestions.length > 0 && (
              <div className="py-2">
                <div className="px-4 py-1 text-caption text-text-muted font-medium">
                  Популярные запросы
                </div>
                {suggestions.map((suggestion, index) => (
                  <button
                    key={index}
                    id={`${listboxId}-option-${index}`}
                    type="button"
                    role="option"
                    aria-selected={activeIndex === index}
                    onClick={() => {
                      setLocalValue(suggestion);
                      setIsOpen(false);
                      if (onSearch) {
                        onSearch(suggestion);
                      }
                    }}
                    className={cn(
                      'w-full px-4 py-2 text-left',
                      'flex items-center gap-2',
                      'text-body-m text-text-primary',
                      'hover:bg-[#F5F7FA]',
                      'transition-colors duration-[120ms]',
                      activeIndex === index && 'bg-[#F5F7FA]'
                    )}
                  >
                    <Search className="w-4 h-4 text-[#7A7A7A]" />
                    {suggestion}
                  </button>
                ))}
              </div>
            )}

            {/* Products Section */}
            {products.length > 0 && (
              <div className="py-2 border-t border-[#E3E8F2]">
                <div className="px-4 py-1 text-caption text-text-muted font-medium">Товары</div>
                {products.map((product, index) => {
                  const itemIndex = suggestions.length + index;
                  return (
                    <button
                      key={product.id}
                      id={`${listboxId}-option-${itemIndex}`}
                      type="button"
                      role="option"
                      aria-selected={activeIndex === itemIndex}
                      onClick={() => {
                        onProductClick?.(product.id);
                        setIsOpen(false);
                      }}
                      className={cn(
                        'w-full px-4 py-2 text-left',
                        'flex items-center justify-between gap-2',
                        'text-body-m',
                        'hover:bg-[#F5F7FA]',
                        'transition-colors duration-[120ms]',
                        activeIndex === itemIndex && 'bg-[#F5F7FA]'
                      )}
                    >
                      <span className="truncate text-text-primary">{product.name}</span>
                      <span className="text-text-secondary font-medium flex-shrink-0">
                        {product.price.toLocaleString('ru-RU')} ₽
                      </span>
                    </button>
                  );
                })}
              </div>
            )}
          </div>
        )}

        {/* Edge Case: Предупреждение о минимальной длине */}
        {showWarning && (
          <p className="mt-1 text-caption text-accent-warning">
            Введите минимум {minLength} символа
          </p>
        )}
      </div>
    );
  }
);

SearchField.displayName = 'SearchField';
