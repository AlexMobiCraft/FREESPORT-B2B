/* eslint-disable @next/next/no-img-element */
/**
 * Electric Orange Category Card Component
 ...
 */

'use client';

import React from 'react';
import { cn } from '@/utils/cn';

// ============================================
// Types
// ============================================

export interface ElectricCategoryCardProps {
  id?: string;
  title: string;
  image: string;
  productCount?: number;
  href?: string;
  onClick?: () => void;
  className?: string;
}

// ============================================
// Category Card Component
// ============================================

export function ElectricCategoryCard({
  // id, // Removed unused id
  title,
  image,
  productCount,
  href,
  onClick,
  className,
}: ElectricCategoryCardProps) {
  const Component = href ? 'a' : 'div';
  const linkProps = href ? { href } : {};

  return (
    <Component
      {...linkProps}
      onClick={onClick}
      className={cn(
        'category-card', // Enforces aspect-ratio: 1 / 1 per globals-electric-orange.css
        'group block', // Needed for nested group-hover behavior
        className
      )}
    >
      {/* Background Image with Grayscale Effect */}
      <img
        src={image}
        alt={title}
        className="category-image absolute inset-0 w-full h-full object-cover"
        loading="lazy"
      />

      {/* Gradient Overlay */}
      <div className="absolute inset-0 bg-gradient-to-b from-transparent via-transparent to-black/80" />

      {/* Title Overlay */}
      <div className="absolute bottom-0 left-0 right-0 p-4 md:p-6">
        <h3 className="category-title">
          <span className="counter-skew">{title}</span>
        </h3>
        {productCount !== undefined && (
          <p
            className="text-[var(--color-text-secondary)] text-sm mt-1"
            style={{ fontFamily: "'Inter', sans-serif" }}
          >
            {productCount} товаров
          </p>
        )}

        {/* Arrow Indicator - Always visible */}
        <div
          className="mt-6 text-[var(--color-primary)] font-black uppercase text-sm"
          style={{
            fontFamily: "'Roboto Condensed', sans-serif",
            transform: 'skewX(-12deg)',
          }}
        >
          <span style={{ transform: 'skewX(12deg)', display: 'inline-block' }}>ПЕРЕЙТИ &gt;</span>
        </div>
      </div>

      {/* Orange Flash Effect on Hover */}
      <div
        className="absolute inset-0 pointer-events-none
          bg-gradient-to-r from-transparent via-[var(--color-primary-subtle)] to-transparent
          -translate-x-full group-hover:translate-x-full
          transition-transform duration-500 ease-out"
      />
    </Component>
  );
}

export default ElectricCategoryCard;
