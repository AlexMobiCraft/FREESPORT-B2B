/**
 * Blog Detail Page (/blog/[slug])
 * Story 21.3 - Детальная страница статьи блога
 *
 * Отображает полное содержание статьи блога
 */

import React from 'react';
import type { Metadata } from 'next';
import Link from 'next/link';
import Image from 'next/image';
import { notFound } from 'next/navigation';
import { ArrowLeft } from 'lucide-react';
import { Breadcrumb } from '@/components/ui';
import { blogService } from '@/services/blogService';
import { normalizeImageUrl } from '@/utils/media';

interface BlogDetailPageProps {
  params: Promise<{ slug: string }>;
}

/**
 * Generate dynamic metadata for SEO
 */
export async function generateMetadata({ params }: BlogDetailPageProps): Promise<Metadata> {
  const { slug } = await params;

  try {
    const post = await blogService.getBlogPostBySlug(slug);
    return {
      title: `${post.meta_title || post.title} | Блог FREESPORT`,
      description: post.meta_description || post.excerpt,
      openGraph: {
        title: post.meta_title || post.title,
        description: post.meta_description || post.excerpt,
        images: post.image ? [post.image] : [],
      },
    };
  } catch {
    return {
      title: 'Статья не найдена | FREESPORT',
      description: 'Запрашиваемая статья не найдена',
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

export default async function BlogDetailPage({ params }: BlogDetailPageProps) {
  const { slug } = await params;

  // Fetch blog post data
  let post;
  try {
    post = await blogService.getBlogPostBySlug(slug);
  } catch {
    notFound();
    return null; // TypeScript safety - notFound() never returns but TS doesn't know that
  }

  const breadcrumbItems = [
    { label: 'Главная', href: '/' },
    { label: 'Блог', href: '/blog' },
    { label: post.title },
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
          {post.image && (
            <div className="relative aspect-video w-full mb-8 rounded-xl overflow-hidden">
              <Image
                src={normalizeImageUrl(post.image)}
                alt={post.title}
                fill
                className="object-cover"
                sizes="(max-width: 1024px) 100vw, 896px"
                priority
              />
            </div>
          )}

          {/* Meta Info */}
          <div className="flex items-center gap-3 text-sm text-text-secondary mb-6">
            <time dateTime={post.published_at}>{formatDate(post.published_at)}</time>
            {post.author && (
              <>
                <span className="text-neutral-300">•</span>
                <span>{post.author}</span>
              </>
            )}
            {post.category && (
              <>
                <span className="text-neutral-300">•</span>
                <span>{post.category}</span>
              </>
            )}
          </div>

          {/* Title */}
          <h1 className="text-3xl sm:text-4xl lg:text-5xl font-bold text-text-primary mb-4">
            {post.title}
          </h1>

          {/* Subtitle */}
          {post.subtitle && <p className="text-xl text-text-secondary mb-8">{post.subtitle}</p>}

          {/* Content */}
          <div
            className="prose prose-lg max-w-none text-text-primary"
            dangerouslySetInnerHTML={{ __html: post.content || post.excerpt }}
          />

          {/* Back Link */}
          <div className="mt-12 pt-8 border-t border-neutral-200">
            <Link
              href="/blog"
              className="inline-flex items-center gap-2 text-primary hover:text-primary-dark transition-colors font-medium"
            >
              <ArrowLeft className="w-5 h-5" />
              Назад к блогу
            </Link>
          </div>
        </div>
      </article>
    </div>
  );
}
