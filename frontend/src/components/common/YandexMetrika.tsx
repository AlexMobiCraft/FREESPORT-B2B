'use client';

/**
 * Яндекс Метрика с гейтингом cookie-согласия (стори 41.14).
 *
 * Инвариант ФЗ-152: tag.js загружается и счётчик получает данные только при
 * `status === 'accepted'`. При 'unset' и 'declined' компонент инертен:
 * запросов и cookie Метрики нет ни до выбора, ни после отказа.
 *
 * Первый pageview отправляет сам tag.js при `init` — здесь вручную шлются
 * только последующие SPA-переходы (`usePathname` → `ym(id, 'hit', url)`).
 *
 * Отзыв согласия (accepted → declined): hit'ы прекращаются, тег снимается,
 * cookie и localStorage-следы Метрики чистятся. Уже выполненный в странице
 * код tag.js физически «выгрузить» нельзя, поэтому гейтится каждый вызов
 * `ym()`, а очистка best-effort — повторное согласие поднимает счётчик заново.
 */

import { usePathname } from 'next/navigation';
import { useEffect, useRef } from 'react';
import { useCookieConsent } from '@/hooks/useCookieConsent';

const SCRIPT_URL = 'https://mc.yandex.ru/metrika/tag.js';
const METRIKA_COOKIE_PREFIXES = ['_ym_', 'ymex', 'yandexuid'];
const METRIKA_STORAGE_PREFIXES = ['_ym', 'ym:'];

interface YmQueue {
  (...args: unknown[]): void;
  a?: unknown[][];
  l?: number;
}

declare global {
  interface Window {
    ym?: YmQueue;
  }
}

/** Числовой id счётчика из env; пустое или нечисловое значение отключает интеграцию. */
function counterId(): number | null {
  const id = Number.parseInt(process.env.NEXT_PUBLIC_YM_ID ?? '', 10);
  return Number.isFinite(id) ? id : null;
}

/**
 * Ставит очередь `ym`, `init` и тег tag.js — официальный паттерн сниппета.
 * Параметры — стандартный минимум по решению владельца: Вебвизор и ecommerce
 * сознательно не включены.
 */
function injectCounter(id: number): void {
  if (!window.ym) {
    const queue: YmQueue = (...args: unknown[]) => {
      (queue.a = queue.a ?? []).push(args);
    };
    queue.l = Date.now();
    window.ym = queue;
  }

  window.ym(id, 'init', {
    clickmap: true,
    trackLinks: true,
    accurateTrackBounce: true,
  });

  if (!document.querySelector(`script[src="${SCRIPT_URL}"]`)) {
    const script = document.createElement('script');
    script.async = true;
    script.src = SCRIPT_URL;
    document.head.appendChild(script);
  }
}

/**
 * Снимает cookie для правдоподобных domain-комбинаций: хост, `.` + хост и
 * родительская зона из двух меток. Cookie без domain-атрибута тоже гасится.
 */
function expireCookie(name: string): void {
  const { hostname } = window.location;
  const root = hostname.split('.').slice(-2).join('.');
  const domains = new Set(['', hostname, `.${hostname}`, `.${root}`]);
  for (const domain of domains) {
    const domainAttr = domain ? `; domain=${domain}` : '';
    document.cookie = `${name}=; expires=Thu, 01 Jan 1970 00:00:00 GMT; path=/${domainAttr}`;
  }
}

/** Приостанавливает счётчик на чувствительном маршруте, не меняя cookie-согласие. */
function suspendCounter(id: number): void {
  document.querySelector(`script[src="${SCRIPT_URL}"]`)?.remove();
  delete window.ym;
  delete (window as unknown as Record<string, unknown>)[`yaCounter${id}`];
}

/** Best-effort очистка при отзыве согласия: cookie, localStorage, тег, глобалы. */
function clearMetrikaState(id: number): void {
  for (const pair of document.cookie.split(';')) {
    const name = pair.split('=')[0]?.trim() ?? '';
    if (METRIKA_COOKIE_PREFIXES.some(prefix => name.startsWith(prefix))) {
      expireCookie(name);
    }
  }

  try {
    const storage = window.localStorage;
    const metrikaKeys: string[] = [];
    for (let i = 0; i < storage.length; i += 1) {
      const key = storage.key(i);
      if (key && METRIKA_STORAGE_PREFIXES.some(prefix => key.startsWith(prefix))) {
        metrikaKeys.push(key);
      }
    }
    metrikaKeys.forEach(key => storage.removeItem(key));
  } catch {
    // Хранилище может быть недоступно — отзыв согласия всё равно фиксируется.
  }

  suspendCounter(id);
}

export default function YandexMetrika() {
  const { status } = useCookieConsent();
  const pathname = usePathname();
  const loadedRef = useRef(false);
  const lastHitPathRef = useRef<string | null>(null);

  useEffect(() => {
    const id = counterId();
    if (!id || typeof document === 'undefined') {
      return;
    }

    if (pathname === '/unsubscribe') {
      suspendCounter(id);
      loadedRef.current = false;
      lastHitPathRef.current = null;
      return;
    }

    if (status === 'accepted') {
      if (!loadedRef.current) {
        injectCounter(id);
        loadedRef.current = true;
        // init отправляет первый hit сам — фиксируем только позицию.
        lastHitPathRef.current = pathname;
        return;
      }
      if (lastHitPathRef.current !== pathname) {
        lastHitPathRef.current = pathname;
        window.ym?.(id, 'hit', window.location.href);
      }
      return;
    }

    if (status === 'declined' && loadedRef.current) {
      clearMetrikaState(id);
      loadedRef.current = false;
      lastHitPathRef.current = null;
    }
  }, [status, pathname]);

  return null;
}
