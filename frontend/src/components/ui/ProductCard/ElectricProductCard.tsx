/* eslint-disable @next/next/no-img-element */
/**
 * Electric Orange Product Card Component
 *
 * Product Card for catalog and homepage
 ...
 */

'use client';

import React from 'react';
import { cn } from '@/utils/cn';
import { ElectricBadge } from '../Badge';
import { ElectricButton } from '../Button/ElectricButton';

const formatPrice = (value: number) => {
  return new Intl.NumberFormat('ru-RU').format(value);
};

export interface ElectricProductCardProps {
  id?: string;
  image: string;
  title: string;
  brand?: string;
  price: number;
  oldPrice?: number;
  rrp?: number;
  badge?: 'primary' | 'sale' | 'hit' | 'new';
  isFavorite?: boolean;
  inStock?: boolean;
  onAddToCart?: () => void;
  onToggleFavorite?: () => void;
  onClick?: () => void;
  className?: string;
}

// ============================================
// Product Card Component
// ============================================

export function ElectricProductCard({
  // id, // Removed unused id
  image,
  title,
  brand,
  price,
  oldPrice,
  rrp,
  badge,
  isFavorite = false,
  inStock = true,
  onAddToCart,
  onToggleFavorite,
  onClick,
  className,
}: ElectricProductCardProps) {
  const handleCardClick = (e: React.MouseEvent | React.KeyboardEvent) => {
    // Prevent navigation if clicking on buttons
    if ((e.target as HTMLElement).closest('button')) {
      return;
    }
    onClick?.();
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault();
      handleCardClick(e);
    }
  };

  return (
    <article
      className={cn(
        // Base - Rectangular card
        'bg-[var(--bg-card)] border border-[var(--border-default)] p-3 md:p-4',
        'transition-all duration-300',
        'hover:border-[var(--color-primary)] hover:shadow-[var(--shadow-hover)] hover:-translate-y-[5px]',
        'cursor-pointer group',
        'flex flex-col h-full', // Ensure full height for alignment
        'w-full', // Strict Width per Design
        !inStock && 'opacity-60',
        className
      )}
      onClick={handleCardClick}
      onKeyDown={handleKeyDown}
      role="button"
      tabIndex={0}
    >
      {/* Image Container */}
      <div className="relative aspect-square bg-[var(--color-neutral-300)] mb-2 md:mb-4 overflow-hidden flex-shrink-0">
        <img
          src={image}
          alt={title}
          className="w-full h-full object-cover transition-transform duration-300 group-hover:scale-105"
          loading="lazy"
        />

        {/* Badge */}
        {badge && (
          <div className="absolute top-2 left-2 z-10">
            <ElectricBadge variant={badge}>
              {badge === 'hit'
                ? 'Хит'
                : badge === 'sale'
                  ? `-${Math.round(((oldPrice! - price) / oldPrice!) * 100)}%`
                  : 'New'}
            </ElectricBadge>
          </div>
        )}

        {/* Favorite Button */}
        <button
          onClick={e => {
            e.stopPropagation();
            onToggleFavorite?.();
          }}
          className={cn(
            'absolute top-2 right-2 z-10 w-8 h-8 flex items-center justify-center',
            'transition-colors duration-200',
            isFavorite
              ? 'text-[var(--color-primary)]'
              : 'text-[var(--color-text-muted)] hover:text-[var(--color-primary)]'
          )}
          aria-label={isFavorite ? 'Убрать из избранного' : 'Добавить в избранное'}
        >
          {isFavorite ? '♥' : '♡'}
        </button>

        {/* Out of Stock Overlay */}
        {!inStock && (
          <div className="absolute inset-0 bg-black/60 flex items-center justify-center">
            <span className="text-[var(--color-text-secondary)] font-medium uppercase">
              Нет в наличии
            </span>
          </div>
        )}
      </div>

      {/* Product Info - Flex Grow to push buttons down */}
      <div className="space-y-2 flex-grow flex flex-col justify-between">
        <div>
          {/* Brand */}
          {brand && (
            <p
              className="text-xs text-[var(--color-text-secondary)] uppercase tracking-wide"
              style={{ fontFamily: "'Inter', sans-serif" }}
            >
              {brand}
            </p>
          )}

          <h3
            className="text-sm md:text-base text-[var(--foreground)] font-medium line-clamp-2 min-h-[40px] md:min-h-[48px] mb-1 md:mb-2"
            style={{ fontFamily: "'Inter', sans-serif" }}
          >
            {title}
          </h3>
        </div>

        {/* Price - Skewed */}
        <div className="flex items-center gap-1 md:gap-2 mb-2 md:mb-4">
          <span
            className="text-lg md:text-xl font-bold text-[var(--color-primary)] inline-block"
            style={{
              fontFamily: "'Roboto Condensed', sans-serif",
              transform: 'skewX(-12deg)',
            }}
          >
            {formatPrice(price)} ₽
          </span>

          {oldPrice && (
            <span className="text-xs md:text-sm text-[var(--color-text-muted)] line-through">
              {formatPrice(oldPrice)} ₽
            </span>
          )}
        </div>

        {/* RRP/MSRP labels */}
        {rrp && (
          <div className="mb-2 space-y-0.5 text-[10px] md:text-xs text-[var(--color-text-secondary)]">
            <div>РРЦ: {formatPrice(rrp)} ₽</div>
          </div>
        )}
      </div>

      {/* Action Buttons - Stack on mobile, row on desktop */}
      <div className="flex flex-col sm:flex-row gap-1.5 sm:gap-2 mt-auto">
        <div className="flex-1 min-w-0">
          <ElectricButton
            variant="primary"
            size="sm"
            className="w-full text-[10px] sm:text-xs"
            disabled={!inStock}
            onClick={e => {
              e.stopPropagation();
              onAddToCart?.();
            }}
          >
            В КОРЗИНУ
          </ElectricButton>
        </div>
        <div className="flex-1 min-w-0">
          <ElectricButton
            variant="outline"
            size="sm"
            className={cn(
              'w-full text-[10px] sm:text-xs',
              isFavorite && 'border-[var(--color-primary)] text-[var(--color-primary)]'
            )}
            onClick={e => {
              e.stopPropagation();
              onToggleFavorite?.();
            }}
          >
            ИЗБРАННОЕ
          </ElectricButton>
        </div>
      </div>
    </article>
  );
}

export default ElectricProductCard;
