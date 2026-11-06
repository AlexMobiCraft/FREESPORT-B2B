'use client';

/**
 * Хук согласия на cookie (Story 41.1).
 *
 * Состояние хранится во внешнем модульном сторе и читается через
 * useSyncExternalStore. Так баннер из корневого layout и кнопка «Настройки
 * cookie» из подвала — компоненты разных поддеревьев — разделяют одно
 * состояние: нажатие в подвале открывает баннер без перезагрузки страницы.
 *
 * ВАЖНО для аналитики (стори 41.14): счётчик Яндекс Метрики
 * подключается ТОЛЬКО при `status === 'accepted'`, а не при
 * `status !== 'declined'` — иначе посетитель, не сделавший выбор, будет
 * отслеживаться без согласия.
 *
 * Выбор привязан к версии текста баннера: хранится значение вида
 * `${status}:v${CONSENT_VERSION}`. Согласие и отказ, данные под текстом
 * без Яндекс Метрики (v1), действующими не считаются — баннер
 * показывается повторно, и счётчик не стартует до нового выбора.
 */

import { useSyncExternalStore } from 'react';

/**
 * Статус согласия.
 * - `unknown` — хранилище ещё не читали (серверный рендер и первый клиентский
 *   кадр). Это НЕ «выбор не сделан».
 * - `unset` — выбор не сделан.
 * - `accepted` / `declined` — выбор посетителя.
 */
export type CookieConsentStatus = 'unknown' | 'unset' | 'accepted' | 'declined';

const STORAGE_KEY = 'cookie_consent';
const LEGACY_STORAGE_KEY = 'cookie_consent_accepted';

/**
 * Версия текста баннера, под которым сделан выбор (стори 41.14).
 * v1 — формулировка «остальные — только с вашего согласия» без аналитики;
 * v2 — текст называет Яндекс Метрику. Повышать при каждой правке текста,
 * меняющей состав того, на что соглашается посетитель.
 */
export const CONSENT_VERSION = 2;

interface CookieConsentSnapshot {
  status: CookieConsentStatus;
  /** Баннер открыт принудительно из подвала. В localStorage не пишется. */
  isForced: boolean;
}

/** Снимок для серверного рендера: статус «ещё не читали хранилище». */
const SERVER_SNAPSHOT: CookieConsentSnapshot = Object.freeze({
  status: 'unknown',
  isForced: false,
});

let snapshot: CookieConsentSnapshot = SERVER_SNAPSHOT;
const listeners = new Set<() => void>();

/**
 * Элемент, из которого баннер открыли принудительно, — чтобы вернуть ему фокус
 * после закрытия. Хранится ВНЕ снимка: DOM-узел в рендере не участвует, и
 * попадание его в снимок означало бы лишние ре-рендеры потребителей.
 */
let forcedTrigger: HTMLElement | null = null;

/**
 * Снимок пересоздаётся ТОЛЬКО здесь. getSnapshot обязан возвращать стабильную
 * ссылку, иначе useSyncExternalStore уходит в бесконечный ре-рендер.
 *
 * Если ни одно поле не меняется, снимок остаётся прежним и подписчики не
 * уведомляются: повторный `reopen()` при уже открытом баннере или событие
 * `storage` без фактического изменения не должны давать лишний ре-рендер (AC4).
 */
function setSnapshot(next: Partial<CookieConsentSnapshot>): void {
  const status = next.status ?? snapshot.status;
  const isForced = next.isForced ?? snapshot.isForced;
  if (status === snapshot.status && isForced === snapshot.isForced) {
    return;
  }

  snapshot = { status, isForced };
  listeners.forEach(listener => listener());
}

/** Сериализованное значение выбора под текущей версией текста. */
function versionedValue(status: 'accepted' | 'declined'): string {
  return `${status}:v${CONSENT_VERSION}`;
}

