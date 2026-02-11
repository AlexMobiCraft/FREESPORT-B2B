'use client';

/**
 * Product Image Gallery Component (Story 12.1, 13.5b)
 * Галерея изображений товара с поддержкой zoom/lightbox
 * Интегрируется с ProductOptions для обновления изображения при смене цвета
 *
 * @see docs/stories/epic-13/13.5b.productoptions-api-integration.md
 */

import { useState, useEffect } from 'react';
import Image from 'next/image';
import type { ProductImage } from '@/types/api';
import type { ProductVariant } from '@/types/api';
import { normalizeImageUrl } from '@/utils/media';

interface ProductImageGalleryProps {
  images: ProductImage[];
  productName: string;
  /** Выбранный вариант товара (для обновления изображения при смене цвета) */
  selectedVariant?: ProductVariant | null;
}

/** Placeholder изображение если нет реальных */
const PLACEHOLDER_IMAGE: ProductImage = {
  image: '/images/No_image.svg',
  alt_text: 'Изображение отсутствует',
  is_primary: true,
};

/** Безопасное получение первого изображения из массива */
function getDefaultImage(imgArray: ProductImage[]): ProductImage {
  if (!imgArray || imgArray.length === 0) return PLACEHOLDER_IMAGE;
  return imgArray.find(img => img.is_primary) || imgArray[0] || PLACEHOLDER_IMAGE;
}

