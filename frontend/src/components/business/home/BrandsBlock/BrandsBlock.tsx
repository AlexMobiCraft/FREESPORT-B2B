'use client';

import React, { useState } from 'react';
import Image from 'next/image';
import Link from 'next/link';
import useEmblaCarousel from 'embla-carousel-react';
import Autoplay from 'embla-carousel-autoplay';
import { motion } from 'motion/react';
import type { Brand } from '@/types/api';
import { normalizeImageUrl } from '@/utils/media';

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const BRAND_CARD_IDLE_OPACITY = 'opacity-80';

const BREAKPOINTS = {
  SM: '(min-width: 640px)',
  LG: '(min-width: 1024px)',
};

const BRAND_IMAGE_FALLBACK_SRC = '/images/No_image.svg';
const BRAND_IMAGE_MEDIA_PREFIX = '/media/brands/';

function buildStaticBrandFallback(imageUrl: string): string | null {
  if (!imageUrl.startsWith(BRAND_IMAGE_MEDIA_PREFIX)) {
    return null;
  }

  const fileName = imageUrl.split('/').pop();
  if (!fileName || !/_black\.[a-z0-9]+$/i.test(fileName)) {
    return null;
  }

  const staticFileName = fileName.replace(/_black(?=\.[a-z0-9]+$)/i, ' black');
  return `/images/brands/${encodeURIComponent(staticFileName)}`;
}

// ---------------------------------------------------------------------------
// BrandCard (internal)
// ---------------------------------------------------------------------------

interface BrandCardProps {
  brand: Brand;
}

const BrandCard: React.FC<BrandCardProps> = ({ brand }) => {
  const normalizedImage = normalizeImageUrl(brand.image);
  const staticBrandFallback = buildStaticBrandFallback(normalizedImage);
  const [imageSrc, setImageSrc] = useState(normalizedImage);
  const [isStaticFallbackUsed, setIsStaticFallbackUsed] = useState(false);

  if (!brand.image) return null;

  const handleImageError = () => {
    if (!isStaticFallbackUsed && staticBrandFallback && imageSrc !== staticBrandFallback) {
      setImageSrc(staticBrandFallback);
      setIsStaticFallbackUsed(true);
      return;
    }

    if (imageSrc !== BRAND_IMAGE_FALLBACK_SRC) {
      setImageSrc(BRAND_IMAGE_FALLBACK_SRC);
    }
  };

  return (
    <Link href={`/catalog?brand=${brand.slug}`} aria-label={brand.name} className="outline-none">
      <motion.div
        whileHover={{ scale: 1.05, opacity: 1 }}
        whileFocus={{ scale: 1.05, opacity: 1 }}
        transition={{ duration: 0.2 }}
        className={`relative h-20 md:h-24 px-4 ${BRAND_CARD_IDLE_OPACITY}`}
      >
        <Image
          src={imageSrc}
          alt={brand.name}
          fill
          sizes="(max-width: 640px) 80px, (max-width: 1024px) 100px, 120px"
          className="object-contain"
          onError={handleImageError}
        />
      </motion.div>
    </Link>
  );
};

// ---------------------------------------------------------------------------
// BrandsBlock
// ---------------------------------------------------------------------------

export interface BrandsBlockProps {
  brands: Brand[];
}

export const BrandsBlock: React.FC<BrandsBlockProps> = ({ brands }) => {
  const visibleBrands = brands.filter(b => b.image);

  const [emblaRef] = useEmblaCarousel(
    {
      align: 'start',
      loop: visibleBrands.length > 1,
      slidesToScroll: 1,
      dragFree: true,
      breakpoints: {
        [BREAKPOINTS.SM]: { slidesToScroll: 2 },
        [BREAKPOINTS.LG]: { slidesToScroll: 3 },
      },
    },
    visibleBrands.length > 1
      ? [
          Autoplay({
            delay: 3000,
            stopOnInteraction: true,
            stopOnMouseEnter: true,
          }),
        ]
      : []
  );

  if (visibleBrands.length === 0) return null;

  return (
    <section
      aria-label="Популярные бренды"
      data-testid="brands-block"
      className="max-w-[1280px] mx-auto px-3 md:px-4 lg:px-6 py-6 md:py-8"
    >
      <div ref={emblaRef} className="overflow-hidden">
        <div className="flex">
          {visibleBrands.map(brand => (
            <div
              key={brand.id}
              className="flex-[0_0_33.333%] sm:flex-[0_0_25%] md:flex-[0_0_20%] lg:flex-[0_0_16.666%] min-w-0"
            >
              <BrandCard brand={brand} />
            </div>
          ))}
        </div>
      </div>
    </section>
  );
};
