/**
 * useSearchHistory Hook
 * Manages search history in localStorage
 *
 * @see docs/stories/epic-18/18.3.search-history.md#Task1
 */

import { useState, useEffect } from 'react';

const STORAGE_KEY = 'search_history';
const MAX_HISTORY_ITEMS = 10;

/**
 * Return type для useSearchHistory hook
 */
export interface UseSearchHistoryReturn {
  /** Массив последних поисковых запросов */
  history: string[];
  /** Добавить запрос в историю */
  addSearch: (query: string) => void;
  /** Удалить конкретный запрос из истории */
  removeSearch: (query: string) => void;
  /** Очистить всю историю */
  clearHistory: () => void;
}

/**
 * Hook для управления историей поиска
 *
 * Хранит последние 10 поисковых запросов в localStorage.
 * Дубликаты перемещаются в начало списка.
 *
 * @returns {UseSearchHistoryReturn} Объект с историей и методами управления
 *
 * @example
 * ```tsx
 * const { history, addSearch, removeSearch, clearHistory } = useSearchHistory();
 *
 * // Добавить запрос
 * addSearch('кроссовки Nike');
 *
 * // Удалить конкретный запрос
 * removeSearch('кроссовки Nike');
 *
 * // Очистить всю историю
 * clearHistory();
 * ```
 */
export function useSearchHistory(): UseSearchHistoryReturn {
  const [history, setHistory] = useState<string[]>([]);

  // Загрузка из localStorage при монтировании
  useEffect(() => {
    if (typeof window !== 'undefined') {
      const stored = localStorage.getItem(STORAGE_KEY);
      if (stored) {
        try {
          const parsed = JSON.parse(stored);
          if (Array.isArray(parsed)) {
            setHistory(parsed);
          }
        } catch (e) {
          console.error('Failed to parse search history:', e);
        }
      }
    }
  }, []);

  // Сохранение в localStorage при изменении
  useEffect(() => {
    if (typeof window !== 'undefined') {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(history));
    }
  }, [history]);

  /**
   * Добавляет запрос в историю
   * Дубликаты перемещаются в начало
   * Ограничение до MAX_HISTORY_ITEMS элементов
   */
  const addSearch = (query: string) => {
    const trimmedQuery = query.trim();
    if (!trimmedQuery) return;

    setHistory(prev => {
      // Удаляем дубликат если существует
      const filtered = prev.filter(item => item !== trimmedQuery);
      // Добавляем в начало и ограничиваем до MAX_HISTORY_ITEMS
      return [trimmedQuery, ...filtered].slice(0, MAX_HISTORY_ITEMS);
    });
  };

  /**
   * Удаляет конкретный запрос из истории
   */
  const removeSearch = (query: string) => {
    setHistory(prev => prev.filter(item => item !== query));
  };

  /**
   * Очищает всю историю
   */
  const clearHistory = () => {
    setHistory([]);
  };

  return { history, addSearch, removeSearch, clearHistory };
}
