/**
 * useDebounce Hook Tests
 * Тесты для debounce hook
 */

import { act, renderHook } from '@testing-library/react';
import { useDebounce } from '../useDebounce';

describe('useDebounce', () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.restoreAllMocks();
  });

  it('returns initial value immediately', () => {
    const { result } = renderHook(() => useDebounce('initial', 500));

    expect(result.current).toBe('initial');
  });

  it('debounces value changes', async () => {
    const { result, rerender } = renderHook(({ value, delay }) => useDebounce(value, delay), {
      initialProps: { value: 'initial', delay: 500 },
    });

    expect(result.current).toBe('initial');

    // Изменяем значение
    act(() => {
      rerender({ value: 'updated', delay: 500 });
    });

    // Значение еще не должно измениться
    expect(result.current).toBe('initial');

    // Fast-forward time
    await act(async () => {
      await vi.advanceTimersByTimeAsync(500);
    });

    // Теперь значение должно обновиться
    expect(result.current).toBe('updated');
  });

  it('cancels previous timeout on rapid changes', async () => {
    vi.useRealTimers();
    const sleep = (ms: number) => new Promise(resolve => setTimeout(resolve, ms));

    const { result, rerender } = renderHook(({ value, delay }) => useDebounce(value, delay), {
      initialProps: { value: 'initial', delay: 500 },
    });

    await act(async () => {
      rerender({ value: 'change1', delay: 500 });
    });
    await sleep(200);

    await act(async () => {
      rerender({ value: 'change2', delay: 500 });
    });
    await sleep(200);

    await act(async () => {
      rerender({ value: 'final', delay: 500 });
    });
    await sleep(600);

    expect(result.current).toBe('final');
  }, 7000);

  it('works with different data types', () => {
    // Number
    const { result: numberResult } = renderHook(() => useDebounce(42, 300));
    expect(numberResult.current).toBe(42);

    // Boolean
    const { result: boolResult } = renderHook(() => useDebounce(true, 300));
    expect(boolResult.current).toBe(true);

    // Object
    const obj = { key: 'value' };
    const { result: objResult } = renderHook(() => useDebounce(obj, 300));
    expect(objResult.current).toBe(obj);

    // Array
    const arr = [1, 2, 3];
    const { result: arrResult } = renderHook(() => useDebounce(arr, 300));
    expect(arrResult.current).toBe(arr);
  });

  it('respects custom delay', async () => {
    vi.useRealTimers();
    const sleep = (ms: number) => new Promise(resolve => setTimeout(resolve, ms));

    const { result, rerender } = renderHook(({ value, delay }) => useDebounce(value, delay), {
      initialProps: { value: 'initial', delay: 1000 },
    });

    await act(async () => {
      rerender({ value: 'updated', delay: 1000 });
    });

    await sleep(500);
    expect(result.current).toBe('initial');

    await sleep(600);
    expect(result.current).toBe('updated');
  }, 7000);

  it('cleans up timeout on unmount', () => {
    const { unmount } = renderHook(() => useDebounce('test', 500));

    const clearTimeoutSpy = vi.spyOn(global, 'clearTimeout');

    unmount();

    expect(clearTimeoutSpy).toHaveBeenCalled();
  });
});
