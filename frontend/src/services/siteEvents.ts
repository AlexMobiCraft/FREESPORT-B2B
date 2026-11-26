/**
 * Очередь событий баннеров (показы и клики) для отчётности в ОРД.
 *
 * События копятся в памяти и уходят пачкой на `POST /api/v1/site-events/`:
 * - через 5 с после первого события в пустой очереди (пустая очередь ничего не шлёт);
 * - при уходе со страницы (`visibilitychange → hidden`, `pagehide`);
 * - сразу при клике — переход по ссылке баннера не ждёт отправки.
 *
 * `fetch` с `keepalive: true` доживает до выгрузки страницы; `credentials: 'omit'` —
 * без cookie; `Content-Type: text/plain` — CORS-safelisted, запрос уходит без preflight
 * (сервер разбирает тело как JSON). Счётчик не обрабатывает персональные данные,
 * поэтому не зависит от согласия на cookie и не трогает Яндекс Метрику.
 *
 * Любой сбой отправки проглатывается: статистика не должна ломать показ баннера
 * и переход по ссылке.
 */

import { API_URL_PUBLIC } from '@/services/api-client';

export type SiteEventKind = 'view' | 'click';

export interface SiteEvent {
  banner_id: number;
  kind: SiteEventKind;
}

/** Задержка отправки очереди после первого события */
export const SITE_EVENTS_FLUSH_DELAY_MS = 5000;
/** Не больше событий в одном запросе — лимит сервера */
export const SITE_EVENTS_MAX_BATCH = 50;

// Путь без слов banner/ad/promo/collect — их режут блокировщики рекламы.
const SITE_EVENTS_PATH = '/site-events/';

let queue: SiteEvent[] = [];
let flushTimer: ReturnType<typeof setTimeout> | null = null;
let listenersAttached = false;

const getEndpoint = (): string => `${API_URL_PUBLIC.replace(/\/+$/, '')}${SITE_EVENTS_PATH}`;

const send = (events: SiteEvent[]): void => {
  try {
    if (typeof fetch !== 'function') return;
    fetch(getEndpoint(), {
      method: 'POST',
      body: JSON.stringify({ events }),
      keepalive: true,
      credentials: 'omit',
      headers: { 'Content-Type': 'text/plain' },
    }).catch(() => {
      // Статистика теряется молча: повтор при 429/сбое не нужен.
    });
  } catch {
    // fetch может бросить синхронно (например, превышен лимит keepalive) — игнорируем.
  }
};

const handleVisibilityChange = (): void => {
  if (document.visibilityState === 'hidden') flushSiteEvents();
};

const handlePageHide = (): void => {
  flushSiteEvents();
};

const attachListeners = (): void => {
  if (listenersAttached || typeof window === 'undefined') return;
  document.addEventListener('visibilitychange', handleVisibilityChange);
  window.addEventListener('pagehide', handlePageHide);
  listenersAttached = true;
};

/** Немедленно отправляет всё накопленное (пачками по 50). */
export function flushSiteEvents(): void {
  if (flushTimer !== null) {
    clearTimeout(flushTimer);
    flushTimer = null;
  }
  while (queue.length > 0) {
    send(queue.splice(0, SITE_EVENTS_MAX_BATCH));
  }
}

/** Ставит событие в очередь; отправка — через 5 с, при уходе со страницы или сразу (`immediate`). */
export function queueSiteEvent(bannerId: number, kind: SiteEventKind, immediate = false): void {
  if (typeof window === 'undefined' || !Number.isInteger(bannerId) || bannerId <= 0) return;
  attachListeners();
  queue.push({ banner_id: bannerId, kind });

  if (immediate || queue.length >= SITE_EVENTS_MAX_BATCH) {
    flushSiteEvents();
    return;
  }
  if (flushTimer === null) {
    flushTimer = setTimeout(() => {
      flushTimer = null;
      flushSiteEvents();
    }, SITE_EVENTS_FLUSH_DELAY_MS);
  }
}

/** Показ баннера: ≥ 50 % площади во вьюпорте не меньше 1 с (см. useBannerViewTracking). */
export function trackBannerView(bannerId: number): void {
  queueSiteEvent(bannerId, 'view');
}

/** Клик по баннеру — уходит сразу вместе с накопленными показами. */
export function trackBannerClick(bannerId: number): void {
  queueSiteEvent(bannerId, 'click', true);
}

/** Сброс состояния модуля между тестами: очередь, таймер, слушатели. */
export function resetForTests(): void {
  queue = [];
  if (flushTimer !== null) {
    clearTimeout(flushTimer);
    flushTimer = null;
  }
  if (listenersAttached && typeof window !== 'undefined') {
    document.removeEventListener('visibilitychange', handleVisibilityChange);
    window.removeEventListener('pagehide', handlePageHide);
  }
  listenersAttached = false;
}
