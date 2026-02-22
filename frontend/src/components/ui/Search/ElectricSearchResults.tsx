/**
 * Electric Orange Search Results Component
 *
 * Автокомплит поиска в стиле Electric Orange
 * Features:
 * - Dropdown под поисковой строкой
 * - Skewed chevrons для категорий
 * - Product thumbnails
 * - Keyboard navigation
 *
 * @see docs/4-ux-design/00-design-system-migration/02-component-specs.md
 */

'use client';

import React, { useState, useRef, useEffect } from 'react';
import Image from 'next/image';
import { Search, ChevronRight, X } from 'lucide-react';
import { cn } from '@/utils/cn';

// ============================================
// Types
// ============================================

export interface SearchResultItem {
  id: string;
  type: 'product' | 'category' | 'brand';
  title: string;
  subtitle?: string;
  image?: string;
  href?: string;
}

export interface ElectricSearchResultsProps {
  /** Search results */
  results: SearchResultItem[];
  /** Search query */
  query: string;
  /** Query change callback */
  onQueryChange: (query: string) => void;
  /** Item select callback */
  onSelect: (item: SearchResultItem) => void;
  /** Search submit callback */
  onSubmit?: (query: string) => void;
  /** Loading state */
  isLoading?: boolean;
  /** Placeholder text */
  placeholder?: string;
  /** Additional class names */
  className?: string;
}

// ============================================
// Component
// ============================================

export function ElectricSearchResults({
  results,
  query,
  onQueryChange,
  onSelect,
  onSubmit,
  isLoading = false,
  placeholder = 'Поиск товаров...',
  className,
}: ElectricSearchResultsProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [highlightedIndex, setHighlightedIndex] = useState(-1);
  const containerRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  // Close on outside click
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    };

    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  // Reset highlight when results change
  useEffect(() => {
    setHighlightedIndex(-1);
  }, [results]);

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const newQuery = e.target.value;
    onQueryChange(newQuery);
    setIsOpen(newQuery.length > 0);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (!isOpen) return;

    switch (e.key) {
      case 'ArrowDown':
        e.preventDefault();
        setHighlightedIndex(prev => (prev < results.length - 1 ? prev + 1 : 0));
        break;
      case 'ArrowUp':
        e.preventDefault();
        setHighlightedIndex(prev => (prev > 0 ? prev - 1 : results.length - 1));
        break;
      case 'Enter':
        e.preventDefault();
        if (highlightedIndex >= 0 && results[highlightedIndex]) {
          onSelect(results[highlightedIndex]);
          setIsOpen(false);
        } else if (onSubmit) {
          onSubmit(query);
          setIsOpen(false);
        }
        break;
      case 'Escape':
        setIsOpen(false);
        break;
    }
  };

  const handleClear = () => {
    onQueryChange('');
    setIsOpen(false);
    inputRef.current?.focus();
  };

  return (
    <div ref={containerRef} className={cn('relative', className)}>
      {/* Search Input */}
      <div className="relative">
        <input
          ref={inputRef}
          type="text"
          value={query}
          onChange={handleInputChange}
          onKeyDown={handleKeyDown}
          onFocus={() => query.length > 0 && setIsOpen(true)}
          placeholder={placeholder}
          className={cn(
            'w-full h-11 pl-10 pr-10',
            'bg-transparent border border-[var(--border-default)]',
            'text-[var(--foreground)] placeholder-[var(--color-text-muted)]',
            'font-inter text-sm',
            'transition-colors duration-200',
            'focus:border-[var(--color-primary)] focus:outline-none',
            isOpen && 'border-[var(--color-primary)]'
          )}
        />

        {/* Search Icon */}
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[var(--color-text-muted)]" />

        {/* Clear Button */}
        {query && (
          <button
            onClick={handleClear}
            className="absolute right-3 top-1/2 -translate-y-1/2 text-[var(--color-text-muted)] hover:text-[var(--foreground)] transition-colors"
          >
            <X className="w-4 h-4" />
          </button>
        )}
      </div>

      {/* Results Dropdown */}
      {isOpen && query.length > 0 && (
        <div
          className={cn(
            'absolute top-full left-0 right-0 z-50 mt-1',
            'bg-[var(--bg-card)] border border-[var(--border-default)]',
            'max-h-80 overflow-y-auto',
            'animate-fadeIn'
          )}
        >
          {isLoading ? (
            <div className="p-4 text-center text-[var(--color-text-muted)]">Поиск...</div>
          ) : results.length === 0 ? (
            <div className="p-4 text-center text-[var(--color-text-muted)]">Ничего не найдено</div>
          ) : (
            <>
              {results.map((item, index) => (
                <button
                  key={item.id}
                  onClick={() => {
                    onSelect(item);
                    setIsOpen(false);
                  }}
                  className={cn(
                    'w-full flex items-center gap-3 p-3',
                    'text-left',
                    'transition-all duration-200',
                    'hover:bg-[var(--bg-card-hover)]',
                    highlightedIndex === index &&
                      'bg-[var(--bg-card-hover)] border-l-2 border-l-[var(--color-primary)]'
                  )}
                >
                  {/* Image/Icon */}
                  {item.image ? (
                    <div className="w-10 h-10 bg-[var(--bg-card-hover)] flex-shrink-0 overflow-hidden relative">
                      <Image src={item.image} alt={item.title} fill className="object-cover" />
                    </div>
                  ) : (
                    <div
                      className={cn(
                        'w-10 h-10 flex-shrink-0',
                        'flex items-center justify-center',
                        'border border-[var(--border-default)]',
                        'transform -skew-x-12'
                      )}
                    >
                      <ChevronRight className="w-4 h-4 text-[var(--color-primary)] transform skew-x-12" />
                    </div>
                  )}

                  {/* Content */}
                  <div className="flex-1 min-w-0">
                    <p className="text-sm text-[var(--foreground)] truncate">{item.title}</p>
                    {item.subtitle && (
                      <p className="text-xs text-[var(--color-text-muted)] truncate">
                        {item.subtitle}
                      </p>
                    )}
                  </div>

                  {/* Type Badge */}
                  <span
                    className={cn(
                      'px-2 py-0.5 text-xs uppercase',
                      'transform -skew-x-12',
                      item.type === 'product' &&
                        'bg-[var(--color-primary-subtle)] text-[var(--color-primary)]',
                      item.type === 'category' &&
                        'bg-[var(--bg-card-hover)] text-[var(--color-text-secondary)]',
                      item.type === 'brand' &&
                        'bg-[var(--bg-card-hover)] text-[var(--color-text-secondary)]'
                    )}
                  >
                    <span className="transform skew-x-12 inline-block">
                      {item.type === 'product'
                        ? 'Товар'
                        : item.type === 'category'
                          ? 'Категория'
                          : 'Бренд'}
                    </span>
                  </span>
                </button>
              ))}
            </>
          )}
        </div>
      )}
    </div>
  );
}

ElectricSearchResults.displayName = 'ElectricSearchResults';

export default ElectricSearchResults;
