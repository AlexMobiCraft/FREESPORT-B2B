/**
 * ProductInfo Component (Story 12.1)
 * Основная информация о товаре: название, SKU, бренд, описание, рейтинг
 */

import React from 'react';
import type { ProductDetail } from '@/types/api';
import { formatPrice, getPriceForRole, type UserRole } from '@/utils/pricing';
import type { ProductVariant } from '@/types/api';

interface ProductInfoProps {
  product: ProductDetail;
  userRole?: UserRole;
  selectedVariant?: ProductVariant | null;
}

export default function ProductInfo({
  product,
  userRole = 'guest',
  selectedVariant,
}: ProductInfoProps) {
  // Защита от undefined для product.price
  const defaultPrice = { retail: 0, currency: 'RUB' };
  const price = product.price || defaultPrice;

  // Используем цену варианта, если он выбран, иначе базовую цену для роли
  const displayedPrice =
    selectedVariant && selectedVariant.current_price
      ? parseFloat(selectedVariant.current_price)
      : getPriceForRole(price, userRole);


  // Определяем статус наличия
  const getStockStatus = () => {
    if (product.stock_quantity > 0) {
      return {
        label: 'В наличии',
        variant: 'delivered' as const,
        className: 'bg-green-50 text-green-700 border border-green-200',
      };
    } else if (product.can_be_ordered) {
      return {
        label: 'Под заказ',
        variant: 'transit' as const,
        className: 'bg-yellow-50 text-yellow-700 border border-yellow-200',
      };
    } else {
      return {
        label: 'Нет в наличии',
        variant: 'cancelled' as const,
        className: 'bg-red-50 text-red-700 border border-red-200',
      };
    }
  };

  const stockStatus = getStockStatus();

  // RRP видят только оптовики (1-3), тренеры и админы
  const canSeeRrp = [
    'wholesale_level1',
    'wholesale_level2',
    'wholesale_level3',
    'trainer',
    'admin',
  ].includes(userRole);

  // Рендеринг рейтинга звездами
  const renderRating = () => {
    if (!product.rating) return null;

    const fullStars = Math.floor(product.rating);
    const hasHalfStar = product.rating % 1 >= 0.5;
    const emptyStars = 5 - fullStars - (hasHalfStar ? 1 : 0);

    return (
      <div className="flex items-center gap-2">
        <div className="flex items-center gap-0.5" aria-label={`Рейтинг ${product.rating} из 5`}>
          {/* Полные звезды */}
          {[...Array(fullStars)].map((_, i) => (
            <svg
              key={`full-${i}`}
              className="w-5 h-5 text-yellow-400 fill-current"
              viewBox="0 0 20 20"
              aria-hidden="true"
            >
              <path d="M9.049 2.927c.3-.921 1.603-.921 1.902 0l1.07 3.292a1 1 0 00.95.69h3.462c.969 0 1.371 1.24.588 1.81l-2.8 2.034a1 1 0 00-.364 1.118l1.07 3.292c.3.921-.755 1.688-1.54 1.118l-2.8-2.034a1 1 0 00-1.175 0l-2.8 2.034c-.784.57-1.838-.197-1.539-1.118l1.07-3.292a1 1 0 00-.364-1.118L2.98 8.72c-.783-.57-.38-1.81.588-1.81h3.461a1 1 0 00.951-.69l1.07-3.292z" />
            </svg>
          ))}
          {/* Полузвезда */}
          {hasHalfStar && (
            <svg className="w-5 h-5 text-yellow-400" viewBox="0 0 20 20" aria-hidden="true">
              <defs>
                <linearGradient id="half-star">
                  <stop offset="50%" stopColor="currentColor" stopOpacity="1" />
                  <stop offset="50%" stopColor="currentColor" stopOpacity="0.2" />
                </linearGradient>
              </defs>
              <path
                fill="url(#half-star)"
                d="M9.049 2.927c.3-.921 1.603-.921 1.902 0l1.07 3.292a1 1 0 00.95.69h3.462c.969 0 1.371 1.24.588 1.81l-2.8 2.034a1 1 0 00-.364 1.118l1.07 3.292c.3.921-.755 1.688-1.54 1.118l-2.8-2.034a1 1 0 00-1.175 0l-2.8 2.034c-.784.57-1.838-.197-1.539-1.118l1.07-3.292a1 1 0 00-.364-1.118L2.98 8.72c-.783-.57-.38-1.81.588-1.81h3.461a1 1 0 00.951-.69l1.07-3.292z"
              />
            </svg>
          )}
          {/* Пустые звезды */}
          {[...Array(emptyStars)].map((_, i) => (
            <svg
              key={`empty-${i}`}
              className="w-5 h-5 text-gray-300 fill-current"
              viewBox="0 0 20 20"
              aria-hidden="true"
            >
              <path d="M9.049 2.927c.3-.921 1.603-.921 1.902 0l1.07 3.292a1 1 0 00.95.69h3.462c.969 0 1.371 1.24.588 1.81l-2.8 2.034a1 1 0 00-.364 1.118l1.07 3.292c.3.921-.755 1.688-1.54 1.118l-2.8-2.034a1 1 0 00-1.175 0l-2.8 2.034c-.784.57-1.838-.197-1.539-1.118l1.07-3.292a1 1 0 00-.364-1.118L2.98 8.72c-.783-.57-.38-1.81.588-1.81h3.461a1 1 0 00.951-.69l1.07-3.292z" />
            </svg>
          ))}
        </div>
        {product.reviews_count !== undefined && product.reviews_count > 0 && (
          <span className="text-sm text-neutral-600">
            ({product.reviews_count} {product.reviews_count === 1 ? 'отзыв' : 'отзывов'})
          </span>
        )}
      </div>
    );
  };

  return (
    <div className="space-y-4">
      {/* Название товара */}
      <h1 className="text-3xl font-bold text-neutral-900 leading-tight">{product.name}</h1>

      {/* Бренд */}
      <div className="flex items-center gap-4 text-base text-neutral-600">
        {product.brand && (
          <span>
            Бренд: <span className="font-medium">{product.brand}</span>
          </span>
        )}

      </div>

      {/* Рейтинг */}
      {renderRating()}

      {/* Цена */}
      <div className="py-4">
        <div className="text-4xl font-bold text-neutral-900">
          {formatPrice(displayedPrice, price.currency)}
        </div>
        {canSeeRrp && selectedVariant && parseFloat(selectedVariant.rrp || '0') > 0 && (
          <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-sm">
            {parseFloat(selectedVariant.rrp || '0') > 0 && (
              <span className="text-neutral-500">
                РРЦ:{' '}
                <span className="font-semibold text-neutral-800">
                  {formatPrice(parseFloat(selectedVariant.rrp!), price.currency)}
                </span>
              </span>
            )}
          </div>
        )}
      </div>

      {/* Статус наличия */}
      <div className="inline-block">
        <span className={`px-3 py-1.5 rounded-md text-sm font-medium ${stockStatus.className}`}>
          {stockStatus.label}
        </span>
      </div>
    </div>
  );
}
