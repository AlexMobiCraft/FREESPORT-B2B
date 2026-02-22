/**
 * News Detail Page (/news/[slug])
 * Story 20.2 - Детальная страница новости
 *
 * Отображает полное содержание новости
 */

import React from 'react';
import type { Metadata } from 'next';
import Link from 'next/link';
import Image from 'next/image';
import { notFound } from 'next/navigation';
import { ArrowLeft } from 'lucide-react';
import { Breadcrumb } from '@/components/ui';
import { newsService } from '@/services/newsService';
import { normalizeImageUrl } from '@/utils/media';

interface NewsDetailPageProps {
  params: Promise<{ slug: string }>;
}

/**
 * Generate dynamic metadata for SEO
 */
export async function generateMetadata({ params }: NewsDetailPageProps): Promise<Metadata> {
  const { slug } = await params;

  try {
    const news = await newsService.getNewsBySlug(slug);
    return {
      title: `${news.title} | Новости FREESPORT`,
      description: news.excerpt,
      openGraph: {
        title: news.title,
        description: news.excerpt,
        images: news.image ? [news.image] : [],
      },
    };
  } catch {
    return {
      title: 'Новость не найдена | FREESPORT',
      description: 'Запрашиваемая новость не найдена',
    };
  }
}

/**
 * Format date to Russian locale
 */
const formatDate = (dateString: string): string => {
  return new Intl.DateTimeFormat('ru-RU', {
    day: 'numeric',
    month: 'long',
    year: 'numeric',
  }).format(new Date(dateString));
};

export default async function NewsDetailPage({ params }: NewsDetailPageProps) {
  const { slug } = await params;

  // Fetch news data
  let news;
  try {
    news = await newsService.getNewsBySlug(slug);
  } catch {
    notFound();
    return null; // TypeScript safety - notFound() never returns but TS doesn't know that
  }

  const breadcrumbItems = [
    { label: 'Главная', href: '/' },
    { label: 'Новости', href: '/news' },
    { label: news.title },
  ];

  return (
    <div className="min-h-screen bg-neutral-50">
      {/* Breadcrumb */}
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
        <Breadcrumb items={breadcrumbItems} />
      </div>

      {/* Article Content */}
      <article className="bg-white">
        <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
          {/* Hero Image */}
          {news.image && (
            <div className="relative aspect-video w-full mb-8 rounded-xl overflow-hidden">
              <Image
                src={normalizeImageUrl(news.image)}
                alt={news.title}
                fill
                className="object-cover"
                sizes="(max-width: 1024px) 100vw, 896px"
                priority
              />
            </div>
          )}

          {/* Meta Info */}
          <div className="flex items-center gap-3 text-sm text-text-secondary mb-6">
            <time dateTime={news.published_at}>{formatDate(news.published_at)}</time>
            {news.author && (
              <>
                <span className="text-neutral-300">•</span>
                <span>{news.author}</span>
              </>
            )}
          </div>

          {/* Title */}
          <h1 className="text-3xl sm:text-4xl lg:text-5xl font-bold text-text-primary mb-8">
            {news.title}
          </h1>

          {/* Content */}
          <div
            className="prose prose-lg max-w-none text-text-primary"
            dangerouslySetInnerHTML={{ __html: news.content || news.excerpt }}
          />

          {/* Back Link */}
          <div className="mt-12 pt-8 border-t border-neutral-200">
            <Link
              href="/news"
              className="inline-flex items-center gap-2 text-primary hover:text-primary-dark transition-colors font-medium"
            >
              <ArrowLeft className="w-5 h-5" />
              Назад к новостям
            </Link>
          </div>
        </div>
      </article>
    </div>
  );
}
