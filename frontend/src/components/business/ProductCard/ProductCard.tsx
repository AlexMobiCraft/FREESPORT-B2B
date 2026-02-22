/**
 * ProductCard Component
 *
 * Компонент карточки товара с поддержкой grid/list/compact layouts и новой дизайн-системой v2.0.
 *
 * Features:
 * - Три варианта отображения: grid, list, compact
 * - Ролевое ценообразование (B2C/B2B)
 * - Автоматические бейджи (sale, new, hit)
 * - Кнопка "В избранное"
 * - Адаптивный дизайн
 * - WCAG 2.1 AA accessibility
 *
 * @see docs/stories/epic-12/12.4.story.md
 *
 * @example
 * ```tsx
 * <ProductCard
 *   product={product}
 *   layout="grid"
 *   userRole="retail"
 *   onAddToCart={(id) => handleAddToCart(id)}
 *   onToggleFavorite={(id) => handleToggleFavorite(id)}
 * />
 * ```
 */

'use client';

import React, { useEffect, useState } from 'react';
import Image from 'next/image';
import Link from 'next/link';
import { Heart } from 'lucide-react';
import { ProductBadge } from '@/components/common/ProductBadge';
import Button from '@/components/ui/Button';
import type { Product } from '@/types/api';
import { cn } from '@/utils/cn';
import { formatPrice, type UserRole } from '@/utils/pricing';
export type { UserRole };

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? '';
const MEDIA_BASE_URL =
  process.env.NEXT_PUBLIC_MEDIA_URL ||
  (API_BASE_URL ? API_BASE_URL.replace(/\/api(?:\/v\d+)?\/?$/, '') : '');

const IMAGE_FALLBACK_PATH = '/images/No_image.svg';

const resolveImageUrl = (path?: string | null): string | null => {
  if (!path) return null;
  if (/^(data|blob):/i.test(path)) {
    return path;
  }

  const publicBase = MEDIA_BASE_URL || '';

  if (/^https?:\/\//i.test(path)) {
    // API может вернуть URL с внутренними Docker адресами (http://backend:8000 или http://nginx)
    // Заменяем их на публичный адрес, доступный из браузера
    if (path.startsWith('http://backend:8000')) {
      return path.replace('http://backend:8000', publicBase);
    }

    if (path.startsWith('http://nginx')) {
      return path.replace('http://nginx', publicBase);
    }

    // Если путь уже публичный (например, https://freesport.ru), оставляем как есть
    return path;
  }

  // Если путь относительный, добавляем публичный базовый URL
  if (publicBase) {
    if (path.startsWith('/')) {
      return `${publicBase}${path}`;
    }
    return `${publicBase}/${path}`;
  }

  return path;
};

/**
 * Props компонента ProductCard
 */
export interface ProductCardProps {
  /** Товар для отображения */
  product: Product;
  /** Вариант отображения карточки */
  layout?: 'grid' | 'list' | 'compact';
  /** Режим работы (B2C/B2B) */
  mode?: 'b2c' | 'b2b';
  /** Роль пользователя для ценообразования */
  userRole?: UserRole;
  /** Показывать RRP (Recommended Retail Price) для B2B */
  showRRP?: boolean;
  /** Callback при добавлении в корзину */
  onAddToCart?: (productId: number) => void;
  /** Callback при переключении избранного */
  onToggleFavorite?: (productId: number) => void;
  /** Товар в избранном */
  isFavorite?: boolean;
  /** Callback при клике на карточку (для compact layout) */
  onClick?: () => void;
  /** Дополнительные CSS классы */
  className?: string;
}

/**
 * Определяет цену товара на основе роли пользователя
 */
function getProductPrice(product: Product, userRole: UserRole): number {
  switch (userRole) {
    case 'retail':
      return product.retail_price;
    case 'wholesale_level1':
      return product.opt1_price || product.retail_price;
    case 'wholesale_level2':
      return product.opt2_price || product.opt1_price || product.retail_price;
    case 'wholesale_level3':
      return product.opt3_price || product.opt2_price || product.opt1_price || product.retail_price;
    case 'trainer':
      return (
        (product as Product & { trainer_price?: number }).trainer_price || product.retail_price
      );
    case 'federation_rep':
      return (
        (product as Product & { federation_price?: number; trainer_price?: number })
          .federation_price ||
        (product as Product & { trainer_price?: number }).trainer_price ||
        product.retail_price
      );
    default:
      return product.retail_price;
  }
}

/**
 * Компонент ProductCard
 */
