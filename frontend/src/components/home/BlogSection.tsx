/**
 * BlogSection Component
 * Загружает статьи блога из API /blog и показывает fallback при недоступности
 *
 * Поддерживает два варианта дизайна:
 * - default: Стандартный светлый дизайн
 * - electric: Electric Orange Design System
 */

'use client';

import React, { useEffect, useState } from 'react';
import Link from 'next/link';
import { BlogPostCard } from './BlogPostCard';
import { ElectricNewsCard } from '@/components/ui/NewsCard/ElectricNewsCard';
import { ElectricButton } from '@/components/ui/Button/ElectricButton';
import Button from '@/components/ui/Button';
import { blogService } from '@/services/blogService';
import type { BlogItem } from '@/types/api';
import { NewsSkeletonLoader } from '@/components/common/NewsSkeletonLoader';
import { NewsFallback } from '@/components/common/NewsFallback';
import { MOCK_BLOG_POSTS } from '@/__mocks__/blogPosts';

export interface BlogSectionProps {
  /** Design variant: 'default' | 'electric' */
  variant?: 'default' | 'electric';
  /** Custom title */
  title?: string;
  /** Link for "View all" button */
  viewAllLink?: string;
}

interface BlogCardData {
  id: string;
  title: string;
  slug: string;
  excerpt: string;
  image: string;
  date: string;
  category?: string;
}

const getFallbackImage = (index: number): string => {
  return MOCK_BLOG_POSTS[index % MOCK_BLOG_POSTS.length]?.image || '/images/new/running-shoes.jpg';
};

const mapBlogItem = (item: BlogItem, index: number): BlogCardData => ({
  id: String(item.id),
  title: item.title,
  slug: item.slug,
  excerpt: item.excerpt,
  image: item.image || getFallbackImage(index),
  date: item.published_at,
  category: 'Блог',
});

const mapStaticItem = (item: (typeof MOCK_BLOG_POSTS)[number]): BlogCardData => ({
  id: item.id,
  title: item.title,
  slug: item.slug,
  excerpt: item.excerpt,
  image: item.image,
  date: item.date,
  category: 'Блог',
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
const ElectricBlogSkeleton = () => (
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

export const BlogSection: React.FC<BlogSectionProps> = ({
  variant = 'default',
  title = 'Наш блог',
  viewAllLink = '/blog',
}) => {
  const [blogItems, setBlogItems] = useState<BlogCardData[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const isElectric = variant === 'electric';

  useEffect(() => {
    let isMounted = true;

    const fetchBlog = async () => {
      try {
        setIsLoading(true);
        const data = await blogService.getBlogPosts({ page_size: isElectric ? 2 : 3 });

        if (!isMounted) return;

        if (data && data.results && data.results.length > 0) {
          setBlogItems(data.results.slice(0, isElectric ? 2 : 3).map(mapBlogItem));
        } else {
          setBlogItems(MOCK_BLOG_POSTS.slice(0, isElectric ? 2 : 3).map(mapStaticItem));
        }
      } catch {
        if (!isMounted) return;
        setBlogItems(MOCK_BLOG_POSTS.slice(0, isElectric ? 2 : 3).map(mapStaticItem));
      } finally {
        if (isMounted) {
          setIsLoading(false);
        }
      }
    };

    fetchBlog();

    return () => {
      isMounted = false;
    };
  }, [isElectric]);

  const hasPosts = blogItems.length > 0;

  // Electric variant
  if (isElectric) {
    return (
      <section
        className="max-w-[1400px] mx-auto px-4 sm:px-6 lg:px-8 py-12"
        aria-labelledby="blog-heading"
      >
        {/* Header row */}
        <div className="flex items-center justify-between mb-8">
          <h2
            id="blog-heading"
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
              Все статьи
            </ElectricButton>
          </Link>
        </div>

        {isLoading && <ElectricBlogSkeleton />}

        {!isLoading && !hasPosts && (
          <div className="flex flex-col items-center justify-center gap-4 py-12">
            <p className="text-[var(--color-text-secondary)]">Нет доступных статей</p>
          </div>
        )}

        {!isLoading && hasPosts && (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
            {blogItems.map(item => (
              <ElectricNewsCard
                key={item.id}
                id={item.id}
                image={item.image}
                category={item.category || 'Блог'}
                date={formatDate(item.date)}
                title={item.title}
                excerpt={item.excerpt}
                href={`/blog/${item.slug}`}
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
      aria-labelledby="blog-heading"
    >
      {/* Header with button */}
      <div className="flex items-center justify-between mb-8">
        <h2 id="blog-heading" className="text-3xl font-bold text-text-primary">
          {title}
        </h2>
        <Link href={viewAllLink}>
          <Button variant="primary">Все статьи</Button>
        </Link>
      </div>

      {isLoading && <NewsSkeletonLoader />}

      {!isLoading && !hasPosts && <NewsFallback />}

      {!isLoading && hasPosts && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {blogItems.map(item => (
            <BlogPostCard
              key={item.id}
              id={item.id}
              title={item.title}
              slug={item.slug}
              excerpt={item.excerpt}
              image={item.image}
              date={item.date}
            />
          ))}
        </div>
      )}
    </section>
  );
};

BlogSection.displayName = 'BlogSection';
