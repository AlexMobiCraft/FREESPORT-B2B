/**
 * useSearchHistory Hook Tests
 *
 * @see docs/stories/epic-18/18.3.search-history.md#Task5
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { useSearchHistory } from '../useSearchHistory';

// Mock localStorage
const localStorageMock = (() => {
  let store: Record<string, string> = {};

  return {
    getItem: vi.fn((key: string) => store[key] || null),
    setItem: vi.fn((key: string, value: string) => {
      store[key] = value;
    }),
    removeItem: vi.fn((key: string) => {
      delete store[key];
    }),
    clear: vi.fn(() => {
      store = {};
    }),
  };
})();

describe('useSearchHistory', () => {
  beforeEach(() => {
    // Очистить store перед каждым тестом
    localStorageMock.clear();
    vi.clearAllMocks();

    // Установить mock для localStorage
    Object.defineProperty(window, 'localStorage', {
      value: localStorageMock,
      writable: true,
    });
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  describe('Initialization', () => {
    it('should initialize with empty history', () => {
      const { result } = renderHook(() => useSearchHistory());

      expect(result.current.history).toEqual([]);
    });

    it('should load existing history from localStorage', () => {
      const existingHistory = ['кроссовки Nike', 'футболка Adidas'];
      localStorageMock.setItem('search_history', JSON.stringify(existingHistory));

      const { result } = renderHook(() => useSearchHistory());

      expect(result.current.history).toEqual(existingHistory);
    });

    it('should handle invalid JSON in localStorage', () => {
      const consoleErrorSpy = vi.spyOn(console, 'error').mockImplementation(() => {});
      localStorageMock.setItem('search_history', 'invalid json');

      const { result } = renderHook(() => useSearchHistory());

      expect(result.current.history).toEqual([]);
      expect(consoleErrorSpy).toHaveBeenCalledWith(
        'Failed to parse search history:',
        expect.any(Error)
      );

      consoleErrorSpy.mockRestore();
    });

    it('should handle non-array data in localStorage', () => {
      localStorageMock.setItem('search_history', JSON.stringify({ invalid: 'data' }));

      const { result } = renderHook(() => useSearchHistory());

      expect(result.current.history).toEqual([]);
    });
  });

  describe('addSearch', () => {
    it('should add new query to history', () => {
      const { result } = renderHook(() => useSearchHistory());

      act(() => {
        result.current.addSearch('кроссовки Nike');
      });

      expect(result.current.history).toEqual(['кроссовки Nike']);
      expect(localStorageMock.setItem).toHaveBeenCalledWith(
        'search_history',
        JSON.stringify(['кроссовки Nike'])
      );
    });

    it('should add multiple queries to history', () => {
      const { result } = renderHook(() => useSearchHistory());

      act(() => {
        result.current.addSearch('кроссовки Nike');
      });

      act(() => {
        result.current.addSearch('футболка Adidas');
      });

      expect(result.current.history).toEqual(['футболка Adidas', 'кроссовки Nike']);
    });

    it('should move duplicate to the beginning', () => {
      const { result } = renderHook(() => useSearchHistory());

      act(() => {
        result.current.addSearch('кроссовки Nike');
        result.current.addSearch('футболка Adidas');
        result.current.addSearch('шорты Puma');
      });

      act(() => {
        result.current.addSearch('футболка Adidas'); // Дубликат
      });

      expect(result.current.history).toEqual(['футболка Adidas', 'шорты Puma', 'кроссовки Nike']);
    });

    it('should limit history to 10 items', () => {
      const { result } = renderHook(() => useSearchHistory());

      act(() => {
        for (let i = 1; i <= 12; i++) {
          result.current.addSearch(`query ${i}`);
        }
      });

      expect(result.current.history).toHaveLength(10);
      expect(result.current.history[0]).toBe('query 12'); // Последний добавленный
      expect(result.current.history[9]).toBe('query 3'); // 10-й элемент
    });

    it('should trim whitespace from query', () => {
      const { result } = renderHook(() => useSearchHistory());

      act(() => {
        result.current.addSearch('  кроссовки Nike  ');
      });

      expect(result.current.history).toEqual(['кроссовки Nike']);
    });

    it('should ignore empty queries', () => {
      const { result } = renderHook(() => useSearchHistory());

      act(() => {
        result.current.addSearch('');
        result.current.addSearch('   ');
      });

      expect(result.current.history).toEqual([]);
    });

    it('should persist to localStorage after adding', () => {
      const { result } = renderHook(() => useSearchHistory());

      act(() => {
        result.current.addSearch('кроссовки Nike');
      });

      // Проверяем последний вызов setItem
      expect(localStorageMock.setItem).toHaveBeenLastCalledWith(
        'search_history',
        JSON.stringify(['кроссовки Nike'])
      );
    });
  });

  describe('removeSearch', () => {
    it('should remove specific query from history', () => {
      const { result } = renderHook(() => useSearchHistory());

      act(() => {
        result.current.addSearch('кроссовки Nike');
        result.current.addSearch('футболка Adidas');
        result.current.addSearch('шорты Puma');
      });

      act(() => {
        result.current.removeSearch('футболка Adidas');
      });

      expect(result.current.history).toEqual(['шорты Puma', 'кроссовки Nike']);
    });

    it('should do nothing if query not found', () => {
      const { result } = renderHook(() => useSearchHistory());

      act(() => {
        result.current.addSearch('кроссовки Nike');
      });

      act(() => {
        result.current.removeSearch('футболка Adidas');
      });

      expect(result.current.history).toEqual(['кроссовки Nike']);
    });

    it('should persist to localStorage after removing', () => {
      const { result } = renderHook(() => useSearchHistory());

      act(() => {
        result.current.addSearch('кроссовки Nike');
        result.current.addSearch('футболка Adidas');
      });

      act(() => {
        result.current.removeSearch('футболка Adidas');
      });

      expect(localStorageMock.setItem).toHaveBeenLastCalledWith(
        'search_history',
        JSON.stringify(['кроссовки Nike'])
      );
    });
  });

  describe('clearHistory', () => {
    it('should clear all history', () => {
      const { result } = renderHook(() => useSearchHistory());

      act(() => {
        result.current.addSearch('кроссовки Nike');
        result.current.addSearch('футболка Adidas');
        result.current.addSearch('шорты Puma');
      });

      act(() => {
        result.current.clearHistory();
      });

      expect(result.current.history).toEqual([]);
    });

    it('should persist empty history to localStorage', () => {
      const { result } = renderHook(() => useSearchHistory());

      act(() => {
        result.current.addSearch('кроссовки Nike');
      });

      act(() => {
        result.current.clearHistory();
      });

      expect(localStorageMock.setItem).toHaveBeenLastCalledWith(
        'search_history',
        JSON.stringify([])
      );
    });
  });

  // SSR compatibility проверяется на уровне реального приложения
  // В тестовом окружении window всегда доступен
});
