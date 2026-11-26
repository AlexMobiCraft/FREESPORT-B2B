/**
 * Управляемый мок IntersectionObserver для тестов счётчика показов баннеров.
 *
 * В happy-dom IntersectionObserver есть, но никогда не вызывает колбэк. Мок
 * запоминает наблюдаемые элементы и даёт тесту сообщить, какая доля элемента
 * видна: `setIntersection(element, 0.6)`.
 *
 * Подключение: `const io = installIntersectionObserverMock()` в `beforeEach`,
 * `vi.unstubAllGlobals()` в `afterEach`.
 */

import { vi } from 'vitest';

export class MockIntersectionObserver {
  static instances: MockIntersectionObserver[] = [];

  readonly callback: IntersectionObserverCallback;
  readonly options: IntersectionObserverInit | undefined;
  readonly elements = new Set<Element>();
  disconnected = false;

  constructor(callback: IntersectionObserverCallback, options?: IntersectionObserverInit) {
    this.callback = callback;
    this.options = options;
    MockIntersectionObserver.instances.push(this);
  }

  observe(element: Element): void {
    this.elements.add(element);
  }

  unobserve(element: Element): void {
    this.elements.delete(element);
  }

  disconnect(): void {
    this.elements.clear();
    this.disconnected = true;
  }

  takeRecords(): IntersectionObserverEntry[] {
    return [];
  }

  trigger(element: Element, ratio: number): void {
    const entry = {
      target: element,
      isIntersecting: ratio > 0,
      intersectionRatio: ratio,
    } as IntersectionObserverEntry;
    this.callback([entry], this as unknown as IntersectionObserver);
  }
}

export interface IntersectionObserverMockControls {
  /** Сообщает всем активным наблюдателям элемента видимую долю его площади */
  setIntersection: (element: Element, ratio: number) => void;
  /** Активные (не отключённые) наблюдатели элемента */
  observersOf: (element: Element) => MockIntersectionObserver[];
}

export function installIntersectionObserverMock(): IntersectionObserverMockControls {
  MockIntersectionObserver.instances = [];
  vi.stubGlobal('IntersectionObserver', MockIntersectionObserver);

  const observersOf = (element: Element) =>
    MockIntersectionObserver.instances.filter(
      observer => !observer.disconnected && observer.elements.has(element)
    );

  return {
    setIntersection: (element, ratio) => {
      for (const observer of observersOf(element)) observer.trigger(element, ratio);
    },
    observersOf,
  };
}

/** Подменяет document.visibilityState и рассылает visibilitychange */
export function setDocumentVisibility(state: DocumentVisibilityState): void {
  Object.defineProperty(document, 'visibilityState', {
    configurable: true,
    get: () => state,
  });
  document.dispatchEvent(new Event('visibilitychange'));
}

/** Возвращает document.visibilityState к значению окружения */
export function resetDocumentVisibility(): void {
  delete (document as unknown as Record<string, unknown>).visibilityState;
}