export const ProductCard = React.forwardRef<HTMLDivElement, ProductCardProps>(
  (
    {
      product,
      layout = 'grid',
      mode = 'b2c',
      userRole = 'retail',
      // showRRP = false,
      onAddToCart,
      onToggleFavorite,
      isFavorite = false,
      onClick,
      className,
    },
    ref
  ) => {
    const currentPrice = getProductPrice(product, userRole);
    const hasDiscount = product.discount_percent && product.discount_percent > 0;
    const stockQuantity = product.stock_quantity ?? 0;
    const canBeOrdered = product.can_be_ordered ?? false;
    const explicitStockFlag: boolean | null =
      typeof (product as Product & { is_in_stock?: boolean }).is_in_stock === 'boolean'
        ? product.is_in_stock
        : null;
    const fallbackStockState = canBeOrdered || stockQuantity > 0;
    const isInStock = explicitStockFlag !== null ? explicitStockFlag : fallbackStockState;

    // Обработчик переключения избранного
    const handleToggleFavorite = (e: React.MouseEvent) => {
      e.preventDefault();
      e.stopPropagation();
      onToggleFavorite?.(product.id);
    };

    // Обработчик добавления в корзину
    const handleAddToCart = (e: React.MouseEvent) => {
      e.preventDefault();
      e.stopPropagation();
      onAddToCart?.(product.id);
    };

    // Получаем основное изображение
    const rawImage =
      product.images?.find(img => img.is_primary)?.image ||
      product.images?.[0]?.image ||
      product.main_image ||
      product.image ||
      null;
    const resolvedProductImage = resolveImageUrl(rawImage);
    const primaryImage = resolvedProductImage ?? IMAGE_FALLBACK_PATH;
    const [imageSrc, setImageSrc] = useState(primaryImage);

    useEffect(() => {
      setImageSrc(primaryImage);
    }, [primaryImage]);

    // Базовые стили карточки
    const cardBaseStyles = cn(
      'bg-white rounded-[12px]',
      'shadow-[0_8px_24px_rgba(15,23,42,0.08)]',
      'hover:shadow-[0_10px_32px_rgba(15,23,42,0.12)]',
      'hover:-translate-y-0.5',
      'transition-all duration-[180ms] ease-[cubic-bezier(0.4,0,0.2,1)]',
      'overflow-hidden'
    );

    // Compact layout
    if (layout === 'compact') {
      const cardContent = (
        <div
          ref={ref}
          className={cn(
            cardBaseStyles,
            'w-[180px] flex-shrink-0 cursor-pointer',
            'focus-within:ring-2 focus-within:ring-[var(--color-primary)] focus-within:ring-offset-2',
            className
          )}
          role="article"
          aria-label={`Товар: ${product.name}`}
        >
          {/* Изображение */}
          <div className="relative w-full aspect-square bg-neutral-100">
            {/* Badge */}
            <div className="absolute top-2 left-2 z-10">
              <ProductBadge product={product} />
            </div>

            {/* Кнопка избранного */}
            <button
              onClick={handleToggleFavorite}
              className={cn(
                'absolute top-1.5 right-1.5 z-10',
                'p-1.5 rounded-full bg-white/80 backdrop-blur-sm',
                'transition-colors',
                isFavorite ? 'text-[#A63232]' : 'text-neutral-600',
                'hover:text-[#A63232]',
                'focus:outline-none focus:ring-2 focus:ring-[var(--color-primary)]'
              )}
              aria-label={isFavorite ? 'Удалить из избранного' : 'Добавить в избранное'}
              role="button"
            >
              <Heart className="w-4 h-4" fill={isFavorite ? 'currentColor' : 'none'} />
            </button>

            {/* Изображение товара */}
            {imageSrc ? (
              <Image
                src={imageSrc}
                alt={product.name}
                fill
                sizes="180px"
                className="object-cover"
                onError={() => setImageSrc(IMAGE_FALLBACK_PATH)}
                loading="lazy"
              />
            ) : (
              <div className="w-full h-full flex items-center justify-center text-neutral-400">
                <svg
                  xmlns="http://www.w3.org/2000/svg"
                  width="48"
                  height="48"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                >
                  <rect x="3" y="3" width="18" height="18" rx="2" ry="2" />
                  <circle cx="8.5" cy="8.5" r="1.5" />
                  <polyline points="21 15 16 10 5 21" />
                </svg>
              </div>
            )}
          </div>

          {/* Информация о товаре */}
          <div className="p-3 flex flex-col">
            {/* Бренд */}
            {product.brand && (
              <p className="text-caption text-[var(--color-text-secondary)] mb-1">
                {product.brand.name}
              </p>
            )}

            {/* Название */}
            <h3
              className="text-body-s font-medium text-[var(--color-text-primary)] mb-2 line-clamp-2 min-h-[40px]"
              title={product.name}
            >
              {product.name}
            </h3>

            {/* Цена */}
            <div className="mt-auto">
              <p className="text-body-m font-semibold text-[var(--color-text-primary)]">
                {currentPrice.toLocaleString('ru-RU')} ₽
              </p>

              {/* Статус наличия */}
              {!isInStock && (
                <p className="text-caption text-[var(--color-text-secondary)] mt-1">
                  Нет в наличии
                </p>
              )}
            </div>
          </div>
        </div>
      );

      // Если передан onClick — используем его, иначе оборачиваем в Link
      if (onClick) {
        return (
          <div
            onClick={onClick}
            onKeyDown={e => {
              if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault();
                onClick?.();
              }
            }}
            tabIndex={0}
            role="button"
          >
            {cardContent}
          </div>
        );
      }

      return (
        <Link href={`/product/${product.slug}`} className="block">
          {cardContent}
        </Link>
      );
    }

    // List layout
    if (layout === 'list') {
      return (
        <Link href={`/product/${product.slug}`} className="block">
          <div
            ref={ref}
            className={cn(
              cardBaseStyles,
              'flex gap-4 p-4',
              'focus-within:ring-2 focus-within:ring-[var(--color-primary)] focus-within:ring-offset-2',
              'cursor-pointer',
              className
            )}
            role="article"
            aria-label={`Товар: ${product.name}`}
          >
            {/* Изображение */}
            <div className="relative w-[120px] h-[120px] flex-shrink-0 rounded-[8px] overflow-hidden bg-neutral-100">
              {imageSrc ? (
                <Image
                  src={imageSrc}
                  alt={product.name}
                  fill
                  sizes="120px"
                  className="object-cover"
                  onError={() => setImageSrc('/images/No_image.svg')}
                  loading="lazy"
                />
              ) : (
                <div className="w-full h-full flex items-center justify-center text-neutral-400">
                  <svg
                    xmlns="http://www.w3.org/2000/svg"
                    width="48"
                    height="48"
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="2"
                  >
                    <rect x="3" y="3" width="18" height="18" rx="2" ry="2" />
                    <circle cx="8.5" cy="8.5" r="1.5" />
                    <polyline points="21 15 16 10 5 21" />
                  </svg>
                </div>
              )}
            </div>

            {/* Информация о товаре */}
            <div className="flex-1 flex flex-col justify-between">
              <div>
                {/* Бренд и Badge */}
                <div className="flex items-center gap-2 mb-1">
                  {product.brand && (
                    <p className="text-body-s text-[var(--color-text-secondary)]">
                      {product.brand.name}
                    </p>
                  )}
                  <ProductBadge product={product} />
                </div>

                {/* Название */}
                <h3 className="text-body-m font-medium text-[var(--color-text-primary)] mb-2 line-clamp-2 min-h-[48px]">
                  {product.name}
                </h3>

                {/* Описание */}
                {product.description && (
                  <p className="text-body-s text-[var(--color-text-secondary)] line-clamp-2">
                    {product.description}
                  </p>
                )}
              </div>
            </div>

            {/* Цена и CTA */}
            <div className="flex flex-col items-end gap-2 justify-between">
              {/* Кнопка избранного */}
              <button
                onClick={handleToggleFavorite}
                className={cn(
                  'p-2 rounded-full bg-white/80 backdrop-blur-sm',
                  'transition-colors',
                  isFavorite ? 'text-[#A63232]' : 'text-neutral-600',
                  'hover:text-[#A63232]',
                  'focus:outline-none focus:ring-2 focus:ring-[var(--color-primary)]'
                )}
                aria-label={isFavorite ? 'Удалить из избранного' : 'Добавить в избранное'}
                role="button"
              >
                <Heart className="w-5 h-5" fill={isFavorite ? 'currentColor' : 'none'} />
              </button>

              {/* Цена */}
              <div className="text-right">
                {hasDiscount && (
                  <p className="text-body-s text-[var(--color-text-muted)] line-through mr-2">
                    {product.retail_price.toLocaleString('ru-RU')} ₽
                  </p>
                )}
                <p className="text-title-m font-semibold text-[var(--color-text-primary)]">
                  {currentPrice.toLocaleString('ru-RU')} ₽
                </p>

                {/* RRP/MSRP для B2B */}
                {(mode === 'b2b' || userRole !== 'retail') && product.rrp && product.rrp > 0 && (
                  <div className="mt-1 space-y-0.5">
                    <p className="text-body-s text-[var(--color-text-secondary)]">
                      РРЦ: {formatPrice(product.rrp)}
                    </p>
                  </div>
                )}

                {/* Кнопка "В корзину" */}
                {isInStock && onAddToCart && (
                  <Button
                    variant="secondary"
                    size="small"
                    onClick={handleAddToCart}
                    className="mt-3"
                    aria-label={`Добавить ${product.name} в корзину`}
                  >
                    В корзину
                  </Button>
                )}
              </div>
            </div>
          </div>
        </Link>
      );
    }

    // Grid layout (default)
    return (
      <Link href={`/product/${product.slug}`} className="block">
        <div
          ref={ref}
          className={cn(
            cardBaseStyles,
            'focus-within:ring-2 focus-within:ring-[var(--color-primary)] focus-within:ring-offset-2',
            'cursor-pointer',
            className
          )}
          role="article"
          aria-label={`Товар: ${product.name}`}
        >
          {/* Изображение */}
          <div className="relative w-full aspect-square bg-neutral-100">
            {/* Badge */}
            <div className="absolute top-2 left-2 z-10">
              <ProductBadge product={product} />
            </div>

            {/* Кнопка избранного */}
            <button
              onClick={handleToggleFavorite}
              className={cn(
                'absolute top-2 right-2 z-10',
                'p-2 rounded-full bg-white/80 backdrop-blur-sm',
                'transition-colors',
                isFavorite ? 'text-[#A63232]' : 'text-neutral-600',
                'hover:text-[#A63232]',
                'focus:outline-none focus:ring-2 focus:ring-[var(--color-primary)]'
              )}
              aria-label={isFavorite ? 'Удалить из избранного' : 'Добавить в избранное'}
              role="button"
            >
              <Heart className="w-5 h-5" fill={isFavorite ? 'currentColor' : 'none'} />
            </button>

            {/* Изображение товара */}
            {imageSrc ? (
              <Image
                src={imageSrc}
                alt={product.name}
                fill
                sizes="(max-width: 768px) 50vw, (max-width: 1024px) 33vw, 25vw"
                className="object-cover"
                onError={() => setImageSrc('/images/No_image.svg')}
                loading="lazy"
              />
            ) : (
              <div className="w-full h-full flex items-center justify-center text-neutral-400">
                <svg
                  xmlns="http://www.w3.org/2000/svg"
                  width="64"
                  height="64"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                >
                  <rect x="3" y="3" width="18" height="18" rx="2" ry="2" />
                  <circle cx="8.5" cy="8.5" r="1.5" />
                  <polyline points="21 15 16 10 5 21" />
                </svg>
              </div>
            )}
          </div>

          {/* Информация о товаре */}
          <div className="p-4 flex flex-col">
            {/* Бренд */}
            {product.brand && (
              <p className="text-body-s text-[var(--color-text-secondary)] mb-1">
                {product.brand.name}
              </p>
            )}

            {/* Название */}
            <h3
              className="text-body-m font-medium text-[var(--color-text-primary)] mb-2 line-clamp-2 min-h-[48px]"
              title={product.name}
            >
              {product.name}
            </h3>

            {/* Цена */}
            <div className="mb-3">
              {hasDiscount && (
                <p className="text-body-s text-[var(--color-text-muted)] line-through mr-2">
                  {product.retail_price.toLocaleString('ru-RU')} ₽
                </p>
              )}
              <p className="text-title-m font-semibold text-[var(--color-text-primary)]">
                {currentPrice.toLocaleString('ru-RU')} ₽
              </p>

              {/* RRP/MSRP для B2B */}
              {(mode === 'b2b' || userRole !== 'retail') && product.rrp && product.rrp > 0 && (
                <div className="mt-1 space-y-0.5">
                  <p className="text-body-s text-[var(--color-text-secondary)]">
                    РРЦ: {formatPrice(product.rrp)}
                  </p>
                </div>
              )}
            </div>

            {/* Кнопка "В корзину" */}
            {isInStock && onAddToCart && (
              <Button
                variant="secondary"
                size="medium"
                onClick={handleAddToCart}
                className="w-full"
                aria-label={`Добавить ${product.name} в корзину`}
              >
                В корзину
              </Button>
            )}

            {/* Статус наличия */}
            {!isInStock && (
              <p className="text-body-s text-[var(--color-text-secondary)] text-center">
                Нет в наличии
              </p>
            )}
          </div>
        </div>
      </Link>
    );
  }
);

ProductCard.displayName = 'ProductCard';
