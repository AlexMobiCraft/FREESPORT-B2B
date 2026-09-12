/**
 * Skeleton Component
 *
 * Универсальный skeleton loader для отображения loading state:
 * - Поддержка произвольных размеров через className
 * - Shimmer анимация через animate-pulse
 * - Варианты скругления (rounded-sm, rounded-md, rounded-full)
 */

import React from 'react';
import { cn } from '@/utils/cn';

export interface SkeletonProps {
  /** CSS классы для размеров и скругления */
  className?: string;
  /** Ширина (inline style, альтернатива className) */
  width?: string | number;
  /** Высота (inline style, альтернатива className) */
  height?: string | number;
  /** Вариант скругления */
  rounded?: 'none' | 'sm' | 'md' | 'lg' | 'full';
}

const roundedVariants = {
  none: 'rounded-none',
  sm: 'rounded-[var(--radius-sm)]',
  md: 'rounded-[var(--radius-md)]',
  lg: 'rounded-[var(--radius-lg)]',
  full: 'rounded-full',
};

export const Skeleton: React.FC<SkeletonProps> = ({ className, width, height, rounded = 'md' }) => {
  const style: React.CSSProperties = {};

  if (width !== undefined) {
    style.width = typeof width === 'number' ? `${width}px` : width;
  }
  if (height !== undefined) {
    style.height = typeof height === 'number' ? `${height}px` : height;
  }

  return (
    <div
      className={cn('animate-pulse bg-neutral-200', roundedVariants[rounded], className)}
      style={Object.keys(style).length > 0 ? style : undefined}
      aria-hidden="true"
    />
  );
};

Skeleton.displayName = 'Skeleton';
