/**
 * NewsSection Component
 * Загружает новости из API /news и показывает fallback при недоступности
 *
 * Поддерживает два варианта дизайна:
 * - default: Стандартный светлый дизайн
 * - electric: Electric Orange Design System
 */

'use client';

import React, { useEffect, useState } from 'react';
import Link from 'next/link';
import { NewsCard } from './NewsCard';
import { ElectricNewsCard } from '@/components/ui/NewsCard/ElectricNewsCard';
import { ElectricButton } from '@/components/ui/Button/ElectricButton';
import Button from '@/components/ui/Button';
import { newsService } from '@/services/newsService';
import type { NewsItem } from '@/types/api';
import { NewsSkeletonLoader } from '@/components/common/NewsSkeletonLoader';
import { NewsFallback } from '@/components/common/NewsFallback';
import { STATIC_NEWS_ITEMS } from '@/__mocks__/news';

export interface NewsSectionProps {
  /** Design variant: 'default' | 'electric' */
  variant?: 'default' | 'electric';
  /** Custom title */
  title?: string;
  /** Link for "View all" button */
  viewAllLink?: string;
}

interface NewsCardData {
  id: number;
  title: string;
  slug: string;
  excerpt: string;
  image: string;
  publishedAt: string;
  category?: string;
}

const getFallbackImage = (index: number): string => {
  return (
    STATIC_NEWS_ITEMS[index % STATIC_NEWS_ITEMS.length]?.image || '/images/new/running-shoes.jpg'
  );
};

const mapNewsItem = (item: NewsItem, index: number): NewsCardData => ({
  id: item.id,
  title: item.title,
  slug: item.slug,
  excerpt: item.excerpt,
  image: item.image || getFallbackImage(index),
  publishedAt: item.published_at,
  category: item.category || 'Новости',
});

const mapStaticItem = (item: (typeof STATIC_NEWS_ITEMS)[number]): NewsCardData => ({
  id: item.id,
  title: item.title,
  slug: item.slug,
  excerpt: item.excerpt,
  image: item.image,
  publishedAt: item.published_at,
  category: 'Новости',
});

const formatDate = (dateString: string): string => {
  try {
    const date = new Date(dateString);
    return date.toLocaleDateString('ru-RU', {
      day: 'numeric',
      month: 'long',
      year: 'numeric',
    });
  } catch {
    return dateString;
  }
};

/**
 * Electric skeleton loader
 */
const ElectricNewsSkeleton = () => (
  <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
    {Array.from({ length: 2 }).map((_, i) => (
      <div
        key={i}
        className="flex bg-[var(--bg-card)] border border-[var(--border-default)] overflow-hidden animate-pulse"
      >
        <div className="w-1/3 aspect-video bg-[var(--border-default)]" />
        <div className="flex-1 p-4 space-y-3">
          <div className="h-3 w-16 bg-[var(--border-default)]" />
          <div className="h-5 w-full bg-[var(--border-default)]" />
          <div className="h-5 w-3/4 bg-[var(--border-default)]" />
          <div className="h-3 w-1/2 bg-[var(--border-default)]" />
        </div>
      </div>
    ))}
  </div>
);

export const NewsSection: React.FC<NewsSectionProps> = ({
  variant = 'default',
  title = 'Новости',
  viewAllLink = '/news',
}) => {
  const [newsItems, setNewsItems] = useState<NewsCardData[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const isElectric = variant === 'electric';

  useEffect(() => {
    let isMounted = true;

    const fetchNews = async () => {
      try {
        setIsLoading(true);
        const data = await newsService.getNews({ page_size: isElectric ? 2 : 3 });

        if (!isMounted) return;

        if (data && data.length > 0) {
          setNewsItems(data.slice(0, isElectric ? 2 : 3).map(mapNewsItem));
        } else {
          setNewsItems(STATIC_NEWS_ITEMS.slice(0, isElectric ? 2 : 3).map(mapStaticItem));
        }
      } catch {
        if (!isMounted) return;
        setNewsItems(STATIC_NEWS_ITEMS.slice(0, isElectric ? 2 : 3).map(mapStaticItem));
      } finally {
        if (isMounted) {
          setIsLoading(false);
        }
      }
    };

    fetchNews();

    return () => {
      isMounted = false;
    };
  }, [isElectric]);

  const hasNews = newsItems.length > 0;

  // Electric variant
  if (isElectric) {
    return (
      <section
        className="max-w-[1400px] mx-auto px-4 sm:px-6 lg:px-8 py-12"
        aria-labelledby="news-heading"
      >
        {/* Header row */}
        <div className="flex items-center justify-between mb-8">
          <h2
            id="news-heading"
            className="text-2xl md:text-3xl font-black uppercase tracking-tight text-[var(--color-text-primary)]"
            style={{
              fontFamily: "'Roboto Condensed', sans-serif",
              transform: 'skewX(-12deg)',
              transformOrigin: 'left',
            }}
          >
            <span style={{ display: 'inline-block', transform: 'skewX(12deg)' }}>
              {title.toUpperCase()}
            </span>
          </h2>

          <Link href={viewAllLink}>
            <ElectricButton variant="outline" size="sm">
              Все новости
            </ElectricButton>
          </Link>
        </div>

        {isLoading && <ElectricNewsSkeleton />}

        {!isLoading && !hasNews && (
          <div className="flex flex-col items-center justify-center gap-4 py-12">
            <p className="text-[var(--color-text-secondary)]">Нет доступных новостей</p>
          </div>
        )}

        {!isLoading && hasNews && (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
            {newsItems.map(item => (
              <ElectricNewsCard
                key={item.id}
                id={String(item.id)}
                image={item.image}
                category={item.category || 'Новости'}
                date={formatDate(item.publishedAt)}
                title={item.title}
                excerpt={item.excerpt}
                href={`/news/${item.slug}`}
              />
            ))}
          </div>
        )}
      </section>
    );
  }

  // Default variant
  return (
    <section
      className="max-w-[1280px] mx-auto px-3 md:px-4 lg:px-6 py-12"
      aria-labelledby="news-heading"
    >
      {/* Header with button */}
      <div className="flex items-center justify-between mb-8">
        <h2 id="news-heading" className="text-3xl font-bold text-text-primary">
          {title}
        </h2>
        <Link href={viewAllLink}>
          <Button variant="primary">Все новости</Button>
        </Link>
      </div>

      {isLoading && <NewsSkeletonLoader />}

      {!isLoading && !hasNews && <NewsFallback />}

      {!isLoading && hasNews && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {newsItems.map(item => (
            <NewsCard
              key={item.id}
              title={item.title}
              slug={item.slug}
              excerpt={item.excerpt}
              image={item.image}
              publishedAt={item.publishedAt}
            />
          ))}
        </div>
      )}
    </section>
  );
};

NewsSection.displayName = 'NewsSection';
