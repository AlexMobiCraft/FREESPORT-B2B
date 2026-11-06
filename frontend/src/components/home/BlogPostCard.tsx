/**
 * BlogPostCard Component (Story 12.7)
 */

import React from 'react';
import Link from 'next/link';
import Image from 'next/image';
import { normalizeImageUrl } from '@/utils/media';

export interface BlogPostCardProps {
  id: string;
  title: string;
  excerpt: string;
  image: string;
  date: string;
  slug: string;
}

export const BlogPostCard: React.FC<BlogPostCardProps> = ({
  title,
  excerpt,
  image,
  date,
  slug,
}) => {
  const formatDate = (dateString: string) => {
    const date = new Date(dateString);
    return date.toLocaleDateString('ru-RU', {
      year: 'numeric',
      month: 'long',
      day: 'numeric',
    });
  };

  return (
    <Link
      href={`/blog/${slug}`}
      className="group block rounded-xl overflow-hidden bg-white shadow-default hover:shadow-hover transition-shadow focus:outline-none focus:ring-2 focus:ring-primary focus:ring-offset-2"
    >
      {/* Изображение */}
      <div className="relative aspect-video overflow-hidden">
        <Image
          src={normalizeImageUrl(image)}
          alt={title}
          fill
          className="object-cover group-hover:scale-105 transition-transform duration-[180ms] ease-in-out"
          sizes="(max-width: 640px) 100vw, (max-width: 1024px) 50vw, 33vw"
        />
      </div>

      {/* Контент */}
      <div className="p-4">
        {/* Дата */}
        <time className="text-xs text-text-secondary block mb-2" dateTime={date}>
          {formatDate(date)}
        </time>

        {/* Заголовок */}
        <h3 className="text-xl font-semibold text-text-primary mb-2 line-clamp-2">{title}</h3>

        {/* Excerpt */}
        <p className="text-sm text-text-secondary line-clamp-2 mb-3">{excerpt}</p>

        {/* Ссылка */}
        <span className="text-sm text-text-primary hover:underline inline-flex items-center gap-1">
          Читать далее
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
          </svg>
        </span>
      </div>
    </Link>
  );
};

BlogPostCard.displayName = 'BlogPostCard';
