import { act, renderHook, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { useCookieConsent } from '../useCookieConsent';

const STORAGE_KEY = 'cookie_consent_accepted';
const STORAGE_VALUE = '1';
const originalLocalStorageDescriptor = Object.getOwnPropertyDescriptor(window, 'localStorage');

describe('useCookieConsent', () => {
  beforeEach(() => {
    window.localStorage.clear();
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.restoreAllMocks();
    if (originalLocalStorageDescriptor) {
      Object.defineProperty(window, 'localStorage', originalLocalStorageDescriptor);
    }
    window.localStorage.clear();
  });

  it('читает пустой localStorage и помечает состояние загруженным', async () => {
    const { result } = renderHook(() => useCookieConsent());

    await waitFor(() => expect(result.current.isLoaded).toBe(true));

    expect(result.current.isAccepted).toBe(false);
  });

  it('возвращает isAccepted=true, если согласие уже записано', async () => {
    window.localStorage.setItem(STORAGE_KEY, STORAGE_VALUE);

    const { result } = renderHook(() => useCookieConsent());

    await waitFor(() => expect(result.current.isLoaded).toBe(true));

    expect(result.current.isAccepted).toBe(true);
  });

  it('accept записывает согласие и скрывает баннер для текущей сессии', async () => {
    const { result } = renderHook(() => useCookieConsent());

    await waitFor(() => expect(result.current.isLoaded).toBe(true));

    act(() => {
      result.current.accept();
    });

    expect(window.localStorage.getItem(STORAGE_KEY)).toBe(STORAGE_VALUE);
    expect(result.current.isAccepted).toBe(true);
  });

  it('игнорирует чужое значение в localStorage', async () => {
    window.localStorage.setItem(STORAGE_KEY, 'abc');

    const { result } = renderHook(() => useCookieConsent());

    await waitFor(() => expect(result.current.isLoaded).toBe(true));

    expect(result.current.isAccepted).toBe(false);
  });

  it('не падает, если localStorage.getItem бросает исключение', async () => {
    const consoleErrorSpy = vi.spyOn(console, 'error').mockImplementation(() => {});

    Object.defineProperty(window, 'localStorage', {
      configurable: true,
      value: {
        getItem: vi.fn(() => {
          throw new Error('storage is unavailable');
        }),
        setItem: vi.fn(),
        removeItem: vi.fn(),
        clear: vi.fn(),
      },
    });

    const { result } = renderHook(() => useCookieConsent());

    await waitFor(() => expect(result.current.isLoaded).toBe(true));

    expect(result.current.isAccepted).toBe(false);
    expect(consoleErrorSpy).toHaveBeenCalledWith(
      'useCookieConsent: чтение localStorage не удалось',
      expect.any(Error)
    );
  });

  it('скрывает баннер для текущей сессии, если localStorage.setItem бросает исключение', async () => {
    const consoleErrorSpy = vi.spyOn(console, 'error').mockImplementation(() => {});
    Object.defineProperty(window, 'localStorage', {
      configurable: true,
      value: {
        getItem: vi.fn(() => null),
        setItem: vi.fn(() => {
          throw new Error('storage is unavailable');
        }),
        removeItem: vi.fn(),
        clear: vi.fn(),
      },
    });

    const { result } = renderHook(() => useCookieConsent());

    await waitFor(() => expect(result.current.isLoaded).toBe(true));

    act(() => {
      result.current.accept();
    });

    expect(result.current.isAccepted).toBe(true);
    expect(consoleErrorSpy).toHaveBeenCalledWith(
      'useCookieConsent: запись localStorage не удалась',
      expect.any(Error)
    );
  });
});
