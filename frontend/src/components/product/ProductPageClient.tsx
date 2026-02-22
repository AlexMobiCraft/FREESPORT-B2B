/**
 * ProductPageClient Component (Story 13.5b)
 * Клиентский компонент для интеграции ProductOptions с ProductGallery и ProductSummary
 *
 * @see docs/stories/epic-13/13.5b.productoptions-api-integration.md
 */

'use client';

import { useState, useCallback } from 'react';
import type { UserRole } from '@/utils/pricing';
import ProductImageGallery from './ProductImageGallery';
import ProductSummary, { type ProductDetailWithVariants } from './ProductSummary';
import ProductSpecs from './ProductSpecs';
import type { ProductVariant } from '@/types/api';

interface ProductPageClientProps {
  /** Данные товара с вариантами */
  product: ProductDetailWithVariants;
  /** Роль пользователя для отображения цены */
  userRole: UserRole;
}

/**
 * ProductPageClient - клиентский компонент страницы товара
 *
 * Управляет состоянием выбранного варианта и синхронизирует
 * ProductGallery с ProductOptions через ProductSummary.
 */
export default function ProductPageClient({ product, userRole }: ProductPageClientProps) {
  // Состояние выбранного варианта для синхронизации между компонентами
  const [selectedVariant, setSelectedVariant] = useState<ProductVariant | null>(null);

  /**
   * Обработчик изменения выбранного варианта
   * Вызывается из ProductSummary при изменении опций
   */
  const handleVariantChange = useCallback((variant: ProductVariant | null) => {
    setSelectedVariant(variant);
  }, []);

  /**
   * Обработчик добавления в корзину
   */
  const handleAddToCart = useCallback((variantId?: number) => {
    // TODO: Интеграция с корзиной (Story 12.2)
    console.log('Add to cart:', variantId);
  }, []);

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 lg:gap-8">
      {/* Left Column: Image Gallery (1/2) */}
      <div className="lg:col-span-1">
        {/* Product Images with Zoom/Lightbox - интегрировано с selectedVariant */}
        <ProductImageGallery
          images={product.images}
          productName={product.name}
          selectedVariant={selectedVariant}
        />

        {/* Product Specifications */}
        <div className="mt-8">
          <ProductSpecs specifications={product.specifications} />
        </div>
      </div>

      {/* Right Column: Product Summary (1/3) - Sticky */}
      <div className="lg:col-span-1">
        <div className="lg:sticky lg:top-24">
          <div className="bg-white rounded-lg border border-neutral-200 p-6">
            <ProductSummary
              product={product}
              userRole={userRole}
              onAddToCart={handleAddToCart}
              onVariantChange={handleVariantChange}
            />
          </div>

          {/* Schema.org Product Structured Data */}
          <script
            type="application/ld+json"
            dangerouslySetInnerHTML={{
              __html: JSON.stringify({
                '@context': 'https://schema.org',
                '@type': 'Product',
                name: product.name,
                image: product.images.map(img => img.image),
                description: product.description,
                sku: product.sku,
                brand: {
                  '@type': 'Brand',
                  name: product.brand,
                },
                offers: {
                  '@type': 'Offer',
                  url: `https://freesport.ru/product/${product.slug}`,
                  priceCurrency: product.price?.currency || 'RUB',
                  price: selectedVariant
                    ? parseFloat(selectedVariant.current_price)
                    : product.price?.retail || 0,
                  availability: selectedVariant
                    ? selectedVariant.is_in_stock
                      ? 'https://schema.org/InStock'
                      : 'https://schema.org/OutOfStock'
                    : product.is_in_stock
                      ? 'https://schema.org/InStock'
                      : product.can_be_ordered
                        ? 'https://schema.org/PreOrder'
                        : 'https://schema.org/OutOfStock',
                },
                aggregateRating: product.rating
                  ? {
                      '@type': 'AggregateRating',
                      ratingValue: product.rating,
                      reviewCount: product.reviews_count || 0,
                    }
                  : undefined,
              }),
            }}
          />
        </div>
      </div>
    </div>
  );
}
