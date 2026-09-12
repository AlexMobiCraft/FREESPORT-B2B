/**
 * Тесты хука useCookieConsent.
 * Story 41.1 — AC2, AC4, AC5, AC7.
 *
 * Хук держит состояние в модульном сторе (useSyncExternalStore), поэтому
 * оно переживает размонтирование компонентов. Каждый тест обязан звать
 * __resetCookieConsentStoreForTests() и чистить оба ключа хранилища —
 * иначе тесты начнут зависеть от порядка выполнения.
 */

import { act, renderHook, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { useCookieConsent, __resetCookieConsentStoreForTests } from '../useCookieConsent';

const STORAGE_KEY = 'cookie_consent';
const LEGACY_STORAGE_KEY = 'cookie_consent_accepted';
const LEGACY_ACCEPTED_VALUE = '1';
const originalLocalStorageDescriptor = Object.getOwnPropertyDescriptor(window, 'localStorage');

/** Подменяет window.localStorage переданной заглушкой. */
function mockLocalStorage(value: Partial<Storage>): void {
  Object.defineProperty(window, 'localStorage', {
    configurable: true,
    value: {
      getItem: vi.fn(() => null),
      setItem: vi.fn(),
      removeItem: vi.fn(),
      clear: vi.fn(),
      ...value,
    },
  });
}

describe('useCookieConsent', () => {
  beforeEach(() => {
    __resetCookieConsentStoreForTests();
    window.localStorage.clear();
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.restoreAllMocks();
    if (originalLocalStorageDescriptor) {
      Object.defineProperty(window, 'localStorage', originalLocalStorageDescriptor);
    }
    window.localStorage.clear();
    __resetCookieConsentStoreForTests();
  });

  describe('чтение хранилища и три статуса (AC2)', () => {
    it('пустое хранилище даёт статус unset и показывает баннер', async () => {
      const { result } = renderHook(() => useCookieConsent());

      await waitFor(() => expect(result.current.isLoaded).toBe(true));

      expect(result.current.status).toBe('unset');
      expect(result.current.isBannerVisible).toBe(true);
    });

    it('сохранённое accepted скрывает баннер', async () => {
      window.localStorage.setItem(STORAGE_KEY, 'accepted');

      const { result } = renderHook(() => useCookieConsent());

      await waitFor(() => expect(result.current.isLoaded).toBe(true));

      expect(result.current.status).toBe('accepted');
      expect(result.current.isBannerVisible).toBe(false);
    });

    it('сохранённое declined скрывает баннер и отличимо от accepted', async () => {
      window.localStorage.setItem(STORAGE_KEY, 'declined');

      const { result } = renderHook(() => useCookieConsent());

      await waitFor(() => expect(result.current.isLoaded).toBe(true));

      expect(result.current.status).toBe('declined');
      expect(result.current.isBannerVisible).toBe(false);
    });

    it('игнорирует чужое значение в ключе — статус unset', async () => {
      window.localStorage.setItem(STORAGE_KEY, 'abc');

      const { result } = renderHook(() => useCookieConsent());

      await waitFor(() => expect(result.current.isLoaded).toBe(true));

      expect(result.current.status).toBe('unset');
      expect(result.current.isBannerVisible).toBe(true);
    });
  });

  describe('действия accept / decline / reopen (AC2, AC3)', () => {
    it('accept записывает accepted и скрывает баннер', async () => {
      const { result } = renderHook(() => useCookieConsent());
      await waitFor(() => expect(result.current.isLoaded).toBe(true));

      act(() => {
        result.current.accept();
      });

      expect(window.localStorage.getItem(STORAGE_KEY)).toBe('accepted');
      expect(result.current.status).toBe('accepted');
      expect(result.current.isBannerVisible).toBe(false);
    });

    it('decline записывает declined и скрывает баннер', async () => {
      const { result } = renderHook(() => useCookieConsent());
      await waitFor(() => expect(result.current.isLoaded).toBe(true));

      act(() => {
        result.current.decline();
      });

      expect(window.localStorage.getItem(STORAGE_KEY)).toBe('declined');
      expect(result.current.status).toBe('declined');
      expect(result.current.isBannerVisible).toBe(false);
    });

    it('reopen показывает баннер, не стирая сохранённый выбор', async () => {
      window.localStorage.setItem(STORAGE_KEY, 'declined');
      const { result } = renderHook(() => useCookieConsent());
      await waitFor(() => expect(result.current.isLoaded).toBe(true));

      act(() => {
        result.current.reopen();
      });

      expect(result.current.isBannerVisible).toBe(true);
      expect(result.current.isForced).toBe(true);
      // Выбор перезаписывается только кнопками баннера — reopen хранилище не трогает.
      expect(window.localStorage.getItem(STORAGE_KEY)).toBe('declined');
      expect(result.current.status).toBe('declined');
    });

    it('accept после reopen сбрасывает признак принудительного показа', async () => {
      window.localStorage.setItem(STORAGE_KEY, 'declined');
      const { result } = renderHook(() => useCookieConsent());
      await waitFor(() => expect(result.current.isLoaded).toBe(true));

      act(() => {
        result.current.reopen();
      });
      act(() => {
        result.current.accept();
      });

      expect(result.current.isForced).toBe(false);
      expect(result.current.isBannerVisible).toBe(false);
      expect(window.localStorage.getItem(STORAGE_KEY)).toBe('accepted');
    });

    it('decline после reopen сбрасывает признак принудительного показа', async () => {
      window.localStorage.setItem(STORAGE_KEY, 'accepted');
      const { result } = renderHook(() => useCookieConsent());
      await waitFor(() => expect(result.current.isLoaded).toBe(true));

      act(() => {
        result.current.reopen();
      });
      act(() => {
        result.current.decline();
      });

      expect(result.current.isForced).toBe(false);
      expect(result.current.isBannerVisible).toBe(false);
      expect(window.localStorage.getItem(STORAGE_KEY)).toBe('declined');
    });
  });

  describe('миграция legacy-ключа (AC2)', () => {
    it('legacy cookie_consent_accepted=1 читается как accepted, переписывается и удаляется', async () => {
      window.localStorage.setItem(LEGACY_STORAGE_KEY, LEGACY_ACCEPTED_VALUE);

      const { result } = renderHook(() => useCookieConsent());
      await waitFor(() => expect(result.current.isLoaded).toBe(true));

      expect(result.current.status).toBe('accepted');
      expect(result.current.isBannerVisible).toBe(false);
      expect(window.localStorage.getItem(STORAGE_KEY)).toBe('accepted');
      expect(window.localStorage.getItem(LEGACY_STORAGE_KEY)).toBeNull();
    });

    it('валидное значение нового ключа имеет приоритет над legacy', async () => {
      window.localStorage.setItem(STORAGE_KEY, 'declined');
      window.localStorage.setItem(LEGACY_STORAGE_KEY, LEGACY_ACCEPTED_VALUE);

      const { result } = renderHook(() => useCookieConsent());
      await waitFor(() => expect(result.current.isLoaded).toBe(true));

      expect(result.current.status).toBe('declined');
    });

    it('legacy-значение, отличное от 1, не мигрируется', async () => {
      window.localStorage.setItem(LEGACY_STORAGE_KEY, '0');

      const { result } = renderHook(() => useCookieConsent());
      await waitFor(() => expect(result.current.isLoaded).toBe(true));

      expect(result.current.status).toBe('unset');
      expect(window.localStorage.getItem(STORAGE_KEY)).toBeNull();
    });

    it('сбой записи при миграции не сбрасывает согласие и логируется как ошибка записи', async () => {
      const consoleErrorSpy = vi.spyOn(console, 'error').mockImplementation(() => {});
      const removeItem = vi.fn();
      mockLocalStorage({
        getItem: vi.fn((key: string) => (key === LEGACY_STORAGE_KEY ? LEGACY_ACCEPTED_VALUE : null)),
        setItem: vi.fn(() => {
          throw new Error('storage is unavailable');
        }),
        removeItem,
      });

      const { result } = renderHook(() => useCookieConsent());
      await waitFor(() => expect(result.current.isLoaded).toBe(true));

      expect(result.current.status).toBe('accepted');
      expect(consoleErrorSpy).toHaveBeenCalledWith(
        'useCookieConsent: запись localStorage не удалась',
        expect.any(Error)
      );
      // Старый ключ удаляется только после успешной записи нового.
      expect(removeItem).not.toHaveBeenCalled();
    });
  });

  describe('сбой хранилища (AC5)', () => {
    it('не падает, если localStorage.getItem бросает исключение', async () => {
      const consoleErrorSpy = vi.spyOn(console, 'error').mockImplementation(() => {});
      mockLocalStorage({
        getItem: vi.fn(() => {
          throw new Error('storage is unavailable');
        }),
      });

      const { result } = renderHook(() => useCookieConsent());
      await waitFor(() => expect(result.current.isLoaded).toBe(true));

      expect(result.current.status).toBe('unset');
      expect(result.current.isBannerVisible).toBe(true);
      expect(consoleErrorSpy).toHaveBeenCalledWith(
        'useCookieConsent: чтение localStorage не удалось',
        expect.any(Error)
      );
    });

    it('скрывает баннер до перезагрузки страницы, если localStorage.setItem бросает исключение', async () => {
      const consoleErrorSpy = vi.spyOn(console, 'error').mockImplementation(() => {});
      mockLocalStorage({
        setItem: vi.fn(() => {
          throw new Error('storage is unavailable');
        }),
      });

      const { result } = renderHook(() => useCookieConsent());
      await waitFor(() => expect(result.current.isLoaded).toBe(true));

      act(() => {
        result.current.decline();
      });

      expect(result.current.status).toBe('declined');
      expect(result.current.isBannerVisible).toBe(false);
      expect(consoleErrorSpy).toHaveBeenCalledWith(
        'useCookieConsent: запись localStorage не удалась',
        expect.any(Error)
      );
    });

    it('после сбоя записи баннер всё равно открывается по reopen', async () => {
      vi.spyOn(console, 'error').mockImplementation(() => {});
      mockLocalStorage({
        setItem: vi.fn(() => {
          throw new Error('storage is unavailable');
        }),
      });

      const { result } = renderHook(() => useCookieConsent());
      await waitFor(() => expect(result.current.isLoaded).toBe(true));

      act(() => {
        result.current.decline();
      });
      expect(result.current.isBannerVisible).toBe(false);

      act(() => {
        result.current.reopen();
      });
      expect(result.current.isBannerVisible).toBe(true);
    });
  });

  describe('общее состояние между потребителями (AC4)', () => {
    it('два независимых потребителя хука видят одно состояние', async () => {
      const first = renderHook(() => useCookieConsent());
      const second = renderHook(() => useCookieConsent());

      await waitFor(() => expect(first.result.current.isLoaded).toBe(true));
      await waitFor(() => expect(second.result.current.isLoaded).toBe(true));

      act(() => {
        first.result.current.decline();
      });

      expect(second.result.current.status).toBe('declined');
      expect(second.result.current.isBannerVisible).toBe(false);

      act(() => {
        second.result.current.reopen();
      });

      expect(first.result.current.isBannerVisible).toBe(true);
    });
  });

  describe('синхронизация между вкладками', () => {
    // В браузере событие storage приходит уже ПОСЛЕ того, как запись другой
    // вкладки стала видна в общем localStorage, а обработчик читает именно
    // хранилище, а не event.newValue. Поэтому тесты имитируют другую вкладку
    // явно: сначала меняют localStorage, затем шлют событие.
    it('внешнее accepted закрывает принудительно открытый баннер', async () => {
      window.localStorage.setItem(STORAGE_KEY, 'declined');
      const { result } = renderHook(() => useCookieConsent());
      await waitFor(() => expect(result.current.isLoaded).toBe(true));

      act(() => {
        result.current.reopen();
      });
      expect(result.current.isBannerVisible).toBe(true);

      window.localStorage.setItem(STORAGE_KEY, 'accepted');
      act(() => {
        window.dispatchEvent(
          new StorageEvent('storage', {
            key: STORAGE_KEY,
            newValue: 'accepted',
            storageArea: window.localStorage,
          })
        );
      });

      expect(result.current.status).toBe('accepted');
      expect(result.current.isForced).toBe(false);
      expect(result.current.isBannerVisible).toBe(false);
    });

    it('внешнее declined закрывает баннер первого визита', async () => {
      const { result } = renderHook(() => useCookieConsent());
      await waitFor(() => expect(result.current.isLoaded).toBe(true));
      expect(result.current.isBannerVisible).toBe(true);

      window.localStorage.setItem(STORAGE_KEY, 'declined');
      act(() => {
        window.dispatchEvent(
          new StorageEvent('storage', {
            key: STORAGE_KEY,
            newValue: 'declined',
            storageArea: window.localStorage,
          })
        );
      });

      expect(result.current.status).toBe('declined');
      expect(result.current.isBannerVisible).toBe(false);
    });

    it('удаление ключа в другой вкладке возвращает статус unset', async () => {
      window.localStorage.setItem(STORAGE_KEY, 'accepted');
      const { result } = renderHook(() => useCookieConsent());
      await waitFor(() => expect(result.current.isLoaded).toBe(true));

      window.localStorage.removeItem(STORAGE_KEY);
      act(() => {
        window.dispatchEvent(
          new StorageEvent('storage', {
            key: STORAGE_KEY,
            newValue: null,
            storageArea: window.localStorage,
          })
        );
      });

      expect(result.current.status).toBe('unset');
      expect(result.current.isBannerVisible).toBe(true);
    });

    it('событие по чужому ключу игнорируется', async () => {
      window.localStorage.setItem(STORAGE_KEY, 'accepted');
      const { result } = renderHook(() => useCookieConsent());
      await waitFor(() => expect(result.current.isLoaded).toBe(true));

      act(() => {
        window.dispatchEvent(
          new StorageEvent('storage', {
            key: 'other_key',
            newValue: 'declined',
            storageArea: window.localStorage,
          })
        );
      });

      expect(result.current.status).toBe('accepted');
    });

    it('событие без фактического изменения не вызывает ре-рендер', async () => {
      window.localStorage.setItem(STORAGE_KEY, 'accepted');
      let renderCount = 0;
      const { result } = renderHook(() => {
        renderCount += 1;
        return useCookieConsent();
      });
      await waitFor(() => expect(result.current.isLoaded).toBe(true));

      const rendersBefore = renderCount;
      act(() => {
        window.dispatchEvent(
          new StorageEvent('storage', {
            key: STORAGE_KEY,
            newValue: 'accepted',
            storageArea: window.localStorage,
          })
        );
      });

      expect(renderCount).toBe(rendersBefore);
    });

    it('событие из sessionStorage с тем же ключом игнорируется', async () => {
      // sessionStorage — другое хранилище: одноимённый ключ в нём не является
      // сохранённым согласием и не должен закрывать баннер.
      const { result } = renderHook(() => useCookieConsent());
      await waitFor(() => expect(result.current.isLoaded).toBe(true));
      expect(result.current.status).toBe('unset');

      act(() => {
        window.dispatchEvent(
          new StorageEvent('storage', {
            key: STORAGE_KEY,
            newValue: 'accepted',
            storageArea: window.sessionStorage,
          })
        );
      });

      expect(result.current.status).toBe('unset');
      expect(result.current.isBannerVisible).toBe(true);
    });

    it('событие без storageArea игнорируется', async () => {
      const { result } = renderHook(() => useCookieConsent());
      await waitFor(() => expect(result.current.isLoaded).toBe(true));

      act(() => {
        window.dispatchEvent(new StorageEvent('storage', { key: STORAGE_KEY, newValue: 'accepted' }));
      });

      expect(result.current.status).toBe('unset');
    });

    it('localStorage.clear() в другой вкладке возвращает статус unset', async () => {
      // Полная очистка приходит событием с key === null: без её обработки
      // здесь остался бы устаревший статус и баннер больше не показался бы.
      window.localStorage.setItem(STORAGE_KEY, 'accepted');
      const { result } = renderHook(() => useCookieConsent());
      await waitFor(() => expect(result.current.isLoaded).toBe(true));
      expect(result.current.status).toBe('accepted');

      window.localStorage.clear();
      act(() => {
        window.dispatchEvent(
          new StorageEvent('storage', {
            key: null,
            newValue: null,
            storageArea: window.localStorage,
          })
        );
      });

      expect(result.current.status).toBe('unset');
      expect(result.current.isBannerVisible).toBe(true);
    });

    it('очистка sessionStorage в другой вкладке статус не трогает', async () => {
      window.localStorage.setItem(STORAGE_KEY, 'accepted');
      const { result } = renderHook(() => useCookieConsent());
      await waitFor(() => expect(result.current.isLoaded).toBe(true));

      act(() => {
        window.dispatchEvent(
          new StorageEvent('storage', {
            key: null,
            newValue: null,
            storageArea: window.sessionStorage,
          })
        );
      });

      expect(result.current.status).toBe('accepted');
    });

    it('обработчик события не пишет обратно в localStorage', async () => {
      // Шпион вместо подмены объекта: обработчик сверяет event.storageArea
      // именно с window.localStorage, поэтому хранилище должно остаться настоящим.
      const setItem = vi.spyOn(window.localStorage, 'setItem');

      const { result } = renderHook(() => useCookieConsent());
      await waitFor(() => expect(result.current.isLoaded).toBe(true));

      // Запись другой вкладки — не запись обработчика: после неё счётчик обнуляется.
      window.localStorage.setItem(STORAGE_KEY, 'declined');
      setItem.mockClear();

      act(() => {
        window.dispatchEvent(
          new StorageEvent('storage', {
            key: STORAGE_KEY,
            newValue: 'declined',
            storageArea: window.localStorage,
          })
        );
      });

      expect(result.current.status).toBe('declined');
      expect(setItem).not.toHaveBeenCalled();
      setItem.mockRestore();
    });

    it('устаревшее событие не перезаписывает более новый локальный выбор', async () => {
      // Гонка: событие другой вкладки с accepted уже поставлено в очередь, но до
      // его доставки пользователь в этой вкладке нажал «Отклонить». Источник
      // истины — текущее содержимое localStorage, а не event.newValue.
      const { result } = renderHook(() => useCookieConsent());
      await waitFor(() => expect(result.current.isLoaded).toBe(true));

      act(() => {
        result.current.decline();
      });
      expect(window.localStorage.getItem(STORAGE_KEY)).toBe('declined');

      act(() => {
        window.dispatchEvent(
          new StorageEvent('storage', {
            key: STORAGE_KEY,
            newValue: 'accepted',
            storageArea: window.localStorage,
          })
        );
      });

      expect(result.current.status).toBe('declined');
      expect(result.current.isBannerVisible).toBe(false);
      expect(window.localStorage.getItem(STORAGE_KEY)).toBe('declined');
    });

    it('при сбое чтения во время события используется event.newValue и логируется ошибка чтения', async () => {
      const consoleErrorSpy = vi.spyOn(console, 'error').mockImplementation(() => {});
      const { result } = renderHook(() => useCookieConsent());
      await waitFor(() => expect(result.current.isLoaded).toBe(true));

      // Spy снимается явно: vi.restoreAllMocks() в afterEach его не восстанавливает,
      // и сломанный getItem утёк бы в следующие тесты.
      const getItem = vi.spyOn(window.localStorage, 'getItem').mockImplementation(() => {
        throw new Error('storage is unavailable');
      });

      try {
        act(() => {
          window.dispatchEvent(
            new StorageEvent('storage', {
              key: STORAGE_KEY,
              newValue: 'accepted',
              storageArea: window.localStorage,
            })
          );
        });
      } finally {
        getItem.mockRestore();
      }

      expect(result.current.status).toBe('accepted');
      expect(consoleErrorSpy).toHaveBeenCalledWith(
        'useCookieConsent: чтение localStorage не удалось',
        expect.any(Error)
      );
    });

    it('legacy-ключ, записанный старой вкладкой во время выката, читается как accepted', async () => {
      // Во время выката вкладка со старым бандлом пишет cookie_consent_accepted='1'.
      // Открытая вкладка с новым бандлом обязана принять это согласие, а не
      // держать баннер до перезагрузки.
      const { result } = renderHook(() => useCookieConsent());
      await waitFor(() => expect(result.current.isLoaded).toBe(true));
      expect(result.current.isBannerVisible).toBe(true);

      window.localStorage.setItem(LEGACY_STORAGE_KEY, LEGACY_ACCEPTED_VALUE);
      act(() => {
        window.dispatchEvent(
          new StorageEvent('storage', {
            key: LEGACY_STORAGE_KEY,
            newValue: LEGACY_ACCEPTED_VALUE,
            storageArea: window.localStorage,
          })
        );
      });

      expect(result.current.status).toBe('accepted');
      expect(result.current.isBannerVisible).toBe(false);
      // Та же безопасная миграция, что и при чтении хранилища.
      expect(window.localStorage.getItem(STORAGE_KEY)).toBe('accepted');
      expect(window.localStorage.getItem(LEGACY_STORAGE_KEY)).toBeNull();
    });

    it('legacy-событие не перебивает валидное значение нового ключа', async () => {
      window.localStorage.setItem(STORAGE_KEY, 'declined');
      const { result } = renderHook(() => useCookieConsent());
      await waitFor(() => expect(result.current.isLoaded).toBe(true));

      window.localStorage.setItem(LEGACY_STORAGE_KEY, LEGACY_ACCEPTED_VALUE);
      act(() => {
        window.dispatchEvent(
          new StorageEvent('storage', {
            key: LEGACY_STORAGE_KEY,
            newValue: LEGACY_ACCEPTED_VALUE,
            storageArea: window.localStorage,
          })
        );
      });

      expect(result.current.status).toBe('declined');
      expect(window.localStorage.getItem(STORAGE_KEY)).toBe('declined');
    });

    it('legacy-событие со значением, отличным от 1, статус не меняет', async () => {
      const { result } = renderHook(() => useCookieConsent());
      await waitFor(() => expect(result.current.isLoaded).toBe(true));

      window.localStorage.setItem(LEGACY_STORAGE_KEY, '0');
      act(() => {
        window.dispatchEvent(
          new StorageEvent('storage', {
            key: LEGACY_STORAGE_KEY,
            newValue: '0',
            storageArea: window.localStorage,
          })
        );
      });

      expect(result.current.status).toBe('unset');
      expect(result.current.isBannerVisible).toBe(true);
      expect(window.localStorage.getItem(STORAGE_KEY)).toBeNull();
    });

    it('при сбое чтения legacy-событие принимается по event.newValue', async () => {
      const consoleErrorSpy = vi.spyOn(console, 'error').mockImplementation(() => {});
      const { result } = renderHook(() => useCookieConsent());
      await waitFor(() => expect(result.current.isLoaded).toBe(true));

      const getItem = vi.spyOn(window.localStorage, 'getItem').mockImplementation(() => {
        throw new Error('storage is unavailable');
      });

      try {
        act(() => {
          window.dispatchEvent(
            new StorageEvent('storage', {
              key: LEGACY_STORAGE_KEY,
              newValue: LEGACY_ACCEPTED_VALUE,
              storageArea: window.localStorage,
            })
          );
        });
      } finally {
        getItem.mockRestore();
      }

      expect(result.current.status).toBe('accepted');
      expect(consoleErrorSpy).toHaveBeenCalledWith(
        'useCookieConsent: чтение localStorage не удалось',
        expect.any(Error)
      );
    });
  });

  describe('стабильность снимка (AC4)', () => {
    it('повторный reopen не пересоздаёт снимок и не вызывает ре-рендер', async () => {
      window.localStorage.setItem(STORAGE_KEY, 'accepted');
      let renderCount = 0;
      const { result } = renderHook(() => {
        renderCount += 1;
        return useCookieConsent();
      });
      await waitFor(() => expect(result.current.isLoaded).toBe(true));

      act(() => {
        result.current.reopen();
      });
      expect(result.current.isForced).toBe(true);
      const rendersAfterFirstReopen = renderCount;

      act(() => {
        result.current.reopen();
      });

      expect(renderCount).toBe(rendersAfterFirstReopen);
      expect(result.current.isForced).toBe(true);
      expect(result.current.isBannerVisible).toBe(true);
    });

    it('повторный accept с тем же статусом не вызывает ре-рендер', async () => {
      window.localStorage.setItem(STORAGE_KEY, 'accepted');
      let renderCount = 0;
      const { result } = renderHook(() => {
        renderCount += 1;
        return useCookieConsent();
      });
      await waitFor(() => expect(result.current.isLoaded).toBe(true));

      const rendersBefore = renderCount;
      act(() => {
        result.current.accept();
      });

      expect(renderCount).toBe(rendersBefore);
      expect(result.current.status).toBe('accepted');
    });
  });
});
