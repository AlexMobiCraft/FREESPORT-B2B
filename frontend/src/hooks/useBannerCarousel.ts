/**
 * useBannerCarousel Hook
 * Carousel hook with Embla Carousel integration for marketing banners
 *
 * @see _bmad-output/implementation-artifacts/32-3-frontend-carousel-logic.md
 */

import { useState, useCallback, useEffect, useMemo } from 'react';
import useEmblaCarousel from 'embla-carousel-react';
import Autoplay from 'embla-carousel-autoplay';
import type { EmblaOptionsType, EmblaCarouselType, EmblaPluginType } from 'embla-carousel';

/**
 * Empty plugins array constant for referential stability when autoplay is disabled
 * Prevents unnecessary Embla re-initialization on re-renders
 */
const EMPTY_PLUGINS: EmblaPluginType[] = [];

/**
 * Опции для useBannerCarousel хука
 */
export interface UseBannerCarouselOptions {
  /** Включить бесконечную прокрутку (default: true) */
  loop?: boolean;
  /** Выравнивание слайдов: 'start' | 'center' | 'end' (default: 'start') */
  align?: EmblaOptionsType['align'];
  /**
   * Скорость анимации прокрутки (Embla `speed` option).
   * Положительное конечное число > 0. Определяет скорость scroll momentum.
   * Если не задано, используется Embla default (10).
   * Выше = быстрее переход между слайдами.
   * Невалидные значения (NaN, Infinity, <=0) игнорируются — используется Embla default.
   */
  speed?: number;
  /** Включить автопрокрутку (default: false) */
  autoplay?: boolean;
  /** Alias для autoplay (AC3 совместимость) */
  autoScroll?: boolean;
  /** Задержка автопрокрутки в мс (default: 4000) */
  autoplayDelay?: number;
  /** Остановить автопрокрутку при взаимодействии (default: true) */
  stopOnInteraction?: boolean;
  /** Остановить автопрокрутку при наведении мыши (default: true) */
  stopOnMouseEnter?: boolean;
}

/**
 * Возвращаемое значение useBannerCarousel хука
 */
export interface UseBannerCarouselReturn {
  /** Ref для контейнера карусели (viewport) */
  emblaRef: ReturnType<typeof useEmblaCarousel>[0];
  /** Текущий индекс выбранного слайда */
  selectedIndex: number;
  /** Массив scroll snap позиций (для точек навигации) */
  scrollSnaps: number[];
  /** Можно ли прокрутить назад */
  canScrollPrev: boolean;
  /** Можно ли прокрутить вперед */
  canScrollNext: boolean;
  /** Прокрутить к следующему слайду */
  scrollNext: () => void;
  /** Прокрутить к предыдущему слайду */
  scrollPrev: () => void;
  /** Прокрутить к слайду по индексу (для точек навигации) */
  onDotButtonClick: (index: number) => void;
  /** Прокрутить к слайду по индексу (прямой API) */
  scrollTo: (index: number) => void;
}

/**
 * Хук для создания карусели баннеров с поддержкой свайпов и автопрокрутки
 *
 * @param options - Опции карусели
 * @returns Объект с ref, состоянием и методами управления каруселью
 *
 * @example
 * ```tsx
 * const {
 *   emblaRef,
 *   selectedIndex,
 *   scrollSnaps,
 *   canScrollPrev,
 *   canScrollNext,
 *   scrollNext,
 *   scrollPrev,
 *   onDotButtonClick,
 * } = useBannerCarousel({
 *   loop: true,
 *   autoplay: true,
 *   autoplayDelay: 5000,
 * });
 *
 * return (
 *   <div ref={emblaRef} className="embla">
 *     <div className="embla__container">
 *       {slides.map((slide) => (
 *         <div className="embla__slide" key={slide.id}>{slide.content}</div>
 *       ))}
 *     </div>
 *   </div>
 * );
 * ```
 */
/**
 * Validates a numeric option - returns undefined if invalid (NaN, Infinity, <=0)
 */
