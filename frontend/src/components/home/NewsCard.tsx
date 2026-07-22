'use client';

import React from 'react';
import Image from 'next/image';
import Link from 'next/link';
import { normalizeImageUrl } from '@/utils/media';

/**
 * Карточка новости для ленты /news
 */
export interface NewsCardProps {
  /** Заголовок новости */
  title: string;
  /** Краткое описание */
  excerpt: string;
  /** URL изображения (может быть абсолютным) */
  image: string;
  /** Дата публикации */
  publishedAt: string;
  /** Slug для формирования ссылки на детальную страницу */
  slug: string;
}

export const NewsCard: React.FC<NewsCardProps> = ({ title, excerpt, image, publishedAt, slug }) => {
  const formatDate = (dateString: string) => {
    const date = new Date(dateString);
    return date.toLocaleDateString('ru-RU', {
      year: 'numeric',
      month: 'long',
      day: 'numeric',
    });
  };

  const safeImage = normalizeImageUrl(image) || '/images/new/running-shoes.jpg';

  return (
    <Link
      href={`/news/${slug}`}
      aria-label={`Читать новость: ${title}`}
      className="group block rounded-xl overflow-hidden bg-white shadow-default hover:shadow-hover transition-shadow focus-within:ring-2 focus-within:ring-primary focus-within:ring-offset-2"
    >
      <article>
        <div className="relative aspect-video overflow-hidden">
          <Image
            src={safeImage}
            alt={title}
            fill
            className="object-cover group-hover:scale-105 transition-transform duration-[180ms] ease-in-out"
            sizes="(max-width: 640px) 100vw, (max-width: 1024px) 50vw, 33vw"
          />
        </div>

        <div className="p-4">
          <time className="text-xs text-text-secondary block mb-2" dateTime={publishedAt}>
            {formatDate(publishedAt)}
          </time>
          <h3 className="text-xl font-semibold text-text-primary mb-2 line-clamp-2">{title}</h3>
          <p className="text-sm text-text-secondary line-clamp-2">{excerpt}</p>
        </div>
      </article>
    </Link>
  );
};

NewsCard.displayName = 'NewsCard';
