/**
 * ElectricHeroSection Component
 *
 * Hero-секция главной страницы в стиле Electric Orange Design System.
 * Динамические баннеры с API + fallback на статические данные.
 *
 * Design System: Electric Orange v2.3.0
 * - Skew: -12deg для контейнеров, 12deg для текста (counter-skew)
 * - Typography: Roboto Condensed (headers), Inter (body)
 * - Colors: #FF6600 (primary), #0F0F0F (bg-body)
 */

'use client';

import { useState, useEffect, useCallback } from 'react';
import Image from 'next/image';
import Link from 'next/link';
import { useAuthStore } from '@/stores/authStore';
import { ElectricButton } from '@/components/ui/Button/ElectricButton';
import bannersService from '@/services/bannersService';
import type { Banner } from '@/types/banners';
import { ChevronLeft, ChevronRight } from 'lucide-react';

interface BannerContent {
  title: string;
  subtitle: string;
  cta: {
    text: string;
    link: string;
  };
  image?: string;
}

// Статические баннеры для fallback
const STATIC_BANNERS: BannerContent[] = [
  {
    title: 'ОПТОВЫЕ ПОСТАВКИ СПОРТИВНЫХ ТОВАРОВ',
    subtitle: 'Специальные цены для бизнеса. Персональный менеджер и гибкие условия.',
    cta: { text: 'Узнать условия', link: '/wholesale' },
  },
  {
    title: 'НОВАЯ КОЛЛЕКЦИЯ 2025',
    subtitle: 'Стиль и качество для вашего спорта. Эксклюзивные новинки уже в продаже.',
    cta: { text: 'В каталог', link: '/electric/catalog' },
  },
  {
    title: 'FREESPORT — ВАШ СПОРТИВНЫЙ ПАРТНЁР',
    subtitle: '5 брендов. 1000+ товаров. Доставка по всей России.',
    cta: { text: 'Начать покупки', link: '/electric/catalog' },
  },
];

/**
 * Skeleton loader в Electric Orange стиле
 */
const HeroSkeleton = () => (
  <section
    className="relative min-h-[500px] bg-[var(--bg-body)] overflow-hidden"
    aria-label="Hero section loading"
    data-testid="electric-hero-skeleton"
  >
    <div className="max-w-[1400px] mx-auto px-4 sm:px-6 lg:px-8 py-16 flex flex-col lg:flex-row items-center gap-12">
      {/* Text skeleton */}
      <div className="flex-1 space-y-6">
        <div
          className="h-16 bg-[var(--bg-card)] animate-pulse"
          style={{ transform: 'skewX(-12deg)', width: '80%' }}
        />
        <div className="h-6 bg-[var(--bg-card)] animate-pulse w-full" />
        <div className="h-6 bg-[var(--bg-card)] animate-pulse w-3/4" />
        <div
          className="h-14 w-48 bg-[var(--bg-card)] animate-pulse mt-8"
          style={{ transform: 'skewX(-12deg)' }}
        />
      </div>
      {/* Image skeleton */}
      <div className="w-full lg:w-[500px] aspect-square bg-[var(--bg-card)] animate-pulse" />
    </div>
  </section>
);

