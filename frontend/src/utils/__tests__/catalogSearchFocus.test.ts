import { afterEach, describe, expect, it, vi } from 'vitest';

import {
  CATALOG_SEARCH_FOCUS_EVENT,
  CATALOG_SEARCH_HASH,
  CATALOG_SEARCH_HREF,
  requestCatalogSearchFocus,
} from '../catalogSearchFocus';

describe('catalogSearchFocus', () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('адрес поиска ведёт на фрагмент каталога без query-параметров', () => {
    expect(CATALOG_SEARCH_HASH).toBe('search');
    expect(CATALOG_SEARCH_HREF).toBe('/catalog#search');
    expect(CATALOG_SEARCH_HREF).not.toContain('?');
  });

  it('requestCatalogSearchFocus рассылает событие фокуса', () => {
    const listener = vi.fn();
    window.addEventListener(CATALOG_SEARCH_FOCUS_EVENT, listener);

    requestCatalogSearchFocus();

    window.removeEventListener(CATALOG_SEARCH_FOCUS_EVENT, listener);
    expect(listener).toHaveBeenCalledTimes(1);
  });

  it('безопасна без window (серверный рендер)', () => {
    vi.stubGlobal('window', undefined);

    expect(() => requestCatalogSearchFocus()).not.toThrow();
  });
});
