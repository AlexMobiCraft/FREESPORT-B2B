/**
 * ElectricCategorySection Component
 *
 * Секция "Популярные категории" для главной страницы Electric Orange Theme.
 * 4 статические категории с фиксированными изображениями.
 *
 * Design System: Electric Orange v2.3.0
 * - Grid layout: 2x2 на desktop, 2 на tablet, 1 на mobile
 * - Square cards (aspect-ratio 1:1)
 * - Grayscale → Color hover effect
 */

'use client';

import React from 'react';
import Link from 'next/link';
import { ElectricCategoryCard } from '@/components/ui/CategoryCard/ElectricCategoryCard';
import { ElectricButton } from '@/components/ui/Button/ElectricButton';

// Статические категории с конкретными изображениями
const CATEGORIES = [
  {
    id: 1,
    title: 'ЕДИНОБОРСТВА',
    slug: 'edinoborstva',
    image: '/electric-orange/img/bags.jpg',
  },
  {
    id: 2,
    title: 'ФИТНЕС И АТЛЕТИКА',
    slug: 'fitnes-i-atletika',
    image: '/electric-orange/img/photo-1534438327276-14e5300c3a48.avif',
  },
  {
    id: 3,
    title: 'ГИМНАСТИКА & ТАНЦЫ',
    slug: 'gimnastika-i-tantsy',
    image: '/electric-orange/img/Gemini_Generated_Image_k7t8bpk7t8bpk7t8.png',
  },
  {
    id: 4,
    title: 'СПОРТИВНЫЕ ИГРЫ',
    slug: 'sportivnye-igry',
    image: '/electric-orange/img/Gemini_Generated_Image_36n5hd36n5hd36n5.png',
  },
];

export const ElectricCategorySection: React.FC = () => {
  return (
    <section
      className="max-w-[1400px] mx-auto px-4 sm:px-6 lg:px-8 py-12"
      aria-labelledby="categories-heading"
    >
      {/* Header row */}
      <div className="flex items-center justify-between mb-8">
        {/* Skewed title */}
        <h2
          id="categories-heading"
          className="text-2xl md:text-3xl font-black uppercase tracking-tight text-[var(--color-text-primary)]"
          style={{
            fontFamily: "'Roboto Condensed', sans-serif",
            transform: 'skewX(-12deg)',
            transformOrigin: 'left',
          }}
        >
          <span style={{ display: 'inline-block', transform: 'skewX(12deg)' }}>
            ПОПУЛЯРНЫЕ КАТЕГОРИИ
          </span>
        </h2>

        {/* View all link */}
        <Link href="/electric/catalog">
          <ElectricButton variant="outline" size="sm">
            Все категории
          </ElectricButton>
        </Link>
      </div>

      {/* Categories grid - 4 columns on desktop */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5" role="list">
        {CATEGORIES.map(category => (
          <div key={category.id} role="listitem">
            <ElectricCategoryCard
              title={category.title}
              image={category.image}
              href={`/electric/catalog?category=${category.slug}`}
            />
          </div>
        ))}
      </div>
    </section>
  );
};

ElectricCategorySection.displayName = 'ElectricCategorySection';

export default ElectricCategorySection;
