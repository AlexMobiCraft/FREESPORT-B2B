/**
 * HeroSection Component
 *
 * Hero-секция главной страницы с динамическими баннерами
 * адаптированными под роль пользователя (B2B/B2C/Guest)
 * Загрузка баннеров из API с fallback на статические данные
 */

'use client';

import { useState, useEffect } from 'react';
import Image from 'next/image';
import Link from 'next/link';
import { useAuthStore } from '@/stores/authStore';
import { Button } from '@/components/ui/Button/Button';
import bannersService from '@/services/bannersService';
import type { Banner } from '@/types/banners';

interface BannerContent {
  title: string;
  subtitle: string;
  cta: {
    text: string;
    link: string;
  };
}

// Статические баннеры для fallback
const STATIC_BANNERS: BannerContent[] = [
  {
    title: 'Оптовые поставки спортивных товаров',
    subtitle: 'Специальные цены для бизнеса. Персональный менеджер и гибкие условия.',
    cta: {
      text: 'Узнать оптовые условия',
      link: '/wholesale',
    },
  },
  {
    title: 'Новая коллекция 2025',
    subtitle: 'Стиль и качество для вашего спорта. Эксклюзивные новинки уже в продаже.',
    cta: {
      text: 'Перейти в каталог',
      link: '/catalog',
    },
  },
  {
    title: 'FREESPORT - Спортивные товары для профессионалов и любителей',
    subtitle: '5 брендов. 1000+ товаров. Доставка по всей России.',
    cta: {
      text: 'Начать покупки',
      link: '/catalog',
    },
  },
];

