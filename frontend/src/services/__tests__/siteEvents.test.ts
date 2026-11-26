/**
 * Очередь событий баннеров (показы/клики) для отчётности в ОРД.
 */

import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';

import {
  flushSiteEvents,
  queueSiteEvent,
  resetForTests,
  SITE_EVENTS_FLUSH_DELAY_MS,
  trackBannerClick,
  trackBannerView,
} from '../siteEvents';

const ENDPOINT = 'http://localhost:8001/api/v1/site-events/';

describe('siteEvents', () => {
  let fetchMock: ReturnType<typeof vi.fn>;

  const sentBatches = () =>
    fetchMock.mock.calls.map(([, init]) => JSON.parse((init as RequestInit).body as string).events);

  beforeEach(() => {
    vi.useFakeTimers();
    resetForTests();
    fetchMock = vi.fn().mockResolvedValue(new Response(null, { status: 204 }));
    vi.stubGlobal('fetch', fetchMock);
  });

  afterEach(() => {
    resetForTests();
    vi.useRealTimers();
    vi.unstubAllGlobals();
  });

  it('копит показы и отправляет одной пачкой через 5 с', () => {
    trackBannerView(5);
    trackBannerView(6);

    vi.advanceTimersByTime(SITE_EVENTS_FLUSH_DELAY_MS - 1);
    expect(fetchMock).not.toHaveBeenCalled();

    vi.advanceTimersByTime(1);
    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(sentBatches()).toEqual([
      [
        { banner_id: 5, kind: 'view' },
        { banner_id: 6, kind: 'view' },
      ],
    ]);
  });

  it('шлёт запрос без cookie, с keepalive и text/plain', () => {
    trackBannerView(5);
    flushSiteEvents();

    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toBe(ENDPOINT);
    expect(init).toMatchObject({
      method: 'POST',
      keepalive: true,
      credentials: 'omit',
      headers: { 'Content-Type': 'text/plain' },
    });
  });

  it('путь не содержит слов из списков блокировщиков', () => {
    trackBannerView(5);
    flushSiteEvents();

    const path = new URL(fetchMock.mock.calls[0][0] as string).pathname;
    expect(path).not.toMatch(/banner|\bad|promo|collect/i);
  });

  it('пустая очередь ничего не отправляет', () => {
    vi.advanceTimersByTime(SITE_EVENTS_FLUSH_DELAY_MS * 5);
    flushSiteEvents();

    expect(fetchMock).not.toHaveBeenCalled();
  });

  it('после отправки таймер не крутится вхолостую', () => {
    trackBannerView(5);
    vi.advanceTimersByTime(SITE_EVENTS_FLUSH_DELAY_MS);
    vi.advanceTimersByTime(SITE_EVENTS_FLUSH_DELAY_MS * 5);

    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(vi.getTimerCount()).toBe(0);
  });

  it('клик уходит сразу вместе с накопленными показами', () => {
    trackBannerView(5);
    trackBannerClick(5);

    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(sentBatches()[0]).toEqual([
      { banner_id: 5, kind: 'view' },
      { banner_id: 5, kind: 'click' },
    ]);

    vi.advanceTimersByTime(SITE_EVENTS_FLUSH_DELAY_MS);
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it('уход со вкладки (visibilitychange → hidden) отправляет очередь', () => {
    trackBannerView(5);
    Object.defineProperty(document, 'visibilityState', { configurable: true, get: () => 'hidden' });
    document.dispatchEvent(new Event('visibilitychange'));
    delete (document as unknown as Record<string, unknown>).visibilityState;

    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it('visibilitychange → visible очередь не трогает', () => {
    trackBannerView(5);
    document.dispatchEvent(new Event('visibilitychange'));

    expect(fetchMock).not.toHaveBeenCalled();
  });

  it('pagehide отправляет очередь', () => {
    trackBannerView(5);
    window.dispatchEvent(new Event('pagehide'));

    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it('50 событий уходят сразу, не дожидаясь таймера', () => {
    for (let i = 0; i < 50; i += 1) trackBannerView(5);

    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(sentBatches()[0]).toHaveLength(50);
  });

  it('ошибка сети проглатывается', async () => {
    fetchMock.mockRejectedValue(new TypeError('Failed to fetch'));

    expect(() => trackBannerClick(5)).not.toThrow();
    await vi.runAllTimersAsync();
  });

  it('синхронное исключение fetch проглатывается', () => {
    fetchMock.mockImplementation(() => {
      throw new TypeError('keepalive limit');
    });

    expect(() => trackBannerClick(5)).not.toThrow();
  });

  it('без fetch в окружении ничего не ломается', () => {
    vi.stubGlobal('fetch', undefined);

    expect(() => trackBannerClick(5)).not.toThrow();
  });

  it('некорректный id не попадает в очередь', () => {
    queueSiteEvent(0, 'view');
    queueSiteEvent(-1, 'view');
    queueSiteEvent(1.5, 'view');
    queueSiteEvent(Number.NaN, 'click');
    flushSiteEvents();

    expect(fetchMock).not.toHaveBeenCalled();
  });

  it('resetForTests очищает очередь, таймер и слушатели', () => {
    trackBannerView(5);
    resetForTests();

    vi.advanceTimersByTime(SITE_EVENTS_FLUSH_DELAY_MS);
    window.dispatchEvent(new Event('pagehide'));

    expect(fetchMock).not.toHaveBeenCalled();
  });
});