export default function ProductImageGallery({
  images,
  productName,
  selectedVariant,
}: ProductImageGalleryProps) {
  const [selectedImage, setSelectedImage] = useState<ProductImage>(() => getDefaultImage(images));
  const [galleryImages, setGalleryImages] = useState<ProductImage[]>(
    images && images.length > 0 ? images : [PLACEHOLDER_IMAGE]
  );
  const [isLightboxOpen, setIsLightboxOpen] = useState(false);

  /**
   * Обновляет изображения при изменении selectedVariant
   * Если у варианта есть main_image, используем его
   * Иначе показываем базовые изображения товара
   */
  useEffect(() => {
    // Базовые изображения товара (с fallback на placeholder)
    const baseImages = images && images.length > 0 ? images : [PLACEHOLDER_IMAGE];

    if (selectedVariant) {
      if (selectedVariant.main_image) {
        // Создаем ProductImage из main_image варианта
        // Нормализуем URL для корректной работы в Docker
        const variantMainImage: ProductImage = {
          image: normalizeImageUrl(selectedVariant.main_image),
          alt_text:
            `${productName} - ${selectedVariant.color_name || ''} ${selectedVariant.size_value || ''}`.trim(),
          is_primary: true,
        };

        // Если есть gallery_images у варианта, обновляем галерею
        if (selectedVariant.gallery_images && selectedVariant.gallery_images.length > 0) {
          // Фильтруем дубликаты:
          // 1. Исключаем main_image из gallery_images
          // 2. Убираем повторяющиеся URL внутри gallery_images
          const mainImageNormalized = normalizeImageUrl(selectedVariant.main_image);
          const seenUrls = new Set<string>([mainImageNormalized]);

          const variantGallery: ProductImage[] = [];
          selectedVariant.gallery_images.forEach(img => {
            const normalizedImg = normalizeImageUrl(img);
            if (!seenUrls.has(normalizedImg)) {
              seenUrls.add(normalizedImg);
              variantGallery.push({
                image: normalizedImg,
                alt_text: `${productName} - вид ${variantGallery.length + 2}`,
                is_primary: false,
              });
            }
          });

          const newGallery = [variantMainImage, ...variantGallery];
          setGalleryImages(newGallery);
          setSelectedImage(variantMainImage);
        } else {
          // Если у варианта нет галереи, показываем только main_image
          setGalleryImages([variantMainImage]);
          setSelectedImage(variantMainImage);
        }
      } else {
        // Вариант выбран, но у него нет изображения — показываем базовые изображения товара
        setGalleryImages(baseImages);
        setSelectedImage(getDefaultImage(baseImages));
      }
    } else {
      // Вариант не выбран — показываем базовые изображения товара
      setGalleryImages(baseImages);
      setSelectedImage(getDefaultImage(baseImages));
    }
  }, [selectedVariant, images, productName]);

  if (!images || images.length === 0) {
    return (
      <div className="aspect-square bg-neutral-100 flex items-center justify-center rounded-lg border border-neutral-200">
        <span className="text-neutral-400">Изображение отсутствует</span>
      </div>
    );
  }

  const openLightbox = () => {
    setIsLightboxOpen(true);
  };

  const closeLightbox = () => {
    setIsLightboxOpen(false);
  };

  const navigateImage = (direction: 'prev' | 'next') => {
    const currentIndex = galleryImages.findIndex(img => img.image === selectedImage.image);
    let newIndex;

    if (direction === 'prev') {
      newIndex = currentIndex === 0 ? galleryImages.length - 1 : currentIndex - 1;
    } else {
      newIndex = currentIndex === galleryImages.length - 1 ? 0 : currentIndex + 1;
    }

    setSelectedImage(galleryImages[newIndex]);
  };

  return (
    <>
      {/* Main Image */}
      <div className="bg-white rounded-lg border border-neutral-200 overflow-hidden">
        <div
          className="aspect-square relative cursor-zoom-in hover:opacity-90 transition-opacity"
          onClick={openLightbox}
          onKeyDown={e => e.key === 'Enter' && openLightbox()}
          role="button"
          tabIndex={0}
        >
          <Image
            src={selectedImage.image}
            alt={selectedImage.alt_text || productName}
            fill
            sizes="(max-width: 1024px) 100vw, 66vw"
            className="object-contain"
            priority={selectedImage.is_primary}
          />
          {/* Zoom hint icon */}
          <div className="absolute top-4 right-4 bg-white/80 backdrop-blur-sm rounded-full p-2 shadow-sm">
            <svg
              className="w-5 h-5 text-neutral-600"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0zM10 7v3m0 0v3m0-3h3m-3 0H7"
              />
            </svg>
          </div>
        </div>
      </div>

      {/* Thumbnails */}
      {galleryImages.length > 1 && (
        <div className="mt-4 grid grid-cols-4 gap-2" data-testid="image-thumbnails">
          {galleryImages.map((image, index) => (
            <button
              key={`${image.image}-${index}`}
              onClick={() => setSelectedImage(image)}
              className={`aspect-square rounded-lg border overflow-hidden transition-all hover:border-primary-500 ${
                image.image === selectedImage.image
                  ? 'border-primary-500 border-2 ring-2 ring-primary-200'
                  : 'border-neutral-200'
              }`}
              aria-label={`Показать изображение ${index + 1}`}
            >
              <div className="relative w-full h-full">
                <Image
                  src={image.image}
                  alt={image.alt_text || `${productName} - вид ${index + 1}`}
                  fill
                  sizes="(max-width: 1024px) 25vw, 15vw"
                  className="object-contain"
                />
              </div>
            </button>
          ))}
        </div>
      )}

      {/* Lightbox Modal */}
      {isLightboxOpen && (
        <div
          className="fixed inset-0 z-50 bg-black/90 flex items-center justify-center"
          onClick={closeLightbox}
          onKeyDown={e => e.key === 'Escape' && closeLightbox()}
          role="dialog"
          aria-modal="true"
          tabIndex={-1}
        >
          {/* Close button */}
          <button
            onClick={closeLightbox}
            className="absolute top-4 right-4 text-white hover:text-neutral-300 transition-colors z-10"
            aria-label="Закрыть"
          >
            <svg className="w-8 h-8" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M6 18L18 6M6 6l12 12"
              />
            </svg>
          </button>

          {/* Previous button */}
          {galleryImages.length > 1 && (
            <button
              onClick={e => {
                e.stopPropagation();
                navigateImage('prev');
              }}
              className="absolute left-4 text-white hover:text-neutral-300 transition-colors z-10"
              aria-label="Предыдущее изображение"
            >
              <svg className="w-10 h-10" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M15 19l-7-7 7-7"
                />
              </svg>
            </button>
          )}

          {/* Image */}
          <div
            className="relative max-w-6xl max-h-[90vh] w-full h-full flex items-center justify-center p-4"
            onClick={e => e.stopPropagation()}
            onKeyDown={e => e.stopPropagation()}
            role="presentation"
          >
            <Image
              src={selectedImage.image}
              alt={selectedImage.alt_text || productName}
              fill
              sizes="90vw"
              className="object-contain"
            />
          </div>

          {/* Next button */}
          {galleryImages.length > 1 && (
            <button
              onClick={e => {
                e.stopPropagation();
                navigateImage('next');
              }}
              className="absolute right-4 text-white hover:text-neutral-300 transition-colors z-10"
              aria-label="Следующее изображение"
            >
              <svg className="w-10 h-10" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M9 5l7 7-7 7"
                />
              </svg>
            </button>
          )}

          {/* Image counter */}
          {galleryImages.length > 1 && (
            <div className="absolute bottom-4 left-1/2 -translate-x-1/2 bg-white/10 backdrop-blur-sm text-white px-4 py-2 rounded-full text-sm">
              {galleryImages.findIndex(img => img.image === selectedImage.image) + 1} /{' '}
              {galleryImages.length}
            </div>
          )}
        </div>
      )}
    </>
  );
}
