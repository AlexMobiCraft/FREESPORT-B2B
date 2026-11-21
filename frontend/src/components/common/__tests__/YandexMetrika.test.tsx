/**
 * Тесты гейтинга Яндекс Метрики cookie-согласием (стори 41.14).
 *
 * Критический инвариант: ни один запрос/вызов счётчика не уходит до выбора
 * (status 'unset') и после отказа (status 'declined'). Согласие привязано к
 * версии текста баннера — неверсионные и legacy-значения счётчик не запускают.
 */

import { render, renderHook, act, waitFor } from '@testing-library/react';
import { usePathname } from 'next/navigation';
import { beforeEach, afterEach, describe, expect, it, vi } from 'vitest';
import YandexMetrika from '../YandexMetrika';
import {
  useCookieConsent,
  __resetCookieConsentStoreForTests,
  CONSENT_VERSION,
} from '@/hooks/useCookieConsent';

vi.mock('next/navigation', () => ({
  usePathname: vi.fn(() => '/'),
}));

const STORAGE_KEY = 'cookie_consent';
const ACCEPTED = `accepted:v${CONSENT_VERSION}`;
const SCRIPT_URL = 'https://mc.yandex.ru/metrika/tag.js';
const TEST_COUNTER_ID = '12345678';

const mockedUsePathname = vi.mocked(usePathname);

// happy-dom глушит загрузку внешних скриптов исключением в virtual console —
// тестам сеть счётчика не нужна, поэтому переводим её в успешный load,
// иначе вывод зашумляется стектрейсами NotSupportedError.
const happyDomApi = (
  window as unknown as {
    happyDOM?: { settings: { handleDisabledFileLoadingAsSuccess: boolean } };
  }
).happyDOM;
if (happyDomApi) {
  happyDomApi.settings.handleDisabledFileLoadingAsSuccess = true;
}

function metrikaScript(): HTMLScriptElement | null {
  return document.querySelector(`script[src="${SCRIPT_URL}"]`);
}

