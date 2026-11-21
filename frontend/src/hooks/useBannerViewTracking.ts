/**
 * useBannerViewTracking — единое определение показа баннера для отчётности в ОРД.
 *
 * Показ засчитывается, когда одновременно и непрерывно не меньше 1 с:
 * - не меньше 50 % площади `element` во вьюпорте (IntersectionObserver, порог 0.5);
 * - вкладка видима (`document.visibilityState === 'visible'`);
 * - загрузилась картинка именно показываемого баннера (`loadedId === activeId`).
 *
 * `activeId` — баннер, который сейчас в `element`. Если баннеры сменяют друг друга
 * в одном DOM-узле (меняется только `src` картинки), IntersectionObserver повторно не
 * срабатывает: смена `activeId` при видимом узле сама перезапускает таймер, а
 * `loadedId` прошлого баннера не даёт засчитать новый до загрузки его картинки.
 *
 * Каждый баннер засчитывается один раз за монтирование (дедуп по id; ref переживает
 * двойной mount StrictMode). Без IntersectionObserver в окружении хук ничего не делает.
 */

import { useEffect, useRef } from 'react';
import { trackBannerView } from '@/services/siteEvents';

/** Сколько баннер должен непрерывно быть видимым, чтобы засчитать показ */
export const BANNER_VIEW_DWELL_MS = 1000;
/** Доля площади баннера во вьюпорте */
export const BANNER_VIEW_THRESHOLD = 0.5;
// Браузер сообщает долю с погрешностью округления: 0.4999 на пороге — это ровно половина.
const RATIO_EPSILON = 0.001;

type BannerId = number | null | undefined;

export function useBannerViewTracking(
  element: Element | null,
  activeId: BannerId,
  loadedId: BannerId
): void {
  const seenRef = useRef<Set<number>>(new Set());
  const intersectingRef = useRef(false);
  const activeIdRef = useRef<BannerId>(activeId);
  const loadedIdRef = useRef<BannerId>(loadedId);
  const timerRef = useRef<{ id: number; handle: ReturnType<typeof setTimeout> } | null>(null);
  const evaluateRef = useRef<() => void>(() => {});

  // Единственная функция решения: идёт ли сейчас отсчёт и для какого баннера.
  // Читает только refs, поэтому её можно звать из любого колбэка.
  useEffect(() => {
    const stopTimer = () => {
      if (timerRef.current) {
        clearTimeout(timerRef.current.handle);
        timerRef.current = null;
      }
    };

    evaluateRef.current = () => {
      const id = activeIdRef.current;
      const pageVisible = typeof document === 'undefined' || document.visibilityState === 'visible';
      const target =
        id != null &&
        loadedIdRef.current === id &&
        intersectingRef.current &&
        pageVisible &&
        !seenRef.current.has(id)
          ? id
          : null;

      if (timerRef.current && timerRef.current.id === target) return;
      stopTimer();
      if (target === null) return;

      const handle = setTimeout(() => {
        timerRef.current = null;
        if (seenRef.current.has(target)) return;
        seenRef.current.add(target);
        trackBannerView(target);
      }, BANNER_VIEW_DWELL_MS);
      timerRef.current = { id: target, handle };
    };

    const onVisibilityChange = () => evaluateRef.current();
    document.addEventListener('visibilitychange', onVisibilityChange);

    return () => {
      document.removeEventListener('visibilitychange', onVisibilityChange);
      stopTimer();
      evaluateRef.current = () => {};
    };
  }, []);

  // Видимость элемента. Наблюдатель привязан только к элементу: смена баннера
  // внутри того же узла его не пересоздаёт.
  useEffect(() => {
    if (!element || typeof IntersectionObserver === 'undefined') return;

    const observer = new IntersectionObserver(
      entries => {
        const entry = entries[entries.length - 1];
        if (!entry) return;
        intersectingRef.current =
          entry.isIntersecting && entry.intersectionRatio >= BANNER_VIEW_THRESHOLD - RATIO_EPSILON;
        evaluateRef.current();
      },
      { threshold: [0, BANNER_VIEW_THRESHOLD] }
    );
    observer.observe(element);

    return () => {
      observer.disconnect();
      intersectingRef.current = false;
      evaluateRef.current();
    };
  }, [element]);

  // Смена показываемого баннера или загрузка его картинки.
  useEffect(() => {
    activeIdRef.current = activeId;
    loadedIdRef.current = loadedId;
    evaluateRef.current();
  }, [activeId, loadedId]);
}

export default useBannerViewTracking;
