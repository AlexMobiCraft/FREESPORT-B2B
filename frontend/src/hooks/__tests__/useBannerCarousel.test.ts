/**
 * useBannerCarousel Hook Tests
 * Tests for the carousel hook with Embla Carousel integration
 *
 * @see _bmad-output/implementation-artifacts/32-3-frontend-carousel-logic.md
 */

import { renderHook, act, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { useBannerCarousel } from '../useBannerCarousel';
import type { UseBannerCarouselOptions } from '../useBannerCarousel';

// Hoisted mocks for vi.mock factory functions
const { mockEmblaApi, mockUseEmblaCarousel, mockAutoplay, mockAutoplayInstance } = vi.hoisted(() => {
  const mockAutoplayInstance = {
    name: 'autoplay',
    options: {},
    init: vi.fn(),
    destroy: vi.fn(),
    play: vi.fn(),
    stop: vi.fn(),
    reset: vi.fn(),
    isPlaying: vi.fn(() => false),
  };

  const mockEmblaApi = {
    scrollNext: vi.fn(),
    scrollPrev: vi.fn(),
    scrollTo: vi.fn(),
    canScrollNext: vi.fn(() => true),
    canScrollPrev: vi.fn(() => false),
    selectedScrollSnap: vi.fn(() => 0),
    scrollSnapList: vi.fn(() => [0, 1, 2]),
    on: vi.fn(),
    off: vi.fn(),
    destroy: vi.fn(),
    reInit: vi.fn(),
    plugins: vi.fn(() => ({ autoplay: mockAutoplayInstance })),
  };

  const mockUseEmblaCarousel = vi.fn(() => [vi.fn(), mockEmblaApi]);

  const mockAutoplay = vi.fn(() => mockAutoplayInstance);

  return { mockEmblaApi, mockUseEmblaCarousel, mockAutoplay, mockAutoplayInstance };
});

vi.mock('embla-carousel-react', () => ({
  default: mockUseEmblaCarousel,
}));

vi.mock('embla-carousel-autoplay', () => ({
  default: mockAutoplay,
}));

describe('useBannerCarousel', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    // Reset mock implementations
    mockEmblaApi.selectedScrollSnap.mockReturnValue(0);
    mockEmblaApi.scrollSnapList.mockReturnValue([0, 1, 2]);
    mockEmblaApi.canScrollNext.mockReturnValue(true);
    mockEmblaApi.canScrollPrev.mockReturnValue(false);
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  describe('Initial State', () => {
    it('should return emblaRef for container attachment', () => {
      const { result } = renderHook(() => useBannerCarousel());

      expect(result.current.emblaRef).toBeDefined();
      expect(typeof result.current.emblaRef).toBe('function');
    });

    it('should return selectedIndex initialized to 0', () => {
      const { result } = renderHook(() => useBannerCarousel());

      expect(result.current.selectedIndex).toBe(0);
    });

    it('should return scrollSnaps array', () => {
      const { result } = renderHook(() => useBannerCarousel());

      expect(Array.isArray(result.current.scrollSnaps)).toBe(true);
    });

    it('should return canScrollPrev and canScrollNext booleans', () => {
      const { result } = renderHook(() => useBannerCarousel());

      expect(typeof result.current.canScrollPrev).toBe('boolean');
      expect(typeof result.current.canScrollNext).toBe('boolean');
    });
  });

  describe('API Methods', () => {
    it('should expose scrollNext method', () => {
      const { result } = renderHook(() => useBannerCarousel());

      expect(typeof result.current.scrollNext).toBe('function');
    });

    it('should expose scrollPrev method', () => {
      const { result } = renderHook(() => useBannerCarousel());

      expect(typeof result.current.scrollPrev).toBe('function');
    });

    it('should expose onDotButtonClick method', () => {
      const { result } = renderHook(() => useBannerCarousel());

      expect(typeof result.current.onDotButtonClick).toBe('function');
    });

    it('should call emblaApi.scrollNext when scrollNext is invoked', () => {
      const { result } = renderHook(() => useBannerCarousel());

      act(() => {
        result.current.scrollNext();
      });

      expect(mockEmblaApi.scrollNext).toHaveBeenCalled();
    });

    it('should call emblaApi.scrollPrev when scrollPrev is invoked', () => {
      const { result } = renderHook(() => useBannerCarousel());

      act(() => {
        result.current.scrollPrev();
      });

      expect(mockEmblaApi.scrollPrev).toHaveBeenCalled();
    });

    it('should call emblaApi.scrollTo when onDotButtonClick is invoked with index', () => {
      const { result } = renderHook(() => useBannerCarousel());

      act(() => {
        result.current.onDotButtonClick(2);
      });

      expect(mockEmblaApi.scrollTo).toHaveBeenCalledWith(2);
    });

    it('should ignore NaN index in onDotButtonClick', () => {
      const { result } = renderHook(() => useBannerCarousel());

      act(() => {
        result.current.onDotButtonClick(NaN);
      });

      expect(mockEmblaApi.scrollTo).not.toHaveBeenCalled();
    });

    it('should ignore negative index in onDotButtonClick', () => {
      const { result } = renderHook(() => useBannerCarousel());

      act(() => {
        result.current.onDotButtonClick(-1);
      });

      expect(mockEmblaApi.scrollTo).not.toHaveBeenCalled();
    });

    it('should ignore Infinity index in scrollTo', () => {
      const { result } = renderHook(() => useBannerCarousel());

      act(() => {
        result.current.scrollTo(Infinity);
      });

      expect(mockEmblaApi.scrollTo).not.toHaveBeenCalled();
    });

    it('should ignore -Infinity index in scrollTo', () => {
      const { result } = renderHook(() => useBannerCarousel());

      act(() => {
        result.current.scrollTo(-Infinity);
      });

      expect(mockEmblaApi.scrollTo).not.toHaveBeenCalled();
    });

    it('should floor non-integer index in scrollTo', () => {
      const { result } = renderHook(() => useBannerCarousel());

      act(() => {
        result.current.scrollTo(1.7);
      });

      expect(mockEmblaApi.scrollTo).toHaveBeenCalledWith(1);
    });

    it('should floor non-integer index in onDotButtonClick', () => {
      const { result } = renderHook(() => useBannerCarousel());

      act(() => {
        result.current.onDotButtonClick(2.9);
      });

      expect(mockEmblaApi.scrollTo).toHaveBeenCalledWith(2);
    });

    it('should ignore out-of-range index in onDotButtonClick (index >= snapCount)', () => {
      // scrollSnapList returns [0, 1, 2] → valid indices are 0, 1, 2
      mockEmblaApi.scrollSnapList.mockReturnValue([0, 1, 2]);
      const { result } = renderHook(() => useBannerCarousel());

      act(() => {
        result.current.onDotButtonClick(3);
      });

      expect(mockEmblaApi.scrollTo).not.toHaveBeenCalled();
    });

    it('should ignore out-of-range index in scrollTo (index >= snapCount)', () => {
      mockEmblaApi.scrollSnapList.mockReturnValue([0, 1, 2]);
      const { result } = renderHook(() => useBannerCarousel());

      act(() => {
        result.current.scrollTo(3);
      });

      expect(mockEmblaApi.scrollTo).not.toHaveBeenCalled();
    });

    it('should ignore large out-of-range index in scrollTo', () => {
      mockEmblaApi.scrollSnapList.mockReturnValue([0, 1, 2]);
      const { result } = renderHook(() => useBannerCarousel());

      act(() => {
        result.current.scrollTo(100);
      });

      expect(mockEmblaApi.scrollTo).not.toHaveBeenCalled();
    });

    it('should accept max valid index in onDotButtonClick (snapCount - 1)', () => {
      mockEmblaApi.scrollSnapList.mockReturnValue([0, 1, 2]);
      const { result } = renderHook(() => useBannerCarousel());

      act(() => {
        result.current.onDotButtonClick(2);
      });

      expect(mockEmblaApi.scrollTo).toHaveBeenCalledWith(2);
    });

    it('should accept max valid index in scrollTo (snapCount - 1)', () => {
      mockEmblaApi.scrollSnapList.mockReturnValue([0, 1, 2]);
      const { result } = renderHook(() => useBannerCarousel());

      act(() => {
        result.current.scrollTo(2);
      });

      expect(mockEmblaApi.scrollTo).toHaveBeenCalledWith(2);
    });

    it('should ignore out-of-range floored index (2.9 floors to 2 which is valid, 3.1 floors to 3 which is out-of-range)', () => {
      mockEmblaApi.scrollSnapList.mockReturnValue([0, 1, 2]);
      const { result } = renderHook(() => useBannerCarousel());

      // 2.9 → floor(2.9) = 2, valid
      act(() => {
        result.current.scrollTo(2.9);
      });
      expect(mockEmblaApi.scrollTo).toHaveBeenCalledWith(2);

      mockEmblaApi.scrollTo.mockClear();

      // 3.1 → floor(3.1) = 3, out-of-range
      act(() => {
        result.current.scrollTo(3.1);
      });
      expect(mockEmblaApi.scrollTo).not.toHaveBeenCalled();
    });

    it('should handle empty scrollSnapList gracefully (no valid index)', () => {
      mockEmblaApi.scrollSnapList.mockReturnValue([]);
      const { result } = renderHook(() => useBannerCarousel());

      act(() => {
        result.current.scrollTo(0);
      });

      expect(mockEmblaApi.scrollTo).not.toHaveBeenCalled();
    });

    it('should expose scrollTo method', () => {
      const { result } = renderHook(() => useBannerCarousel());

      expect(typeof result.current.scrollTo).toBe('function');
    });

    it('should call emblaApi.scrollTo when scrollTo is invoked with index', () => {
      const { result } = renderHook(() => useBannerCarousel());

      act(() => {
        result.current.scrollTo(1);
      });

      expect(mockEmblaApi.scrollTo).toHaveBeenCalledWith(1);
    });
  });

  describe('Options Configuration', () => {
    it('should accept loop option', () => {
      const options: UseBannerCarouselOptions = { loop: true };
      const { result } = renderHook(() => useBannerCarousel(options));

      expect(result.current.emblaRef).toBeDefined();
    });

    it('should accept align option', () => {
      const options: UseBannerCarouselOptions = { align: 'center' };
      const { result } = renderHook(() => useBannerCarousel(options));

      expect(result.current.emblaRef).toBeDefined();
    });

    it('should accept speed option', () => {
      const options: UseBannerCarouselOptions = { speed: 5 };
      const { result } = renderHook(() => useBannerCarousel(options));

      expect(result.current.emblaRef).toBeDefined();
    });

    it('should accept autoplay option', () => {
      const options: UseBannerCarouselOptions = { autoplay: true };
      const { result } = renderHook(() => useBannerCarousel(options));

      expect(result.current.emblaRef).toBeDefined();
    });

    it('should accept autoplayDelay option', () => {
      const options: UseBannerCarouselOptions = {
        autoplay: true,
        autoplayDelay: 5000,
      };
      const { result } = renderHook(() => useBannerCarousel(options));

      expect(result.current.emblaRef).toBeDefined();
    });

    it('should accept stopOnInteraction option', () => {
      const options: UseBannerCarouselOptions = {
        autoplay: true,
        stopOnInteraction: false,
      };
      const { result } = renderHook(() => useBannerCarousel(options));

      expect(result.current.emblaRef).toBeDefined();
    });

    it('should accept autoScroll as alias for autoplay (AC3 compatibility)', () => {
      const options: UseBannerCarouselOptions = { autoScroll: true };
      const { result } = renderHook(() => useBannerCarousel(options));

      expect(result.current.emblaRef).toBeDefined();
    });
  });

  describe('Options Passed to Embla', () => {
    it('should pass loop, align, and dragFree options to useEmblaCarousel', () => {
      renderHook(() => useBannerCarousel({ loop: false, align: 'center' }));

      expect(mockUseEmblaCarousel).toHaveBeenCalledWith(
        expect.objectContaining({ loop: false, align: 'center', dragFree: false }),
        expect.any(Array)
      );
    });

    it('should pass speed option to useEmblaCarousel when provided', () => {
      renderHook(() => useBannerCarousel({ speed: 5 }));

      expect(mockUseEmblaCarousel).toHaveBeenCalledWith(
        expect.objectContaining({ speed: 5 }),
        expect.any(Array)
      );
    });

    it('should not include speed in options when not provided', () => {
      renderHook(() => useBannerCarousel({}));

      const lastCall = mockUseEmblaCarousel.mock.calls[mockUseEmblaCarousel.mock.calls.length - 1];
      expect(lastCall[0]).not.toHaveProperty('speed');
    });

    it('should call Autoplay with correct options when autoplay is enabled', () => {
      renderHook(() =>
        useBannerCarousel({
          autoplay: true,
          autoplayDelay: 3000,
          stopOnInteraction: false,
        })
      );

      expect(mockAutoplay).toHaveBeenCalledWith(
        expect.objectContaining({
          delay: 3000,
          stopOnInteraction: false,
        })
      );
    });

    it('should not call Autoplay when autoplay is disabled', () => {
      mockAutoplay.mockClear();
      renderHook(() => useBannerCarousel({ autoplay: false }));

      expect(mockAutoplay).not.toHaveBeenCalled();
    });

    it('should enable Autoplay when autoScroll is true (alias)', () => {
      mockAutoplay.mockClear();
      renderHook(() => useBannerCarousel({ autoScroll: true }));

      expect(mockAutoplay).toHaveBeenCalled();
    });

    it('should pass stopOnMouseEnter option to Autoplay', () => {
      mockAutoplay.mockClear();
      renderHook(() =>
        useBannerCarousel({
          autoplay: true,
          stopOnMouseEnter: false,
        })
      );

      expect(mockAutoplay).toHaveBeenCalledWith(
        expect.objectContaining({
          stopOnMouseEnter: false,
        })
      );
    });

    it('should default stopOnMouseEnter to true', () => {
      mockAutoplay.mockClear();
      renderHook(() => useBannerCarousel({ autoplay: true }));

      expect(mockAutoplay).toHaveBeenCalledWith(
        expect.objectContaining({
          stopOnMouseEnter: true,
        })
      );
    });
  });

  describe('Event Listeners', () => {
    it('should register select and reInit event listeners', async () => {
      renderHook(() => useBannerCarousel());

      await waitFor(() => {
        const onCalls = mockEmblaApi.on.mock.calls;
        const eventNames = onCalls.map(call => call[0]);

        expect(eventNames).toContain('select');
        expect(eventNames).toContain('reInit');
      });
    });

    it('should register exactly 2 event handlers (select + reInit)', async () => {
      renderHook(() => useBannerCarousel());

      await waitFor(() => {
        // onSelect for 'select', onReInit for 'reInit' (merged onInit+onSelect)
        expect(mockEmblaApi.on.mock.calls.length).toBe(2);
      });
    });

    it('should sync full nav-state via direct onReInit call on mount', async () => {
      // Setup: mock returns specific values
      mockEmblaApi.selectedScrollSnap.mockReturnValue(2);
      mockEmblaApi.canScrollPrev.mockReturnValue(true);
      mockEmblaApi.canScrollNext.mockReturnValue(false);
      mockEmblaApi.scrollSnapList.mockReturnValue([0, 1, 2, 3, 4]);

      const { result } = renderHook(() => useBannerCarousel());

      // Nav state should be synced from direct onReInit call
      await waitFor(() => {
        expect(result.current.selectedIndex).toBe(2);
        expect(result.current.canScrollPrev).toBe(true);
        expect(result.current.canScrollNext).toBe(false);
        expect(result.current.scrollSnaps).toEqual([0, 1, 2, 3, 4]);
      });
    });
  });

  describe('State Reactivity', () => {
    it('should update selectedIndex when select event fires', async () => {
      const { result } = renderHook(() => useBannerCarousel());

      // Find the select handler
      await waitFor(() => {
        expect(mockEmblaApi.on).toHaveBeenCalled();
      });

      const selectCall = mockEmblaApi.on.mock.calls.find(call => call[0] === 'select');
      expect(selectCall).toBeDefined();

      // Simulate select event with new index
      mockEmblaApi.selectedScrollSnap.mockReturnValue(2);

      act(() => {
        selectCall![1](mockEmblaApi);
      });

      expect(result.current.selectedIndex).toBe(2);
    });

    it('should update canScrollPrev/canScrollNext when select event fires', async () => {
      const { result } = renderHook(() => useBannerCarousel());

      await waitFor(() => {
        expect(mockEmblaApi.on).toHaveBeenCalled();
      });

      const selectCall = mockEmblaApi.on.mock.calls.find(call => call[0] === 'select');

      // Simulate state change
      mockEmblaApi.canScrollPrev.mockReturnValue(true);
      mockEmblaApi.canScrollNext.mockReturnValue(false);

      act(() => {
        selectCall![1](mockEmblaApi);
      });

      expect(result.current.canScrollPrev).toBe(true);
      expect(result.current.canScrollNext).toBe(false);
    });

    it('should update scrollSnaps and nav-state when reInit event fires (merged handler)', async () => {
      const { result } = renderHook(() => useBannerCarousel());

      await waitFor(() => {
        expect(mockEmblaApi.on).toHaveBeenCalled();
      });

      // Find the single reInit handler (onReInit = merged onInit + onSelect)
      const reInitCall = mockEmblaApi.on.mock.calls.find(call => call[0] === 'reInit');
      expect(reInitCall).toBeDefined();

      // Simulate reInit with new snaps and nav state
      mockEmblaApi.scrollSnapList.mockReturnValue([0, 1]);
      mockEmblaApi.selectedScrollSnap.mockReturnValue(1);
      mockEmblaApi.canScrollPrev.mockReturnValue(true);

      act(() => {
        reInitCall![1](mockEmblaApi);
      });

      expect(result.current.scrollSnaps).toEqual([0, 1]);
      expect(result.current.selectedIndex).toBe(1);
      expect(result.current.canScrollPrev).toBe(true);
    });
  });

  describe('Options Stability (Memoization)', () => {
    it('should maintain referential stability of emblaOptions between renders with same values', () => {
      const options: UseBannerCarouselOptions = {
        loop: true,
        align: 'center',
        autoplay: true,
        autoplayDelay: 5000,
      };

      const { rerender } = renderHook(({ opts }) => useBannerCarousel(opts), {
        initialProps: { opts: options },
      });

      const initialCallCount = mockUseEmblaCarousel.mock.calls.length;

      // Rerender with same option values (but new object reference)
      rerender({ opts: { ...options } });

      // useEmblaCarousel should be called again, but with memoized options
      const calls = mockUseEmblaCarousel.mock.calls;
      const firstOptions = calls[initialCallCount - 1][0];
      const secondOptions = calls[calls.length - 1][0];

      // Options should be REFERENTIALLY equal due to useMemo (toBe checks identity)
      expect(firstOptions).toBe(secondOptions);
    });

    it('should maintain referential stability of plugins array between renders with same autoplay config', () => {
      const { rerender } = renderHook(({ autoplay }) => useBannerCarousel({ autoplay }), {
        initialProps: { autoplay: true },
      });

      const callsBefore = mockUseEmblaCarousel.mock.calls.length;

      // Rerender with same autoplay value
      rerender({ autoplay: true });

      const callsAfter = mockUseEmblaCarousel.mock.calls.length;

      // Plugins array should be REFERENTIALLY stable (toBe checks identity)
      const pluginsBefore = mockUseEmblaCarousel.mock.calls[callsBefore - 1][1];
      const pluginsAfter = mockUseEmblaCarousel.mock.calls[callsAfter - 1][1];

      expect(pluginsBefore).toBe(pluginsAfter);
    });

    it('should reinitialize when autoplay changes from false to true', () => {
      mockAutoplay.mockClear();

      const { rerender } = renderHook(({ autoplay }) => useBannerCarousel({ autoplay }), {
        initialProps: { autoplay: false },
      });

      expect(mockAutoplay).not.toHaveBeenCalled();

      rerender({ autoplay: true });

      expect(mockAutoplay).toHaveBeenCalled();
    });

    it('should maintain referential stability of empty plugins array when autoplay=false', () => {
      const { rerender } = renderHook(({ delay }) => useBannerCarousel({ autoplay: false, autoplayDelay: delay }), {
        initialProps: { delay: 4000 },
      });

      const callsBefore = mockUseEmblaCarousel.mock.calls.length;

      // Rerender with different delay (should not affect empty plugins)
      rerender({ delay: 5000 });

      const callsAfter = mockUseEmblaCarousel.mock.calls.length;

      // Empty plugins array should be REFERENTIALLY stable (same constant)
      const pluginsBefore = mockUseEmblaCarousel.mock.calls[callsBefore - 1][1];
      const pluginsAfter = mockUseEmblaCarousel.mock.calls[callsAfter - 1][1];

      expect(pluginsBefore).toBe(pluginsAfter);
      expect(pluginsBefore).toHaveLength(0);
    });
  });

  describe('Touch/Swipe Behavior (AC2)', () => {
    it('should explicitly set dragFree: false for 1:1 finger tracking (AC2)', () => {
      renderHook(() => useBannerCarousel({}));

      const lastCall = mockUseEmblaCarousel.mock.calls[mockUseEmblaCarousel.mock.calls.length - 1];
      const emblaOptions = lastCall[0];

      // dragFree should be explicitly false (not relying on Embla default)
      expect(emblaOptions.dragFree).toBe(false);
    });

    /**
     * Pause-on-hover and pause-on-interaction tests consolidated into
     * "AC3 Behavioral Contract: Auto Cycle and Pause" section
     * to maintain a single source of truth for AC3 contract verification.
     */
  });

  describe('Behavioral Contract Tests (Mock-based)', () => {
    /**
     * These tests verify the behavioral contract of the hook using mocked Embla/Autoplay.
     * They validate API coordination, state synchronization, and configuration passing.
     *
     * NOTE: These are NOT browser-level integration tests. True integration tests
     * (swipe gestures, touch events, visual scroll) require E2E tools like Playwright
     * or Cypress with a real browser engine.
     *
     * JSDOM limitations: no layout engine, getBoundingClientRect returns zeros,
     * no IntersectionObserver, no real touch/pointer events.
     *
     * TODO [DEFERRED → Epic 32 E2E story]: Add Playwright E2E tests for touch/swipe
     * verification (AC2) and autoplay pause on hover/touch (AC3).
     * Scope: requires real browser engine; out of scope for hook unit tests.
     */

    it('should coordinate multiple API calls correctly', () => {
      const { result } = renderHook(() => useBannerCarousel({ loop: true }));

      // Multiple sequential API calls should work without errors
      act(() => {
        result.current.scrollNext();
        result.current.scrollPrev();
        result.current.scrollTo(1);
        result.current.onDotButtonClick(2);
      });

      // All methods should have been invoked on the API
      expect(mockEmblaApi.scrollNext).toHaveBeenCalledTimes(1);
      expect(mockEmblaApi.scrollPrev).toHaveBeenCalledTimes(1);
      expect(mockEmblaApi.scrollTo).toHaveBeenCalledTimes(2); // scrollTo + onDotButtonClick
    });

    it('should handle rapid state changes without losing sync', async () => {
      const { result } = renderHook(() => useBannerCarousel());

      await waitFor(() => {
        expect(mockEmblaApi.on).toHaveBeenCalled();
      });

      const selectHandler = mockEmblaApi.on.mock.calls.find(c => c[0] === 'select')![1];

      // Simulate rapid state changes
      act(() => {
        mockEmblaApi.selectedScrollSnap.mockReturnValue(1);
        selectHandler(mockEmblaApi);
        mockEmblaApi.selectedScrollSnap.mockReturnValue(2);
        selectHandler(mockEmblaApi);
        mockEmblaApi.selectedScrollSnap.mockReturnValue(0);
        selectHandler(mockEmblaApi);
      });

      // Final state should match last update
      expect(result.current.selectedIndex).toBe(0);
    });

    it('should pass complete autoplay configuration to plugin', () => {
      mockAutoplay.mockClear();

      renderHook(() =>
        useBannerCarousel({
          autoplay: true,
          autoplayDelay: 3000,
          stopOnInteraction: false,
          stopOnMouseEnter: true,
        })
      );

      // Verify all autoplay options are passed together
      expect(mockAutoplay).toHaveBeenCalledWith({
        delay: 3000,
        stopOnInteraction: false,
        stopOnMouseEnter: true,
      });
    });

    it('should pass complete Embla options to useEmblaCarousel', () => {
      renderHook(() =>
        useBannerCarousel({
          loop: false,
          align: 'center',
          speed: 15,
        })
      );

      const lastCall = mockUseEmblaCarousel.mock.calls[mockUseEmblaCarousel.mock.calls.length - 1];

      expect(lastCall[0]).toEqual({
        loop: false,
        align: 'center',
        dragFree: false,
        speed: 15,
      });
    });

    it('should cleanup event listeners on unmount', async () => {
      const { unmount } = renderHook(() => useBannerCarousel());

      await waitFor(() => {
        expect(mockEmblaApi.on).toHaveBeenCalled();
      });

      // 2 listeners: select (onSelect), reInit (onReInit)
      const onCallCount = mockEmblaApi.on.mock.calls.length;
      expect(onCallCount).toBe(2);

      unmount();

      // All registered listeners should be unregistered
      expect(mockEmblaApi.off.mock.calls.length).toBe(onCallCount);
    });

    it('should cleanup with correct event names and handler references', async () => {
      const { unmount } = renderHook(() => useBannerCarousel());

      await waitFor(() => {
        expect(mockEmblaApi.on).toHaveBeenCalled();
      });

      // Capture registered handlers
      const onCalls = mockEmblaApi.on.mock.calls;
      const registeredHandlers = onCalls.map(call => ({ event: call[0], handler: call[1] }));

      unmount();

      // Verify each handler is unregistered with same event name and handler reference
      const offCalls = mockEmblaApi.off.mock.calls;
      registeredHandlers.forEach(({ event, handler }) => {
        const matchingOff = offCalls.find(
          call => call[0] === event && call[1] === handler
        );
        expect(matchingOff).toBeDefined();
      });
    });

    it('should unregister single reInit handler (onReInit) on unmount', async () => {
      const { unmount } = renderHook(() => useBannerCarousel());

      await waitFor(() => {
        expect(mockEmblaApi.on).toHaveBeenCalled();
      });

      const reInitOnCalls = mockEmblaApi.on.mock.calls.filter(c => c[0] === 'reInit');
      expect(reInitOnCalls.length).toBe(1);

      unmount();

      const reInitOffCalls = mockEmblaApi.off.mock.calls.filter(c => c[0] === 'reInit');
      expect(reInitOffCalls.length).toBe(1);
      // Handler reference should match
      expect(reInitOffCalls[0][1]).toBe(reInitOnCalls[0][1]);
    });

    it('should unregister select handler on unmount', async () => {
      const { unmount } = renderHook(() => useBannerCarousel());

      await waitFor(() => {
        expect(mockEmblaApi.on).toHaveBeenCalled();
      });

      const selectOnCall = mockEmblaApi.on.mock.calls.find(c => c[0] === 'select');
      expect(selectOnCall).toBeDefined();

      unmount();

      const selectOffCall = mockEmblaApi.off.mock.calls.find(c => c[0] === 'select');
      expect(selectOffCall).toBeDefined();
      // Handler reference should match
      expect(selectOffCall![1]).toBe(selectOnCall![1]);
    });
  });

  describe('AC3 Behavioral Contract: Auto Cycle and Pause', () => {
    /**
     * AC3: Given autoScroll: true or defined interval, carousel cycles automatically
     * and pauses on user interaction (hover or touch) if configured.
     *
     * These tests verify the behavioral contract through plugin configuration.
     * Actual pause/resume behavior depends on Embla Autoplay plugin implementation.
     */

    it('should configure auto-cycle with default 4000ms delay when autoplay=true', () => {
      mockAutoplay.mockClear();
      renderHook(() => useBannerCarousel({ autoplay: true }));

      expect(mockAutoplay).toHaveBeenCalledWith(
        expect.objectContaining({ delay: 4000 })
      );
    });

    it('should configure auto-cycle with custom delay', () => {
      mockAutoplay.mockClear();
      renderHook(() => useBannerCarousel({ autoplay: true, autoplayDelay: 6000 }));

      expect(mockAutoplay).toHaveBeenCalledWith(
        expect.objectContaining({ delay: 6000 })
      );
    });

    it('should enable pause on hover by default (stopOnMouseEnter=true)', () => {
      mockAutoplay.mockClear();
      renderHook(() => useBannerCarousel({ autoplay: true }));

      expect(mockAutoplay).toHaveBeenCalledWith(
        expect.objectContaining({ stopOnMouseEnter: true })
      );
    });

    it('should enable pause on touch/interaction by default (stopOnInteraction=true)', () => {
      mockAutoplay.mockClear();
      renderHook(() => useBannerCarousel({ autoplay: true }));

      expect(mockAutoplay).toHaveBeenCalledWith(
        expect.objectContaining({ stopOnInteraction: true })
      );
    });

    it('should allow continuous auto-cycle without pause on hover', () => {
      mockAutoplay.mockClear();
      renderHook(() =>
        useBannerCarousel({
          autoplay: true,
          stopOnMouseEnter: false,
        })
      );

      expect(mockAutoplay).toHaveBeenCalledWith(
        expect.objectContaining({ stopOnMouseEnter: false })
      );
    });

    it('should allow continuous auto-cycle without pause on interaction', () => {
      mockAutoplay.mockClear();
      renderHook(() =>
        useBannerCarousel({
          autoplay: true,
          stopOnInteraction: false,
        })
      );

      expect(mockAutoplay).toHaveBeenCalledWith(
        expect.objectContaining({ stopOnInteraction: false })
      );
    });

    it('should pass complete pause configuration to Autoplay plugin', () => {
      mockAutoplay.mockClear();
      renderHook(() =>
        useBannerCarousel({
          autoplay: true,
          autoplayDelay: 3000,
          stopOnInteraction: true,
          stopOnMouseEnter: true,
        })
      );

      // Verify Autoplay receives all AC3 relevant options
      expect(mockAutoplay).toHaveBeenCalledWith({
        delay: 3000,
        stopOnInteraction: true,
        stopOnMouseEnter: true,
      });
    });

    it('should maintain stable autoplay plugin instance on re-render with same options', () => {
      mockAutoplay.mockClear();

      const { rerender } = renderHook(
        ({ autoplay, delay }) => useBannerCarousel({ autoplay, autoplayDelay: delay }),
        { initialProps: { autoplay: true, delay: 5000 } }
      );

      const initialAutoplayCallCount = mockAutoplay.mock.calls.length;

      // Re-render with same values
      rerender({ autoplay: true, delay: 5000 });

      // Autoplay should NOT be called again (stable instance via useMemo)
      expect(mockAutoplay.mock.calls.length).toBe(initialAutoplayCallCount);
    });

    it('should recreate autoplay plugin only when options change', () => {
      mockAutoplay.mockClear();

      const { rerender } = renderHook(
        ({ delay }) => useBannerCarousel({ autoplay: true, autoplayDelay: delay }),
        { initialProps: { delay: 4000 } }
      );

      const initialCallCount = mockAutoplay.mock.calls.length;

      // Change delay - should recreate plugin
      rerender({ delay: 6000 });

      expect(mockAutoplay.mock.calls.length).toBe(initialCallCount + 1);
      expect(mockAutoplay).toHaveBeenLastCalledWith(
        expect.objectContaining({ delay: 6000 })
      );
    });
  });

  describe('Autoplay Activation Logic (AC3)', () => {
    it('should enable autoplay when autoplayDelay is provided without explicit autoplay=true', () => {
      mockAutoplay.mockClear();
      renderHook(() => useBannerCarousel({ autoplayDelay: 5000 }));

      // AC3: "defined interval" should activate autoplay
      expect(mockAutoplay).toHaveBeenCalledWith(
        expect.objectContaining({ delay: 5000 })
      );
    });

    it('should NOT enable autoplay when neither autoplay nor autoplayDelay is provided', () => {
      mockAutoplay.mockClear();
      renderHook(() => useBannerCarousel({}));

      expect(mockAutoplay).not.toHaveBeenCalled();
    });

    it('should respect explicit autoplay=false even with autoplayDelay provided', () => {
      mockAutoplay.mockClear();
      renderHook(() => useBannerCarousel({ autoplay: false, autoplayDelay: 5000 }));

      // Explicit false should take precedence
      expect(mockAutoplay).not.toHaveBeenCalled();
    });

    it('should respect explicit autoScroll=false even with autoplayDelay provided', () => {
      mockAutoplay.mockClear();
      renderHook(() => useBannerCarousel({ autoScroll: false, autoplayDelay: 5000 }));

      // Explicit false should take precedence
      expect(mockAutoplay).not.toHaveBeenCalled();
    });

    it('should prioritize autoScroll over autoplay when both provided', () => {
      mockAutoplay.mockClear();
      renderHook(() => useBannerCarousel({ autoScroll: true, autoplay: false }));

      // autoScroll takes precedence
      expect(mockAutoplay).toHaveBeenCalled();
    });

    it('should prioritize autoScroll=false over autoplay=true when both provided', () => {
      mockAutoplay.mockClear();
      renderHook(() => useBannerCarousel({ autoScroll: false, autoplay: true }));

      // autoScroll takes precedence
      expect(mockAutoplay).not.toHaveBeenCalled();
    });
  });

  describe('Runtime Validation', () => {
    it('should ignore invalid speed (NaN) and use default', () => {
      renderHook(() => useBannerCarousel({ speed: NaN }));

      const lastCall = mockUseEmblaCarousel.mock.calls[mockUseEmblaCarousel.mock.calls.length - 1];
      // NaN should be filtered out
      expect(lastCall[0]).not.toHaveProperty('speed');
    });

    it('should ignore invalid speed (<=0) and use default', () => {
      renderHook(() => useBannerCarousel({ speed: 0 }));

      const lastCall = mockUseEmblaCarousel.mock.calls[mockUseEmblaCarousel.mock.calls.length - 1];
      expect(lastCall[0]).not.toHaveProperty('speed');
    });

    it('should ignore negative speed and use default', () => {
      renderHook(() => useBannerCarousel({ speed: -5 }));

      const lastCall = mockUseEmblaCarousel.mock.calls[mockUseEmblaCarousel.mock.calls.length - 1];
      expect(lastCall[0]).not.toHaveProperty('speed');
    });

    it('should ignore invalid autoplayDelay (NaN) and use default', () => {
      mockAutoplay.mockClear();
      renderHook(() => useBannerCarousel({ autoplay: true, autoplayDelay: NaN }));

      expect(mockAutoplay).toHaveBeenCalledWith(
        expect.objectContaining({ delay: 4000 }) // default
      );
    });

    it('should ignore invalid autoplayDelay (<=0) and use default', () => {
      mockAutoplay.mockClear();
      renderHook(() => useBannerCarousel({ autoplay: true, autoplayDelay: 0 }));

      expect(mockAutoplay).toHaveBeenCalledWith(
        expect.objectContaining({ delay: 4000 }) // default
      );
    });

    it('should ignore negative autoplayDelay and use default', () => {
      mockAutoplay.mockClear();
      renderHook(() => useBannerCarousel({ autoplay: true, autoplayDelay: -1000 }));

      expect(mockAutoplay).toHaveBeenCalledWith(
        expect.objectContaining({ delay: 4000 }) // default
      );
    });

    it('should accept valid positive speed', () => {
      renderHook(() => useBannerCarousel({ speed: 15 }));

      const lastCall = mockUseEmblaCarousel.mock.calls[mockUseEmblaCarousel.mock.calls.length - 1];
      expect(lastCall[0]).toHaveProperty('speed', 15);
    });

    it('should accept valid positive autoplayDelay', () => {
      mockAutoplay.mockClear();
      renderHook(() => useBannerCarousel({ autoplay: true, autoplayDelay: 3000 }));

      expect(mockAutoplay).toHaveBeenCalledWith(
        expect.objectContaining({ delay: 3000 })
      );
    });

    it('should ignore Infinity speed and exclude from options', () => {
      renderHook(() => useBannerCarousel({ speed: Infinity }));

      const lastCall = mockUseEmblaCarousel.mock.calls[mockUseEmblaCarousel.mock.calls.length - 1];
      expect(lastCall[0]).not.toHaveProperty('speed');
    });

    it('should ignore -Infinity speed and exclude from options', () => {
      renderHook(() => useBannerCarousel({ speed: -Infinity }));

      const lastCall = mockUseEmblaCarousel.mock.calls[mockUseEmblaCarousel.mock.calls.length - 1];
      expect(lastCall[0]).not.toHaveProperty('speed');
    });

    it('should ignore Infinity autoplayDelay and use default', () => {
      mockAutoplay.mockClear();
      renderHook(() => useBannerCarousel({ autoplay: true, autoplayDelay: Infinity }));

      expect(mockAutoplay).toHaveBeenCalledWith(
        expect.objectContaining({ delay: 4000 })
      );
    });
  });

  describe('Cleanup: Explicit off() Verification', () => {
    it('should call emblaApi.off for select/onSelect and reInit/onReInit on unmount', async () => {
      const { unmount } = renderHook(() => useBannerCarousel());

      await waitFor(() => {
        expect(mockEmblaApi.on).toHaveBeenCalled();
      });

      unmount();

      // Verify exact off() calls matching the 2 subscriptions
      const offCalls = mockEmblaApi.off.mock.calls.map(c => c[0]);
      expect(offCalls.filter(e => e === 'reInit').length).toBe(1);
      expect(offCalls.filter(e => e === 'select').length).toBe(1);
      expect(offCalls.length).toBe(2);
    });
  });

  describe('AC3 Behavioral: Autoplay Plugin Flow', () => {
    it('should pass the autoplay plugin instance to useEmblaCarousel in plugins array', () => {
      mockAutoplay.mockClear();
      const mockPlugin = { name: 'autoplay', init: vi.fn(), destroy: vi.fn() };
      mockAutoplay.mockReturnValueOnce(mockPlugin);

      renderHook(() => useBannerCarousel({ autoplay: true }));

      const lastCall = mockUseEmblaCarousel.mock.calls[mockUseEmblaCarousel.mock.calls.length - 1];
      expect(lastCall[1]).toContain(mockPlugin);
    });

    it('should pass empty plugins array when autoplay is disabled', () => {
      mockAutoplay.mockClear();

      renderHook(() => useBannerCarousel({ autoplay: false }));

      const lastCall = mockUseEmblaCarousel.mock.calls[mockUseEmblaCarousel.mock.calls.length - 1];
      expect(lastCall[1]).toEqual([]);
    });

    it('should transition plugins from active to empty when autoplay is disabled', () => {
      mockAutoplay.mockClear();

      const { rerender } = renderHook(
        ({ autoplay }) => useBannerCarousel({ autoplay }),
        { initialProps: { autoplay: true } }
      );

      // Verify plugin is active
      let lastCall = mockUseEmblaCarousel.mock.calls[mockUseEmblaCarousel.mock.calls.length - 1];
      expect(lastCall[1].length).toBe(1);

      // Disable autoplay
      rerender({ autoplay: false });

      lastCall = mockUseEmblaCarousel.mock.calls[mockUseEmblaCarousel.mock.calls.length - 1];
      expect(lastCall[1]).toEqual([]);
    });

    it('should transition plugins from empty to active when autoplay is enabled', () => {
      mockAutoplay.mockClear();

      const { rerender } = renderHook(
        ({ autoplay }) => useBannerCarousel({ autoplay }),
        { initialProps: { autoplay: false } }
      );

      // Verify plugins empty
      let lastCall = mockUseEmblaCarousel.mock.calls[mockUseEmblaCarousel.mock.calls.length - 1];
      expect(lastCall[1]).toEqual([]);

      // Enable autoplay
      rerender({ autoplay: true });

      lastCall = mockUseEmblaCarousel.mock.calls[mockUseEmblaCarousel.mock.calls.length - 1];
      expect(lastCall[1].length).toBe(1);
    });
  });

  describe('Type Safety', () => {
    it('should return correctly typed UseBannerCarouselReturn object with all required properties', () => {
      const { result } = renderHook(() => useBannerCarousel());

      // Verify all properties exist and have correct runtime types
      expect(result.current.emblaRef).toBeDefined();
      expect(typeof result.current.emblaRef).toBe('function');

      expect(typeof result.current.selectedIndex).toBe('number');
      expect(result.current.selectedIndex).toBeGreaterThanOrEqual(0);

      expect(Array.isArray(result.current.scrollSnaps)).toBe(true);

      expect(typeof result.current.canScrollPrev).toBe('boolean');
      expect(typeof result.current.canScrollNext).toBe('boolean');

      expect(typeof result.current.scrollNext).toBe('function');
      expect(typeof result.current.scrollPrev).toBe('function');
      expect(typeof result.current.onDotButtonClick).toBe('function');
      expect(typeof result.current.scrollTo).toBe('function');
    });

    it('should have all 9 properties in the return object', () => {
      const { result } = renderHook(() => useBannerCarousel());

      const keys = Object.keys(result.current);
      expect(keys).toContain('emblaRef');
      expect(keys).toContain('selectedIndex');
      expect(keys).toContain('scrollSnaps');
      expect(keys).toContain('canScrollPrev');
      expect(keys).toContain('canScrollNext');
      expect(keys).toContain('scrollNext');
      expect(keys).toContain('scrollPrev');
      expect(keys).toContain('onDotButtonClick');
      expect(keys).toContain('scrollTo');
      expect(keys).toHaveLength(9);
    });
  });

  describe('Autoplay Error Handling (AC1)', () => {
    it('should not throw when autoplay plugin is unavailable', async () => {
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      mockEmblaApi.plugins.mockReturnValueOnce({} as any);
      
      expect(() => {
        renderHook(() => useBannerCarousel({ autoplay: true }));
      }).not.toThrow();
    });

    it('should not throw when plugins() throws an error', async () => {
      mockEmblaApi.plugins.mockImplementationOnce(() => {
        throw new Error('Plugin access failed');
      });

      expect(() => {
        renderHook(() => useBannerCarousel({ autoplay: true }));
      }).not.toThrow();
    });

    it('should not throw when plugins() returns null', async () => {
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      mockEmblaApi.plugins.mockReturnValueOnce(null as any);

      expect(() => {
        renderHook(() => useBannerCarousel({ autoplay: true }));
      }).not.toThrow();
    });

    it('should not throw when autoplay plugin is not an object', async () => {
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      mockEmblaApi.plugins.mockReturnValueOnce({ autoplay: 'invalid' } as any);

      expect(() => {
        renderHook(() => useBannerCarousel({ autoplay: true }));
      }).not.toThrow();
    });

    it('should not call play() when plugin is unavailable', async () => {
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      mockEmblaApi.plugins.mockReturnValueOnce({} as any);
      mockAutoplayInstance.play.mockClear();

      renderHook(() => useBannerCarousel({ autoplay: true }));

      await waitFor(() => {
        expect(mockAutoplayInstance.play).not.toHaveBeenCalled();
      });
    });
  });

  describe('Autoplay Method Validation (AC10)', () => {
    it('should validate play() method exists before calling', async () => {
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      const invalidPlugin = { ...mockAutoplayInstance, play: undefined as any };
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      mockEmblaApi.plugins.mockReturnValueOnce({ autoplay: invalidPlugin } as any);

      expect(() => {
        renderHook(() => useBannerCarousel({ autoplay: true }));
      }).not.toThrow();
    });

    it('should validate play() is a function before calling', async () => {
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      const invalidPlugin = { ...mockAutoplayInstance, play: 'not-a-function' as any };
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      mockEmblaApi.plugins.mockReturnValueOnce({ autoplay: invalidPlugin } as any);

      expect(() => {
        renderHook(() => useBannerCarousel({ autoplay: true }));
      }).not.toThrow();
    });

    it('should call play() when it exists and is a function', async () => {
      mockAutoplayInstance.play.mockClear();
      mockAutoplayInstance.isPlaying.mockReturnValue(false);

      renderHook(() => useBannerCarousel({ autoplay: true }));

      await waitFor(() => {
        expect(mockAutoplayInstance.play).toHaveBeenCalled();
      });
    });

    it('should not call play() when already playing', async () => {
      mockAutoplayInstance.play.mockClear();
      mockAutoplayInstance.isPlaying.mockReturnValue(true);

      renderHook(() => useBannerCarousel({ autoplay: true }));

      await waitFor(() => {
        expect(mockAutoplayInstance.play).not.toHaveBeenCalled();
      });
    });
  });

  describe('Autoplay Cleanup and Memory Leaks (AC11)', () => {
    it('should call stop() on unmount when autoplay is enabled', async () => {
      mockAutoplayInstance.stop.mockClear();

      const { unmount } = renderHook(() => useBannerCarousel({ autoplay: true }));

      await waitFor(() => {
        expect(mockEmblaApi.plugins).toHaveBeenCalled();
      });

      unmount();

      expect(mockAutoplayInstance.stop).toHaveBeenCalled();
    });

    it('should not throw during cleanup if plugins() fails', async () => {
      const { unmount } = renderHook(() => useBannerCarousel({ autoplay: true }));

      mockEmblaApi.plugins.mockImplementationOnce(() => {
        throw new Error('Cleanup error');
      });

      expect(() => unmount()).not.toThrow();
    });

    it('should not throw during cleanup if stop() is missing', async () => {
      const { unmount } = renderHook(() => useBannerCarousel({ autoplay: true }));

      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      const invalidPlugin = { ...mockAutoplayInstance, stop: undefined as any };
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      mockEmblaApi.plugins.mockReturnValueOnce({ autoplay: invalidPlugin } as any);

      expect(() => unmount()).not.toThrow();
    });

    it('should not call stop() on unmount when autoplay is disabled', async () => {
      mockAutoplayInstance.stop.mockClear();

      const { unmount } = renderHook(() => useBannerCarousel({ autoplay: false }));

      unmount();

      expect(mockAutoplayInstance.stop).not.toHaveBeenCalled();
    });
  });

  describe('Autoplay Race Conditions (AC2)', () => {
    it('should handle rapid emblaApi changes without errors', async () => {
      const { rerender } = renderHook(
        ({ api }) => {
          mockUseEmblaCarousel.mockReturnValue([vi.fn(), api]);
          return useBannerCarousel({ autoplay: true });
        },
        { initialProps: { api: mockEmblaApi } }
      );

      const newApi = { ...mockEmblaApi, plugins: vi.fn(() => ({ autoplay: mockAutoplayInstance })) };

      expect(() => {
        rerender({ api: newApi });
        rerender({ api: mockEmblaApi });
        rerender({ api: newApi });
      }).not.toThrow();
    });

    it('should use stable callback to prevent race conditions', async () => {
      mockAutoplayInstance.play.mockClear();

      const { rerender } = renderHook(
        ({ delay }) => useBannerCarousel({ autoplay: true, autoplayDelay: delay }),
        { initialProps: { delay: 3000 } }
      );

      // Rapid rerenders should not cause multiple play() calls due to stable callback
      rerender({ delay: 3000 });
      rerender({ delay: 3000 });

      await waitFor(() => {
        // Should only call play once (or minimal times) due to useCallback stability
        expect(mockAutoplayInstance.play.mock.calls.length).toBeLessThanOrEqual(2);
      });
    });
  });
});