const HeroSection = () => {
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

  // Автопрокрутка карусели (только если баннеров > 1)
  useEffect(() => {
    if (banners.length <= 1 || isPaused) return;

    const interval = setInterval(() => {
      setCurrentIndex(prevIndex => (prevIndex + 1) % banners.length);
    }, 5000); // 5 секунд

    return () => clearInterval(interval);
  }, [banners.length, isPaused]);

  // Определение контента баннера на основе роли пользователя (fallback)
  const getStaticBannerContent = (): BannerContent => {
    // B2B пользователи (wholesale)
    if (
      user?.role === 'wholesale_level1' ||
      user?.role === 'wholesale_level2' ||
      user?.role === 'wholesale_level3'
    ) {
      return STATIC_BANNERS[0];
    }

    // B2C пользователи (retail)
    if (user?.role === 'retail') {
      return STATIC_BANNERS[1];
    }

    // Неавторизованные пользователи (универсальный баннер)
    return STATIC_BANNERS[2];
  };

  // Skeleton loader
  if (isLoading) {
    return (
      <section
        className="relative overflow-hidden text-gray-900 md:min-h-[400px]"
        aria-label="Hero section loading"
        data-testid="hero-skeleton"
      >
        <div className="relative mx-auto px-3 md:px-4 lg:px-6 max-w-[1280px] h-full flex flex-col-reverse gap-6 py-8 md:py-12 md:flex-row md:items-center">
          <div className="text-center md:text-left max-w-2xl space-y-6">
            {/* Skeleton title */}
            <div className="h-12 bg-gray-200 rounded-lg animate-pulse w-3/4 mx-auto md:mx-0" />
            {/* Skeleton subtitle */}
            <div className="h-6 bg-gray-200 rounded-lg animate-pulse w-full" />
            <div className="h-6 bg-gray-200 rounded-lg animate-pulse w-5/6 mx-auto md:mx-0" />
            {/* Skeleton button */}
            <div className="flex justify-center md:justify-start">
              <div className="h-14 w-48 bg-gray-200 rounded-2xl animate-pulse" />
            </div>
          </div>
          <div className="flex w-full md:w-[480px] items-center justify-center md:justify-end md:self-center md:flex-shrink-0">
            <div className="relative w-full max-w-[480px] aspect-[7/4]">
              <div className="h-full min-h-[300px] bg-gray-200 rounded-[32px] animate-pulse" />
            </div>
          </div>
        </div>
      </section>
    );
  }

  // Fallback на статические баннеры при ошибке или пустом ответе
  const shouldUseFallback = error || banners.length === 0;

  if (shouldUseFallback) {
    const bannerContent = getStaticBannerContent();

    return (
      <section
        className="relative overflow-hidden text-gray-900 md:min-h-[400px]"
        aria-label="Hero section"
      >
        <div className="relative mx-auto px-3 md:px-4 lg:px-6 max-w-[1280px] h-full flex flex-col-reverse gap-6 py-8 md:py-12 md:flex-row md:items-center">
          <div className="text-center md:text-left md:flex-1 md:pr-8">
            <h1 className="text-3xl md:text-4xl font-bold mb-4">
              {bannerContent.title}
            </h1>
            <p className="text-base font-medium mb-6 mx-auto md:mx-0 text-gray-600 max-w-3xl">
              {bannerContent.subtitle}
            </p>
            <div className="flex justify-center md:justify-start">
              <Link href={bannerContent.cta.link}>
                <Button
                  variant="primary"
                  size="large"
                  className="shadow-[0_10px_30px_rgba(8,145,178,0.2)]"
                >
                  {bannerContent.cta.text}
                </Button>
              </Link>
            </div>
          </div>

          <div className="flex w-full md:w-[480px] items-center justify-center md:justify-end md:self-center md:flex-shrink-0">
            <div className="relative w-full max-w-[480px] aspect-[7/4]">
              <Image
                src="/og-image.jpg"
                alt="FREESPORT — подборка спортивных товаров"
                fill
                className="rounded-[32px] object-cover shadow-[0_35px_120px_rgba(0,0,0,0.15)]"
                priority
              />
              <div className="pointer-events-none absolute inset-0 rounded-[32px] ring-1 ring-gray-900/5" />
            </div>
          </div>
        </div>
      </section>
    );
  }

  // Отображение баннера из API
  const currentBanner = banners[currentIndex];

  return (
    <section
      className="relative overflow-hidden text-gray-900 md:min-h-[400px]"
      aria-label="Hero section"
      onMouseEnter={() => setIsPaused(true)}
      onMouseLeave={() => setIsPaused(false)}
    >
      <div className="relative mx-auto px-3 md:px-4 lg:px-6 max-w-[1280px] h-full flex flex-col-reverse gap-6 py-8 md:py-12 md:flex-row md:items-center">
        <div className="text-center md:text-left md:flex-1 md:pr-8 md:self-stretch md:flex md:flex-col md:justify-center">
          <div>
            <h1 className="text-3xl md:text-4xl font-bold mb-4">
              {currentBanner.title}
            </h1>
            <p className="text-base font-medium mb-6 mx-auto md:mx-0 text-gray-600 max-w-3xl">
              {currentBanner.subtitle}
            </p>
          </div>
          <div className="flex justify-center md:justify-start md:mt-auto">
            <Link href={currentBanner.cta_link}>
              <Button
                variant="primary"
                size="large"
                className="shadow-[0_10px_30px_rgba(8,145,178,0.2)]"
              >
                {currentBanner.cta_text}
              </Button>
            </Link>
          </div>
        </div>

        <div className="flex w-full md:w-[480px] items-center justify-center md:justify-end md:self-center md:flex-shrink-0">
          <div className="relative w-full max-w-[480px] aspect-[7/4]">
            <Image
              src={currentBanner.image_url}
              alt={currentBanner.image_alt}
              fill
              className="rounded-[32px] object-cover shadow-[0_35px_120px_rgba(0,0,0,0.15)]"
              priority
              unoptimized
            />
            <div className="pointer-events-none absolute inset-0 rounded-[32px] ring-1 ring-gray-900/5" />
          </div>
        </div>
      </div>

      {/* Индикаторы карусели (dots) - только если баннеров > 1 */}
      {banners.length > 1 && (
        <div className="relative mt-4 md:mt-0 md:absolute md:bottom-4 left-1/2 transform -translate-x-1/2 flex gap-2 justify-center pb-4 md:pb-0">
          {banners.map((_, index) => (
            <button
              key={index}
              onClick={() => setCurrentIndex(index)}
              className={`w-2 h-2 rounded-full transition-all ${index === currentIndex ? 'bg-gray-900 w-8' : 'bg-gray-300'
                }`}
              aria-label={`Go to banner ${index + 1}`}
            />
          ))}
        </div>
      )}
    </section>
  );
};

export default HeroSection;