/**
 * Распознаёт значение хранилища. Действующим считается только выбор под
 * текущей версией текста; устаревшие `accepted`/`declined` без версии и
 * всё прочее трактуются как «выбор не сделан» — баннер покажется повторно.
 */
function parseStatus(raw: string | null): CookieConsentStatus {
  if (raw === versionedValue('accepted')) {
    return 'accepted';
  }
  if (raw === versionedValue('declined')) {
    return 'declined';
  }
  return 'unset';
}

/**
 * Записывает выбор в хранилище. Сбой записи не считается фатальным:
 * статус остаётся в памяти до полной перезагрузки страницы (AC5).
 */
function persist(status: 'accepted' | 'declined'): void {
  if (typeof window === 'undefined') {
    return;
  }

  try {
    window.localStorage.setItem(STORAGE_KEY, versionedValue(status));
    // Старый ключ после успешной записи нового больше не нужен.
    window.localStorage.removeItem(LEGACY_STORAGE_KEY);
  } catch (error) {
    console.error('useCookieConsent: запись localStorage не удалась', error);
  }
}

/**
 * Читает актуальное состояние хранилища.
 *
 * Действующим считается только значение текущей версии. Legacy-ключ
 * `'1'` и неверсионные `accepted`/`declined` со стори 41.14 миграцией не
 * поднимаются: они записаны под текстом без Яндекс Метрики, поэтому
 * трактуются как «выбор не сделан» и приводят к повторному показу баннера.
 *
 * При сбое чтения возвращает `null` и пишет в лог — решение о запасном
 * источнике принимает вызывающая сторона.
 */
function readStorage(): CookieConsentStatus | null {
  try {
    return parseStatus(window.localStorage.getItem(STORAGE_KEY));
  } catch (error) {
    console.error('useCookieConsent: чтение localStorage не удалось', error);
    return null;
  }
}

/** Читает состояние из хранилища при первой подписке. */
function readFromStorage(): void {
  if (typeof window === 'undefined') {
    setSnapshot({ status: 'unset' });
    return;
  }

  setSnapshot({ status: readStorage() ?? 'unset', isForced: false });
}

/**
 * Согласие, данное в другой вкладке, применяется и здесь.
 *
 * Учитывается только `localStorage`: событие `storage` приходит и от
 * `sessionStorage`, где одноимённый ключ согласием не является. Событие с
 * `key === null` — это `localStorage.clear()` в другой вкладке; без его
 * обработки здесь остался бы устаревший статус и баннер больше не показался
 * бы. Обратно в хранилище обработчик ничего не пишет.
 *
 * Событие может устареть: пока оно ждало доставки, пользователь мог сделать
 * выбор в этой вкладке. Поэтому источник истины — текущее содержимое
 * хранилища, а `event.newValue` — лишь запасной вариант на случай сбоя чтения.
 *
 * Legacy-ключ по-прежнему слушается: во время выката вкладка со старым
 * бандлом пишет `cookie_consent_accepted='1'`. Согласием оно больше не
 * считается (записано под текстом без Яндекс Метрики), но событие валидно
 * будит перечитывание хранилища.
 */
function handleStorageEvent(event: StorageEvent): void {
  if (typeof window === 'undefined' || event.storageArea !== window.localStorage) {
    return;
  }

  const isFullClear = event.key === null;
  if (!isFullClear && event.key !== STORAGE_KEY && event.key !== LEGACY_STORAGE_KEY) {
    return;
  }

  // Событие без фактического изменения новый снимок не создаёт — это
  // гарантирует equality-guard в setSnapshot.
  setSnapshot({ status: readStorage() ?? fallbackFromEvent(event), isForced: false });
}

/**
 * Запасной источник статуса, когда чтение хранилища во время события упало.
 * Legacy-значение согласием не является — оно под текстом без Метрики.
 */