function validatePositiveNumber(value: number | undefined): number | undefined {
  if (value === undefined) return undefined;
  if (!Number.isFinite(value) || value <= 0) return undefined;
  return value;
}

/**
 * Default autoplay delay in milliseconds
 */
const DEFAULT_AUTOPLAY_DELAY = 4000;

export function useBannerCarousel(options: UseBannerCarouselOptions = {}): UseBannerCarouselReturn {
  const {
    loop = true,
    align = 'start',
    speed: rawSpeed,
    autoplay: autoplayOption,
    autoScroll,
    autoplayDelay: rawAutoplayDelay,
    stopOnInteraction = true,
    stopOnMouseEnter = true,
  } = options;

  // Runtime validation for numeric options
  const speed = validatePositiveNumber(rawSpeed);
  const autoplayDelay = validatePositiveNumber(rawAutoplayDelay) ?? DEFAULT_AUTOPLAY_DELAY;

  /**
   * Autoplay activation logic (AC3):
   * - autoScroll takes priority over autoplay (explicit alias)
   * - If neither autoScroll nor autoplay is explicitly set, but autoplayDelay is provided,
   *   autoplay is enabled automatically ("defined interval" activates autoplay)
   * - Explicit false (autoScroll=false or autoplay=false) disables autoplay
   */
  const autoplay = (() => {
    // autoScroll has priority when explicitly set
    if (autoScroll !== undefined) return autoScroll;
    // autoplay explicit value
    if (autoplayOption !== undefined) return autoplayOption;
    // AC3: "defined interval" should activate autoplay
    if (rawAutoplayDelay !== undefined && validatePositiveNumber(rawAutoplayDelay) !== undefined) {
      return true;
    }
    // Default: disabled
    return false;
  })();

  // State for navigation
  const [selectedIndex, setSelectedIndex] = useState(0);
  const [scrollSnaps, setScrollSnaps] = useState<number[]>([]);
  const [canScrollPrev, setCanScrollPrev] = useState(false);
  const [canScrollNext, setCanScrollNext] = useState(false);

  // Memoize Embla options to prevent unnecessary reinitialization
  // dragFree: false ensures 1:1 finger tracking for swipe gestures (AC2)
  const emblaOptions = useMemo<EmblaOptionsType>(
    () => ({
      loop,
      align,
      dragFree: false,
      ...(speed !== undefined && { speed }),
    }),
    [loop, align, speed]
  );

  // Memoize autoplay options separately for stable reference
  const autoplayOptions = useMemo(
    () => ({
      delay: autoplayDelay,
      stopOnInteraction,
      stopOnMouseEnter,
    }),
    [autoplayDelay, stopOnInteraction, stopOnMouseEnter]
  );

  // Autoplay plugin instance via useMemo (safe: Autoplay() is a pure factory)
  const autoplayPlugin = useMemo<EmblaPluginType | null>(
    () => (autoplay ? Autoplay(autoplayOptions) : null),
    [autoplay, autoplayOptions]
  );

  // Memoize plugins array for referential stability
  // Uses EMPTY_PLUGINS constant when autoplay is disabled
  const plugins = useMemo<EmblaPluginType[]>(
    () => (autoplayPlugin ? [autoplayPlugin] : EMPTY_PLUGINS),
    [autoplayPlugin]
  );

  // Initialize Embla Carousel
  const [emblaRef, emblaApi] = useEmblaCarousel(emblaOptions, plugins);

  /**
   * Обновление состояния навигации на основе текущего состояния Embla
   */
  const onSelect = useCallback((embla: EmblaCarouselType) => {
    setSelectedIndex(embla.selectedScrollSnap());
    setCanScrollPrev(embla.canScrollPrev());
    setCanScrollNext(embla.canScrollNext());
  }, []);

  /**
   * Полная ресинхронизация состояния при reInit (scrollSnaps + nav-state)
   * Объединяет логику onInit + onSelect в один обработчик для reInit,
   * исключая дублирующие state-updates
   */
  const onReInit = useCallback((embla: EmblaCarouselType) => {
    setScrollSnaps(embla.scrollSnapList());
    setSelectedIndex(embla.selectedScrollSnap());
    setCanScrollPrev(embla.canScrollPrev());
    setCanScrollNext(embla.canScrollNext());
  }, []);

  /**
   * Прокрутка к следующему слайду
   */
  const scrollNext = useCallback(() => {
    if (emblaApi) emblaApi.scrollNext();
  }, [emblaApi]);

  /**
   * Прокрутка к предыдущему слайду
   */
  const scrollPrev = useCallback(() => {
    if (emblaApi) emblaApi.scrollPrev();
  }, [emblaApi]);

  /**
   * Shared runtime-guard for index-based scrolling.
   * Validates index (NaN, Infinity, negative, >= snapCount) and delegates to emblaApi.scrollTo.
   * Used by both onDotButtonClick and scrollTo to prevent behavior divergence.
   */
  const safeScrollTo = useCallback(
    (index: number) => {
      if (!emblaApi || !Number.isFinite(index) || index < 0) return;
      const floored = Math.floor(index);
      if (floored >= emblaApi.scrollSnapList().length) return;
      emblaApi.scrollTo(floored);
    },
    [emblaApi]
  );

  // Subscribe to Embla events
  // Direct call to onReInit handles initial mount state.
  // 'select' handles slide changes; 'reInit' handles full resync when options/plugins change.
  useEffect(() => {
    if (!emblaApi) return;

    // Initial state setup (emblaApi exists = already initialized)
    onReInit(emblaApi);

    // Register event listeners
    emblaApi.on('select', onSelect);
    emblaApi.on('reInit', onReInit);

    // Cleanup
    return () => {
      emblaApi.off('select', onSelect);
      emblaApi.off('reInit', onReInit);
    };
  }, [emblaApi, onSelect, onReInit]);

  /**
   * Autoplay lifecycle management with error handling and cleanup.
   * 
   * Handles:
   * - Safe plugin access with try-catch (AC1: no errors when plugin unavailable)
   * - Race condition prevention via stable callback (AC2)
   * - Full play/pause/stop lifecycle (AC7)
   * - Memory leak prevention via cleanup (AC11)
   * - Method validation before calling (AC10)
   * 
   * This effect manages autoplay plugin initialization and cleanup.
   * It handles cases where plugins are re-initialized dynamically (React 19, Strict Mode)
   * or when data loads asynchronously.
   */
  const startAutoplay = useCallback(() => {
    if (!emblaApi || !autoplay) return;

    try {
      const plugins = emblaApi.plugins();
      if (!plugins || typeof plugins.autoplay !== 'object') return;

      const autoplayPlugin = plugins.autoplay;

      // Validate play method exists before calling (AC10)
      if (typeof autoplayPlugin.play === 'function' && !autoplayPlugin.isPlaying()) {
        autoplayPlugin.play();
      }
    } catch {
      // Silently handle plugin access errors (AC1)
      // Plugin may not be available or initialized yet
    }
  }, [emblaApi, autoplay]);

  useEffect(() => {
    startAutoplay();

    // Cleanup: stop autoplay on unmount to prevent memory leaks (AC11)
    return () => {
      if (!emblaApi || !autoplay) return;

      try {
        const plugins = emblaApi.plugins();
        if (plugins && typeof plugins.autoplay === 'object') {
          const autoplayPlugin = plugins.autoplay;
          if (typeof autoplayPlugin.stop === 'function') {
            autoplayPlugin.stop();
          }
        }
      } catch {
        // Silently handle cleanup errors
      }
    };
  }, [startAutoplay, emblaApi, autoplay]);

  return {
    emblaRef,
    selectedIndex,
    scrollSnaps,
    canScrollPrev,
    canScrollNext,
    scrollNext,
    scrollPrev,
    onDotButtonClick: safeScrollTo,
    scrollTo: safeScrollTo,
  };
}
