/**
 * useDebounce Hook
 * Debounces a value with specified delay
 *
 * @see docs/stories/epic-12/12.5.story.md#Task4.5
 */

import { useState, useEffect } from 'react';

/**
 * Debounce hook для отложенного обновления значения
 *
 * @param value - Значение для debounce
 * @param delay - Задержка в миллисекундах
 * @returns Debounced значение
 *
 * @example
 * ```tsx
 * const [searchQuery, setSearchQuery] = useState('');
 * const debouncedQuery = useDebounce(searchQuery, 300);
 *
 * useEffect(() => {
 *   // API call with debouncedQuery
 * }, [debouncedQuery]);
 * ```
 */
export function useDebounce<T>(value: T, delay: number): T {
  const [debouncedValue, setDebouncedValue] = useState<T>(value);

  useEffect(() => {
    const timer = setTimeout(() => setDebouncedValue(value), delay);
    return () => clearTimeout(timer);
  }, [value, delay]);

  return debouncedValue;
}
