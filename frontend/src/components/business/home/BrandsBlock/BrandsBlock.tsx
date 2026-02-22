'use client';

import React, { useState } from 'react';
import Image from 'next/image';
import Link from 'next/link';
import useEmblaCarousel from 'embla-carousel-react';
import Autoplay from 'embla-carousel-autoplay';
import { motion } from 'motion/react';
import type { Brand } from '@/types/api';

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const BRAND_CARD_IDLE_OPACITY = 'opacity-80';

const BREAKPOINTS = {
  SM: '(min-width: 640px)',
  LG: '(min-width: 1024px)',
};

// ---------------------------------------------------------------------------
// BrandCard (internal)
// ---------------------------------------------------------------------------

interface BrandCardProps {
  brand: Brand;
}

const BrandCard: React.FC<BrandCardProps> = ({ brand }) => {
  const [hasError, setHasError] = useState(false);

  if (!brand.image || hasError) return null;

  return (
    <Link
      href={`/catalog?brand=${brand.slug}`}
      aria-label={brand.name}
      className="outline-none"
    >
      <motion.div
        whileHover={{ scale: 1.05, opacity: 1 }}
        whileFocus={{ scale: 1.05, opacity: 1 }}
        transition={{ duration: 0.2 }}
        className={`relative h-20 md:h-24 px-4 ${BRAND_CARD_IDLE_OPACITY}`}
      >
        <Image
          src={brand.image}
          alt={brand.name}
          fill
          sizes="(max-width: 640px) 80px, (max-width: 1024px) 100px, 120px"
          className="object-contain"
          onError={() => setHasError(true)}
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
  const visibleBrands = brands.filter((b) => b.image);

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
          {visibleBrands.map((brand) => (
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
