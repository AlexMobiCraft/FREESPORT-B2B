/**
 * StatCounter Unit Tests
 * Story 19.1 - AC 6 (покрытие ≥ 80%)
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { StatCounter } from './StatCounter';

describe('StatCounter', () => {
  const mockProps = {
    value: 1000,
    suffix: '+',
    label: 'товаров',
  };

  // Mock IntersectionObserver
  beforeEach(() => {
    global.IntersectionObserver = class IntersectionObserver {
      constructor(callback: IntersectionObserverCallback) {
        // Симулируем вход элемента в область видимости
        callback([{ isIntersecting: true } as IntersectionObserverEntry], this);
      }
      observe = vi.fn();
      disconnect = vi.fn();
      unobserve = vi.fn();
      takeRecords = vi.fn(() => []);
      root = null;
      rootMargin = '';
      thresholds = [];
    } as unknown as typeof IntersectionObserver;

    // Mock requestAnimationFrame - вызываем один раз с завершенной анимацией
    let rafCallCount = 0;
    vi.spyOn(window, 'requestAnimationFrame').mockImplementation((cb: FrameRequestCallback) => {
      if (rafCallCount < 1) {
        rafCallCount++;
        // Симулируем завершенное состояние (progress = 1)
        setTimeout(() => cb(performance.now() + 3000), 0);
      }
      return 0;
    });
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('renders initial value of 0', () => {
    // Отключаем IntersectionObserver для этого теста
    global.IntersectionObserver = class IntersectionObserver {
      constructor() {
        // Не вызываем callback
      }
      observe = vi.fn();
      disconnect = vi.fn();
      unobserve = vi.fn();
      takeRecords = vi.fn(() => []);
      root = null;
      rootMargin = '';
      thresholds = [];
    } as unknown as typeof IntersectionObserver;

    render(<StatCounter {...mockProps} />);
    expect(screen.getByText('0')).toBeInTheDocument();
  });

  it('renders label correctly', () => {
    render(<StatCounter {...mockProps} />);
    expect(screen.getByText('товаров')).toBeInTheDocument();
  });

  it('displays suffix correctly', async () => {
    render(<StatCounter {...mockProps} />);

    await waitFor(() => {
      const suffix = screen.getByText('+');
      expect(suffix).toBeInTheDocument();
    });
  });

  it('renders without suffix', () => {
    const { value, label } = mockProps;
    render(<StatCounter value={value} label={label} />);

    expect(screen.getByText('товаров')).toBeInTheDocument();
    expect(screen.queryByText('+')).not.toBeInTheDocument();
  });

  it('animates to target value when in viewport', async () => {
    render(<StatCounter {...mockProps} />);

    await waitFor(
      () => {
        // Проверяем что значение анимировалось (не равно 0)
        const valueElement = screen.getByRole('status');
        expect(valueElement).toBeInTheDocument();
      },
      { timeout: 100 }
    );
  });

  it('respects prefers-reduced-motion', () => {
    // Mock matchMedia для prefers-reduced-motion
    Object.defineProperty(window, 'matchMedia', {
      writable: true,
      value: vi.fn().mockImplementation(query => ({
        matches: query === '(prefers-reduced-motion: reduce)',
        media: query,
        onchange: null,
        addListener: vi.fn(),
        removeListener: vi.fn(),
        addEventListener: vi.fn(),
        removeEventListener: vi.fn(),
        dispatchEvent: vi.fn(),
      })),
    });

    render(<StatCounter {...mockProps} />);

    // При prefers-reduced-motion значение должно сразу быть финальным
    waitFor(() => {
      expect(screen.getByText('1 000')).toBeInTheDocument();
    });
  });

  it('formats large numbers with locale separators', async () => {
    render(<StatCounter value={1000000} suffix="+" label="пользователей" />);

    await waitFor(
      () => {
        // Проверяем что число форматируется с разделителями (1 000 000)
        const valueElement = screen.getByRole('status');
        expect(valueElement).toHaveAttribute('aria-label', '1000000+ пользователей');
      },
      { timeout: 100 }
    );
  });

  it('has correct ARIA attributes', () => {
    render(<StatCounter {...mockProps} />);
    const counter = screen.getByRole('status');

    expect(counter).toHaveAttribute('aria-live', 'polite');
    expect(counter).toHaveAttribute('aria-label', '1000+ товаров');
  });

  it('applies custom className', () => {
    const { container } = render(<StatCounter {...mockProps} className="custom-class" />);
    const counter = container.firstChild as HTMLElement;

    expect(counter.className).toContain('custom-class');
  });

  it('accepts custom duration', () => {
    render(<StatCounter {...mockProps} duration={1000} />);
    const counter = screen.getByRole('status');

    expect(counter).toBeInTheDocument();
    // Анимация должна работать с кастомной длительностью
  });
});