function fallbackFromEvent(event: StorageEvent): CookieConsentStatus {
  if (event.key === LEGACY_STORAGE_KEY) {
    return 'unset';
  }

  // key === null — это localStorage.clear() в другой вкладке.
  return event.key === null ? 'unset' : parseStatus(event.newValue);
}

/**
 * Подписка на стор. Хранилище читается лениво — при первой подписке,
 * а не в useEffect каждого потребителя.
 */
function subscribe(listener: () => void): () => void {
  listeners.add(listener);

  if (listeners.size === 1 && typeof window !== 'undefined') {
    window.addEventListener('storage', handleStorageEvent);
  }

  if (snapshot.status === 'unknown') {
    readFromStorage();
  }

  return () => {
    listeners.delete(listener);
    if (listeners.size === 0 && typeof window !== 'undefined') {
      window.removeEventListener('storage', handleStorageEvent);
    }
  };
}

function getSnapshot(): CookieConsentSnapshot {
  return snapshot;
}

function getServerSnapshot(): CookieConsentSnapshot {
  return SERVER_SNAPSHOT;
}

/** Зафиксировать согласие. */
function accept(): void {
  persist('accepted');
  setSnapshot({ status: 'accepted', isForced: false });
}

/** Зафиксировать отказ. */
function decline(): void {
  persist('declined');
  setSnapshot({ status: 'declined', isForced: false });
}

/**
 * Открыть баннер заново, не стирая сохранённый выбор.
 *
 * @param trigger элемент, инициировавший открытие. Баннер вернёт ему фокус,
 * когда закроется: иначе после выбора фокус остаётся на `body` и клавиатурный
 * пользователь теряет позицию в подвале (AC6).
 */
function reopen(trigger?: HTMLElement | null): void {
  forcedTrigger = trigger ?? null;
  setSnapshot({ isForced: true });
}

/**
 * Забирает элемент-инициатор и обнуляет его: фокус возвращается ровно один раз.
 * Внутренний контракт хука и баннера, а не публичный API страниц.
 */
export function consumeCookieConsentTrigger(): HTMLElement | null {
  const trigger = forcedTrigger;
  forcedTrigger = null;
  return trigger;
}

/**
 * Сброс модульного стора. ТОЛЬКО ДЛЯ ТЕСТОВ.
 *
 * Состояние стора переживает размонтирование компонентов, поэтому каждый
 * тестовый файл, использующий хук, обязан звать этот сброс в beforeEach —
 * иначе тесты начнут зависеть от порядка выполнения. Очистку самого
 * localStorage хелпер на себя не берёт: это ответственность теста.
 */
export function __resetCookieConsentStoreForTests(): void {
  snapshot = SERVER_SNAPSHOT;
  listeners.clear();
  forcedTrigger = null;
  if (typeof window !== 'undefined') {
    window.removeEventListener('storage', handleStorageEvent);
  }
}

export interface UseCookieConsentReturn {
  /** Текущий статус согласия. */
  status: CookieConsentStatus;
  /** Хранилище прочитано (статус отличен от `unknown`). */
  isLoaded: boolean;
  /** Баннер открыт принудительно кнопкой «Настройки cookie». */
  isForced: boolean;
  /** Баннер должен отображаться. */
  isBannerVisible: boolean;
  /** Зафиксировать согласие. */
  accept: () => void;
  /** Зафиксировать отказ. */
  decline: () => void;
  /**
   * Открыть баннер заново, не стирая сохранённый выбор. Переданный элемент
   * получит фокус обратно после закрытия баннера.
   */
  reopen: (trigger?: HTMLElement | null) => void;
}

export function useCookieConsent(): UseCookieConsentReturn {
  const state = useSyncExternalStore(subscribe, getSnapshot, getServerSnapshot);
  const isLoaded = state.status !== 'unknown';

  return {
    status: state.status,
    isLoaded,
    isForced: state.isForced,
    isBannerVisible: isLoaded && (state.status === 'unset' || state.isForced),
    accept,
    decline,
    reopen,
  };
}
