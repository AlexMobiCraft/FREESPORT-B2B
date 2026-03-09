/* eslint-disable @next/next/no-img-element */
/**
 * Electric Orange News Card Component
 *
 * Horizontal news card for news listing
 * Features:
 * - Horizontal layout
 * - 16:9 Image container
 * - Skewed category badge
 * - Straight text typography
 *
 * @see docs/4-ux-design/00-design-system-migration/02-component-specs.md#news-card
 */

'use client';

import React from 'react';
import { cn } from '@/utils/cn';

export interface ElectricNewsCardProps {
  id?: string;
  image: string;
  category: string;
  date: string;
  title: string;
  excerpt: string;
  href?: string;
  className?: string;
}

export function ElectricNewsCard({
  image,
  category,
  date,
  title,
  excerpt,
  href = '#',
  className,
}: ElectricNewsCardProps) {
  return (
    <article
      className={cn(
        'news-card group cursor-pointer', // Uses .news-card from globals-electric-orange.css
        className
      )}
    >
      {/* 16:9 Image Container */}
      <div className="news-image-container relative">
        <img
          src={image}
          alt={title}
          className="news-image transition-transform duration-500 group-hover:scale-105"
          loading="lazy"
        />

        {/* Category Badge - Skewed */}
        <div className="absolute top-2 left-2">
          <span
            className="inline-block bg-[var(--color-primary)] text-black px-3 py-1 font-bold text-xs uppercase"
            style={{
              transform: 'skewX(-12deg)',
              fontFamily: "'Roboto Condensed', sans-serif",
            }}
          >
            <span className="inline-block" style={{ transform: 'skewX(12deg)' }}>
              {category}
            </span>
          </span>
        </div>
      </div>

      {/* Content */}
      <div className="flex flex-col flex-1 py-4 pr-6">
        <time className="text-[var(--color-text-muted)] text-xs mb-2 font-inter">{date}</time>

        <h3 className="text-[var(--foreground)] text-lg font-semibold mb-3 leading-tight group-hover:text-[var(--color-primary)] transition-colors font-inter">
          <a href={href} className="before:absolute before:inset-0">
            {title}
          </a>
        </h3>

        <p className="text-[var(--color-text-secondary)] text-sm leading-relaxed line-clamp-2 font-inter">
          {excerpt}
        </p>

        {/* Read More Link (Mock) */}
        <div className="mt-auto pt-4">
          <span
            className="text-[var(--color-primary)] text-xs font-bold uppercase border-b border-transparent group-hover:border-[var(--color-primary)] transition-all"
            style={{ fontFamily: "'Roboto Condensed', sans-serif" }}
          >
            Читать далее
          </span>
        </div>
      </div>
    </article>
  );
}

export default ElectricNewsCard;