export const ElectricHeroSection = () => {
  const { user } = useAuthStore();
  const [banners, setBanners] = useState<Banner[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);
  const [currentIndex, setCurrentIndex] = useState(0);
  const [isPaused, setIsPaused] = useState(false);

  // Загрузка баннеров из API
  useEffect(() => {
    const loadBanners = async () => {
      try {
        setIsLoading(true);
        const data = await bannersService.getActive();
        setBanners(data);
        setError(null);
      } catch (err) {
        console.error('Failed to load banners:', err);
        setError(err instanceof Error ? err : new Error('Unknown error'));
      } finally {
        setIsLoading(false);
      }
    };

    loadBanners();
  }, []);

  // Автопрокрутка карусели
  useEffect(() => {
    const itemsCount = banners.length > 0 ? banners.length : STATIC_BANNERS.length;
    if (itemsCount <= 1 || isPaused) return;

    const interval = setInterval(() => {
      setCurrentIndex(prev => (prev + 1) % itemsCount);
    }, 5000);

    return () => clearInterval(interval);
  }, [banners.length, isPaused]);

  // Навигация
  const goToPrev = useCallback(() => {
    const itemsCount = banners.length > 0 ? banners.length : STATIC_BANNERS.length;
    setCurrentIndex(prev => (prev - 1 + itemsCount) % itemsCount);
  }, [banners.length]);

  const goToNext = useCallback(() => {
    const itemsCount = banners.length > 0 ? banners.length : STATIC_BANNERS.length;
    setCurrentIndex(prev => (prev + 1) % itemsCount);
  }, [banners.length]);

  // Определение контента для fallback
  const getStaticBannerContent = (): BannerContent => {
    if (
      user?.role === 'wholesale_level1' ||
      user?.role === 'wholesale_level2' ||
      user?.role === 'wholesale_level3'
    ) {
      return STATIC_BANNERS[0];
    }
    if (user?.role === 'retail') {
      return STATIC_BANNERS[1];
    }
    return STATIC_BANNERS[2];
  };

  if (isLoading) {
    return <HeroSkeleton />;
  }

  // Используем API баннеры или fallback
  const useApiBanners = !error && banners.length > 0;
  const currentBanner = useApiBanners ? banners[currentIndex] : null;
  const currentStatic = useApiBanners ? null : getStaticBannerContent();
  const itemsCount = useApiBanners ? banners.length : 1; // Для fallback показываем только 1

  const title = currentBanner?.title || currentStatic?.title || '';
  const subtitle = currentBanner?.subtitle || currentStatic?.subtitle || '';
  const ctaText = currentBanner?.cta_text || currentStatic?.cta.text || '';
  const ctaLink = currentBanner?.cta_link || currentStatic?.cta.link || '/';
  const imageUrl = currentBanner?.image_url || '/og-image.jpg';
  const imageAlt = currentBanner?.image_alt || 'FREESPORT';

  return (
    <section
      className="relative min-h-[500px] lg:min-h-[600px] bg-[var(--bg-body)] overflow-hidden"
      aria-label="Hero section"
      onMouseEnter={() => setIsPaused(true)}
      onMouseLeave={() => setIsPaused(false)}
    >
      {/* Background gradient overlay */}
      <div
        className="absolute inset-0 bg-gradient-to-r from-[var(--bg-body)] via-[var(--bg-body)]/80 to-transparent z-10"
        aria-hidden="true"
      />

      {/* Background image */}
      <div className="absolute inset-0 z-0">
        <Image
          src={imageUrl}
          alt={imageAlt}
          fill
          className="object-cover object-right opacity-40"
          priority
          unoptimized
        />
      </div>

      {/* Content */}
      <div className="relative z-20 max-w-[1400px] mx-auto px-4 sm:px-6 lg:px-8 py-16 lg:py-24 min-h-[500px] lg:min-h-[600px] flex flex-col justify-center">
        <div className="max-w-2xl">
          {/* Title with Electric skew */}
          <h1
            className="text-4xl md:text-5xl lg:text-6xl font-black uppercase tracking-tight text-[var(--color-text-primary)] mb-6"
            style={{
              fontFamily: "'Roboto Condensed', sans-serif",
              transform: 'skewX(-12deg)',
              transformOrigin: 'left',
            }}
          >
            <span style={{ display: 'inline-block', transform: 'skewX(12deg)' }}>{title}</span>
          </h1>

          {/* Subtitle */}
          <p
            className="text-lg md:text-xl text-[var(--color-text-secondary)] mb-8 max-w-xl"
            style={{ fontFamily: "'Inter', sans-serif" }}
          >
            {subtitle}
          </p>

          {/* CTA Button */}
          <Link href={ctaLink}>
            <ElectricButton variant="primary" size="lg">
              {ctaText}
            </ElectricButton>
          </Link>
        </div>

        {/* Navigation arrows - only if multiple banners */}
        {itemsCount > 1 && (
          <>
            <button
              onClick={goToPrev}
              className="absolute left-4 top-1/2 -translate-y-1/2 w-12 h-12 flex items-center justify-center border border-[var(--border-default)] text-[var(--color-text-secondary)] hover:border-[var(--color-primary)] hover:text-[var(--color-primary)] transition-all duration-200 bg-[var(--bg-body)]/80"
              style={{ transform: 'translateY(-50%) skewX(-12deg)' }}
              aria-label="Previous banner"
            >
              <ChevronLeft className="w-6 h-6" style={{ transform: 'skewX(12deg)' }} />
            </button>
            <button
              onClick={goToNext}
              className="absolute right-4 top-1/2 -translate-y-1/2 w-12 h-12 flex items-center justify-center border border-[var(--border-default)] text-[var(--color-text-secondary)] hover:border-[var(--color-primary)] hover:text-[var(--color-primary)] transition-all duration-200 bg-[var(--bg-body)]/80"
              style={{ transform: 'translateY(-50%) skewX(-12deg)' }}
              aria-label="Next banner"
            >
              <ChevronRight className="w-6 h-6" style={{ transform: 'skewX(12deg)' }} />
            </button>
          </>
        )}

        {/* Dots indicators */}
        {itemsCount > 1 && (
          <div className="absolute bottom-8 left-1/2 -translate-x-1/2 flex gap-3">
            {Array.from({ length: itemsCount }).map((_, index) => (
              <button
                key={index}
                onClick={() => setCurrentIndex(index)}
                className={`h-2 transition-all duration-300 ${index === currentIndex
                    ? 'w-8 bg-[var(--color-primary)]'
                    : 'w-2 bg-[var(--color-text-secondary)]/50 hover:bg-[var(--color-text-secondary)]'
                  }`}
                style={{ transform: 'skewX(-12deg)' }}
                aria-label={`Go to banner ${index + 1}`}
              />
            ))}
          </div>
        )}
      </div>
    </section>
  );
};

ElectricHeroSection.displayName = 'ElectricHeroSection';

export default ElectricHeroSection;
