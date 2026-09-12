/**
 * CategoryCard Component
 *
 * Карточка категории для блока "Категории" на главной странице (Story 12.7)
 *
 * @example
 * ```tsx
 * <CategoryCard
 *   name="Футбол"
 *   image="/images/categories/football.jpg"
 *   href="/catalog/football"
 * />
 * ```
 */

import React from 'react';
import Link from 'next/link';
import Image from 'next/image';

export interface CategoryCardProps {
  name: string;
  image: string;
  href: string;
  alt?: string;
}

export const CategoryCard: React.FC<CategoryCardProps> = ({ name, image, href, alt = name }) => {
  return (
    <Link
      href={href}
      className="group block rounded-2xl shadow-default hover:shadow-hover hover:-translate-y-0.5 transition-all duration-[180ms] ease-in-out overflow-hidden bg-white focus:outline-none focus:ring-2 focus:ring-primary focus:ring-offset-2"
    >
      {/* Изображение категории */}
      <div className="relative aspect-square overflow-hidden">
        <Image
          src={image}
          alt={alt}
          fill
          className="object-cover group-hover:scale-105 transition-transform duration-[180ms] ease-in-out"
          sizes="(max-width: 640px) 100vw, (max-width: 1024px) 50vw, 20vw"
        />
      </div>

      {/* Название категории */}
      <div className="p-4">
        <h3 className="text-xl font-semibold text-primary text-center">{name}</h3>
      </div>
    </Link>
  );
};

CategoryCard.displayName = 'CategoryCard';