describe('YandexMetrika', () => {
  beforeEach(() => {
    __resetCookieConsentStoreForTests();
    window.localStorage.clear();
    vi.clearAllMocks();
    mockedUsePathname.mockReturnValue('/');
    process.env.NEXT_PUBLIC_YM_ID = TEST_COUNTER_ID;
    delete window.ym;
    metrikaScript()?.remove();
  });

  afterEach(() => {
    delete process.env.NEXT_PUBLIC_YM_ID;
    delete window.ym;
    metrikaScript()?.remove();
  });

  it('без NEXT_PUBLIC_YM_ID не делает ничего даже при принятом согласии', async () => {
    delete process.env.NEXT_PUBLIC_YM_ID;
    window.localStorage.setItem(STORAGE_KEY, ACCEPTED);

    render(<YandexMetrika />);
    const driver = renderHook(() => useCookieConsent());
    await waitFor(() => expect(driver.result.current.isLoaded).toBe(true));
    expect(driver.result.current.status).toBe('accepted');

    expect(metrikaScript()).toBeNull();
    expect(window.ym).toBeUndefined();
  });

  it('при unset не загружает счётчик и не создаёт window.ym', async () => {
    render(<YandexMetrika />);
    const driver = renderHook(() => useCookieConsent());
    await waitFor(() => expect(driver.result.current.isLoaded).toBe(true));

    expect(metrikaScript()).toBeNull();
    expect(window.ym).toBeUndefined();
  });

  it('при declined не загружает счётчик', async () => {
    window.localStorage.setItem(STORAGE_KEY, `declined:v${CONSENT_VERSION}`);

    render(<YandexMetrika />);
    const driver = renderHook(() => useCookieConsent());
    await waitFor(() => expect(driver.result.current.isLoaded).toBe(true));
    expect(driver.result.current.status).toBe('declined');

    expect(metrikaScript()).toBeNull();
    expect(window.ym).toBeUndefined();
  });

  it('неверсионное accepted под текстом без Метрики счётчик не запускает', async () => {
    window.localStorage.setItem(STORAGE_KEY, 'accepted');

    render(<YandexMetrika />);
    const driver = renderHook(() => useCookieConsent());
    await waitFor(() => expect(driver.result.current.isLoaded).toBe(true));
    expect(driver.result.current.status).toBe('unset');

    expect(metrikaScript()).toBeNull();
    expect(window.ym).toBeUndefined();
  });

  it('при accepted вставляет tag.js и инициализирует счётчик минимальным набором', async () => {
    window.localStorage.setItem(STORAGE_KEY, ACCEPTED);

    render(<YandexMetrika />);
    const driver = renderHook(() => useCookieConsent());
    await waitFor(() => expect(driver.result.current.isLoaded).toBe(true));

    const script = metrikaScript();
    expect(script).not.toBeNull();
    expect(script?.async).toBe(true);
    expect(window.ym).toBeDefined();
    expect(window.ym?.a).toEqual([
      [
        Number(TEST_COUNTER_ID),
        'init',
        { clickmap: true, trackLinks: true, accurateTrackBounce: true },
      ],
    ]);
  });

  it('запускается по свежему accept без перезагрузки страницы', async () => {
    render(<YandexMetrika />);
    const driver = renderHook(() => useCookieConsent());
    await waitFor(() => expect(driver.result.current.isLoaded).toBe(true));
    expect(metrikaScript()).toBeNull();

    act(() => {
      driver.result.current.accept();
    });

    expect(metrikaScript()).not.toBeNull();
    expect(window.ym?.a?.[0]?.[1]).toBe('init');
  });

  it('шлёт hit при SPA-навигации и не дублирует hit первой страницы', async () => {
    window.localStorage.setItem(STORAGE_KEY, ACCEPTED);
    mockedUsePathname.mockReturnValue('/catalog');

    const { rerender } = render(<YandexMetrika />);
    const driver = renderHook(() => useCookieConsent());
    await waitFor(() => expect(driver.result.current.isLoaded).toBe(true));

    // init сам отправляет первый hit — в очереди должен быть только init.
    expect(window.ym?.a?.filter(call => call[1] === 'hit')).toHaveLength(0);

    mockedUsePathname.mockReturnValue('/delivery');
    rerender(<YandexMetrika />);

    const hits = window.ym?.a?.filter(call => call[1] === 'hit') ?? [];
    expect(hits).toHaveLength(1);
    expect(hits[0]?.[0]).toBe(Number(TEST_COUNTER_ID));
  });

  it('отказ после принятия останавливает счётчик и чистит следы Метрики', async () => {
    window.localStorage.setItem(STORAGE_KEY, ACCEPTED);
    document.cookie = '_ym_uid=abc; path=/';
    window.localStorage.setItem('_ym12345678:foo', 'bar');

    render(<YandexMetrika />);
    const driver = renderHook(() => useCookieConsent());
    await waitFor(() => expect(metrikaScript()).not.toBeNull());

    act(() => {
      driver.result.current.decline();
    });

    expect(metrikaScript()).toBeNull();
    expect(window.ym).toBeUndefined();
    expect(document.cookie).not.toContain('_ym_uid');
    expect(window.localStorage.getItem('_ym12345678:foo')).toBeNull();
    // Ключ согласия при очистке Метрики не задевается.
    expect(window.localStorage.getItem(STORAGE_KEY)).toBe(`declined:v${CONSENT_VERSION}`);
  });

  it('после отказа hit при навигации не уходит', async () => {
    window.localStorage.setItem(STORAGE_KEY, ACCEPTED);
    mockedUsePathname.mockReturnValue('/catalog');

    const { rerender } = render(<YandexMetrika />);
    const driver = renderHook(() => useCookieConsent());
    await waitFor(() => expect(metrikaScript()).not.toBeNull());

    act(() => {
      driver.result.current.decline();
    });

    mockedUsePathname.mockReturnValue('/delivery');
    rerender(<YandexMetrika />);

    expect(window.ym).toBeUndefined();
    expect(metrikaScript()).toBeNull();
  });

  it('повторное согласие после отказа поднимает счётчик заново', async () => {
    window.localStorage.setItem(STORAGE_KEY, ACCEPTED);

    render(<YandexMetrika />);
    const driver = renderHook(() => useCookieConsent());
    await waitFor(() => expect(metrikaScript()).not.toBeNull());

    act(() => {
      driver.result.current.decline();
    });
    expect(metrikaScript()).toBeNull();

    act(() => {
      driver.result.current.accept();
    });

    expect(metrikaScript()).not.toBeNull();
    expect(window.ym?.a?.[0]?.[1]).toBe('init');
  });

  it('не запускает Метрику и не отправляет fragment на странице отписки', async () => {
    window.localStorage.setItem(STORAGE_KEY, ACCEPTED);
    mockedUsePathname.mockReturnValue('/unsubscribe');
    window.history.replaceState(null, '', '/unsubscribe#opaque-token');

    render(<YandexMetrika />);
    const driver = renderHook(() => useCookieConsent());
    await waitFor(() => expect(driver.result.current.isLoaded).toBe(true));

    expect(metrikaScript()).toBeNull();
    expect(window.ym).toBeUndefined();
  });
});
