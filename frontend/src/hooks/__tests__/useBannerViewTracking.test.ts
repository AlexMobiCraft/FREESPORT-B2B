/**
 * useBannerViewTracking — определение показа баннера для отчётности в ОРД.
 *
 * Показ: ≥ 50 % площади во вьюпорте непрерывно ≥ 1 с при видимой вкладке и
 * загруженной картинке именно текущего баннера; один раз на баннер за монтирование.
 */

import React from 'react';
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { renderHook, act } from '@testing-library/react';

import { useBannerViewTracking } from '../useBannerViewTracking';
import { trackBannerView } from '@/services/siteEvents';
import {
  installIntersectionObserverMock,
  resetDocumentVisibility,
  setDocumentVisibility,
  type IntersectionObserverMockControls,
} from '@/__mocks__/intersectionObserver';

vi.mock('@/services/siteEvents', () => ({
  trackBannerView: vi.fn(),
  trackBannerClick: vi.fn(),
}));

type Props = { element: Element | null; activeId: number | null; loadedId: number | null };

describe('useBannerViewTracking', () => {
  let io: IntersectionObserverMockControls;
  let element: HTMLDivElement;

  const renderTracking = (initial: Partial<Props> = {}, wrapper?: React.FC<{ children: React.ReactNode }>) =>
    renderHook(
      ({ element: el, activeId, loadedId }: Props) => useBannerViewTracking(el, activeId, loadedId),
      {
        initialProps: { element, activeId: 1, loadedId: 1, ...initial },
        wrapper,
      }
    );

  const show = (ratio = 0.6) => act(() => io.setIntersection(element, ratio));
  const wait = (ms: number) => act(() => vi.advanceTimersByTime(ms));

  beforeEach(() => {
    vi.useFakeTimers();
    io = installIntersectionObserverMock();
    element = document.createElement('div');
    vi.mocked(trackBannerView).mockClear();
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
    resetDocumentVisibility();
  });

  it('засчитывает показ через 1 с видимости ≥ 50 %', () => {
    renderTracking();

    show(0.5);
    wait(999);
    expect(trackBannerView).not.toHaveBeenCalled();

    wait(1);
    expect(trackBannerView).toHaveBeenCalledTimes(1);
    expect(trackBannerView).toHaveBeenCalledWith(1);
  });

  it('не засчитывает показ при видимости меньше 50 %', () => {
    renderTracking();

    show(0.49);
    wait(5000);

    expect(trackBannerView).not.toHaveBeenCalled();
  });

  it('не засчитывает 0,8 с видимости, а повторное появление запускает отсчёт заново', () => {
    renderTracking();

    show();
    wait(800);
    show(0);
    wait(2000);
    expect(trackBannerView).not.toHaveBeenCalled();

    show();
    wait(800);
    expect(trackBannerView).not.toHaveBeenCalled();
    wait(200);
    expect(trackBannerView).toHaveBeenCalledTimes(1);
  });

  it('не засчитывает показ на скрытой вкладке и возобновляет отсчёт при возврате', () => {
    renderTracking();

    show();
    wait(500);
    act(() => setDocumentVisibility('hidden'));
    wait(3000);
    expect(trackBannerView).not.toHaveBeenCalled();

    act(() => setDocumentVisibility('visible'));
    wait(999);
    expect(trackBannerView).not.toHaveBeenCalled();
    wait(1);
    expect(trackBannerView).toHaveBeenCalledWith(1);
  });

  it('не стартует, если вкладка скрыта с самого начала', () => {
    act(() => setDocumentVisibility('hidden'));
    renderTracking();

    show();
    wait(3000);

    expect(trackBannerView).not.toHaveBeenCalled();
  });

  it('не засчитывает показ, пока картинка не загрузилась', () => {
    const { rerender } = renderTracking({ loadedId: null });

    show();
    wait(3000);
    expect(trackBannerView).not.toHaveBeenCalled();

    rerender({ element, activeId: 1, loadedId: 1 });
    wait(1000);
    expect(trackBannerView).toHaveBeenCalledWith(1);
  });

  it('ошибка картинки (loadedId → null) останавливает отсчёт', () => {
    const { rerender } = renderTracking();

    show();
    wait(500);
    rerender({ element, activeId: 1, loadedId: null });
    wait(3000);

    expect(trackBannerView).not.toHaveBeenCalled();
  });

  it('смена баннера без нового срабатывания IO засчитывает показ новому баннеру', () => {
    const { rerender } = renderTracking();

    show();
    wait(1000);
    expect(trackBannerView).toHaveBeenLastCalledWith(1);

    // Автопрокрутка hero: тот же DOM-узел, IO молчит, картинка нового баннера загрузилась.
    rerender({ element, activeId: 2, loadedId: 2 });
    wait(999);
    expect(trackBannerView).toHaveBeenCalledTimes(1);
    wait(1);
    expect(trackBannerView).toHaveBeenCalledTimes(2);
    expect(trackBannerView).toHaveBeenLastCalledWith(2);
  });

  it('смена activeId до загрузки новой картинки — таймер не идёт', () => {
    const { rerender } = renderTracking();

    show();
    wait(500);
    // loadedId остался от прошлого баннера.
    rerender({ element, activeId: 2, loadedId: 1 });
    wait(3000);
    expect(trackBannerView).not.toHaveBeenCalled();

    rerender({ element, activeId: 2, loadedId: 2 });
    wait(1000);
    expect(trackBannerView).toHaveBeenCalledTimes(1);
    expect(trackBannerView).toHaveBeenCalledWith(2);
  });

  it('смена баннера до истечения 1 с перезапускает отсчёт', () => {
    const { rerender } = renderTracking();

    show();
    wait(700);
    rerender({ element, activeId: 2, loadedId: 2 });
    wait(700);
    expect(trackBannerView).not.toHaveBeenCalled();
    wait(300);
    expect(trackBannerView).toHaveBeenCalledWith(2);
    expect(trackBannerView).not.toHaveBeenCalledWith(1);
  });

  it('засчитывает баннер один раз за монтирование', () => {
    const { rerender } = renderTracking();

    show();
    wait(1000);
    show(0);
    show();
    wait(5000);
    rerender({ element, activeId: 2, loadedId: 2 });
    wait(1000);
    rerender({ element, activeId: 1, loadedId: 1 });
    wait(5000);

    expect(vi.mocked(trackBannerView).mock.calls).toEqual([[1], [2]]);
  });

  it('новое монтирование — новый показ', () => {
    const first = renderTracking();
    show();
    wait(1000);
    first.unmount();

    element = document.createElement('div');
    renderTracking();
    show();
    wait(1000);

    expect(trackBannerView).toHaveBeenCalledTimes(2);
  });

  it('устойчив к двойному mount в StrictMode', () => {
    renderTracking({}, ({ children }) => React.createElement(React.StrictMode, null, children));

    show();
    wait(5000);

    expect(trackBannerView).toHaveBeenCalledTimes(1);
  });

  it('размонтирование до 1 с отменяет показ', () => {
    const { unmount } = renderTracking();

    show();
    wait(500);
    unmount();
    wait(3000);

    expect(trackBannerView).not.toHaveBeenCalled();
  });

  it('без элемента ничего не наблюдает', () => {
    renderTracking({ element: null });

    expect(io.observersOf(element)).toHaveLength(0);
  });

  it('без IntersectionObserver в окружении — no-op', () => {
    vi.stubGlobal('IntersectionObserver', undefined);

    expect(() => renderTracking()).not.toThrow();
    wait(5000);

    expect(trackBannerView).not.toHaveBeenCalled();
  });
});
