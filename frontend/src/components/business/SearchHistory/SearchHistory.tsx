/**
 * SearchHistory Component
 * Displays search history with ability to select, remove items and clear all
 *
 * @see docs/stories/epic-18/18.3.search-history.md#Task2
 */

'use client';

import React, { useState } from 'react';
import { Clock, X } from 'lucide-react';
import { cn } from '@/utils/cn';

/**
 * Props для компонента SearchHistory
 */
export interface SearchHistoryProps {
  /** Массив последних поисковых запросов */
  history: string[];
  /** Callback при выборе элемента истории */
  onSelect: (query: string) => void;
  /** Callback при удалении конкретного элемента */
  onRemove: (query: string) => void;
  /** Callback при очистке всей истории */
  onClear: () => void;
  /** Дополнительные CSS классы */
  className?: string;
}

/**
 * Компонент отображения истории поиска
 *
 * Показывает список последних поисковых запросов с возможностью:
 * - Клик по элементу → выполнить поиск
 * - Удаление конкретного элемента (иконка X)
 * - Очистка всей истории с подтверждением
 *
 * @example
 * ```tsx
 * <SearchHistory
 *   history={['кроссовки Nike', 'футболка Adidas']}
 *   onSelect={(query) => handleSearch(query)}
 *   onRemove={(query) => removeSearch(query)}
 *   onClear={() => clearHistory()}
 * />
 * ```
 */
export function SearchHistory({
  history,
  onSelect,
  onRemove,
  onClear,
  className,
}: SearchHistoryProps) {
  const [showConfirm, setShowConfirm] = useState(false);

  /**
   * Обработчик очистки истории с подтверждением
   */
  const handleClear = () => {
    if (showConfirm) {
      onClear();
      setShowConfirm(false);
    } else {
      setShowConfirm(true);
      // Сбросить подтверждение через 3 секунды
      setTimeout(() => setShowConfirm(false), 3000);
    }
  };

  /**
   * Обработчик удаления конкретного элемента
   */
  const handleRemove = (e: React.MouseEvent, query: string) => {
    e.stopPropagation();
    onRemove(query);
  };

  if (history.length === 0) {
    return null;
  }

  return (
    <div
      className={cn(
        'absolute top-full left-0 right-0 mt-1 z-50',
        'bg-white rounded-lg',
        'border border-[#E3E8F2]',
        'shadow-lg',
        'max-h-80 overflow-y-auto',
        'animate-in fade-in-0 zoom-in-95 duration-100',
        className
      )}
      role="listbox"
      aria-label="История поиска"
      data-testid="search-history"
    >
      {/* Заголовок секции */}
      <div className="px-4 py-2 text-caption text-text-muted font-medium border-b border-[#E3E8F2]">
        История поиска
      </div>

      {/* Список элементов истории */}
      <div className="py-1">
        {history.map((query, index) => (
          <button
            key={`${query}-${index}`}
            className={cn(
              'w-full px-4 py-2',
              'flex items-center justify-between gap-2',
              'text-left text-body text-text-primary',
              'hover:bg-[#F5F7FA]',
              'transition-colors'
            )}
            onClick={() => onSelect(query)}
            role="option"
            aria-selected={false}
            aria-label={`Выбрать запрос: ${query}`}
          >
            <div className="flex items-center gap-2 flex-1 min-w-0">
              <Clock className="w-4 h-4 text-[#7A7A7A] flex-shrink-0" aria-hidden="true" />
              <span className="truncate">{query}</span>
            </div>
            <button
              type="button"
              onClick={e => handleRemove(e, query)}
              onKeyDown={e => {
                if (e.key === 'Enter' || e.key === ' ') {
                  e.preventDefault();
                  handleRemove(e as unknown as React.MouseEvent, query);
                }
              }}
              className="p-1 rounded hover:bg-[#E3E8F2] transition-colors flex-shrink-0 cursor-pointer"
              aria-label={`Удалить запрос: ${query}`}
            >
              <X className="w-4 h-4 text-text-muted hover:text-text-primary" />
            </button>
          </button>
        ))}
      </div>

      {/* Кнопка очистки истории */}
      <div className="border-t border-[#E3E8F2]">
        <button
          onClick={handleClear}
          className={cn(
            'w-full px-4 py-2',
            'text-caption text-center',
            'transition-colors',
            showConfirm
              ? 'text-red-600 font-medium hover:bg-red-50'
              : 'text-text-muted hover:text-text-primary hover:bg-[#F5F7FA]'
          )}
          aria-label="Очистить историю поиска"
          type="button"
        >
          {showConfirm ? 'Нажмите еще раз для подтверждения' : 'Очистить историю'}
        </button>
      </div>
    </div>
  );
}
