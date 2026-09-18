/**
 * Electric Orange Features Block Component
 *
 * Блок преимуществ в стиле Electric Orange
 * Features:
 * - Grid layout (3-4 columns)
 * - Skewed icon containers
 * - Skewed titles (-12deg) in orange
 * - Dark theme
 *
 * @see docs/4-ux-design/00-design-system-migration/02-component-specs.md
 */

'use client';

import React from 'react';
import { cn } from '@/utils/cn';
import { Truck, Shield, RefreshCcw, Headphones, type LucideIcon } from 'lucide-react';

// ============================================
// Types
// ============================================

export interface ElectricFeatureItem {
  id: string;
  icon: LucideIcon;
  title: string;
  description: string;
}

export interface ElectricFeaturesBlockProps {
  /** Feature items (defaults to defaultFeatures) */
  items?: ElectricFeatureItem[];
  /** Columns count (auto, 2, 3, 4) */
  columns?: 'auto' | 2 | 3 | 4;
  /** Additional class names */
  className?: string;
}

// ============================================
// Default Features
// ============================================

export const defaultFeatures: ElectricFeatureItem[] = [
  {
    id: 'delivery',
    icon: Truck,
    title: 'Быстрая доставка',
    description: 'По всей России от 2-х дней',
  },
  {
    id: 'quality',
    icon: Shield,
    title: 'Гарантия качества',
    description: 'Только оригинальные бренды',
  },
  {
    id: 'return',
    icon: RefreshCcw,
    title: '30 дней на возврат',
    description: 'Если товар вам не подошел',
  },
  {
    id: 'support',
    icon: Headphones,
    title: 'Поддержка 24/7',
    description: 'Всегда на связи для вас',
  },
];

// ============================================
// Component
// ============================================

export function ElectricFeaturesBlock({
  items = defaultFeatures,
  columns = 'auto',
  className,
}: ElectricFeaturesBlockProps) {
  const gridClasses = {
    auto: 'grid-cols-1 sm:grid-cols-2 lg:grid-cols-4',
    2: 'grid-cols-1 sm:grid-cols-2',
    3: 'grid-cols-1 sm:grid-cols-2 lg:grid-cols-3',
    4: 'grid-cols-1 sm:grid-cols-2 lg:grid-cols-4',
  };

  return (
    <section className={cn('py-16 border-y border-[var(--border-default)]', className)}>
      <div className="max-w-[1200px] mx-auto px-5">
        <div className={cn('grid gap-10', gridClasses[columns])}>
          {items.map(item => {
            const Icon = item.icon;

            return (
              <div key={item.id} className="flex flex-col items-center text-center">
                {/* Skewed Icon Container */}
                <div
                  className={cn(
                    'w-14 h-14 mb-4',
                    'flex items-center justify-center',
                    'border border-[var(--color-primary)]',
                    'transform -skew-x-12',
                    'transition-all duration-200',
                    'hover:bg-[var(--color-primary-subtle)]'
                  )}
                >
                  <Icon
                    className="w-6 h-6 text-[var(--color-primary)] transform skew-x-12"
                    strokeWidth={1.5}
                  />
                </div>

                {/* Title - Skewed */}
                <h3 className="font-roboto-condensed font-bold text-lg uppercase text-[var(--color-primary)] mb-2 transform -skew-x-12">
                  <span className="transform skew-x-12 inline-block">{item.title}</span>
                </h3>

                {/* Description - Straight */}
                <p className="text-[var(--color-text-secondary)] text-sm leading-relaxed max-w-[280px]">
                  {item.description}
                </p>
              </div>
            );
          })}
        </div>
      </div>
    </section>
  );
}

ElectricFeaturesBlock.displayName = 'ElectricFeaturesBlock';

export default ElectricFeaturesBlock;
