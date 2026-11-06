/**
 * Electric Orange Spinner Component
 *
 * Индикатор загрузки в стиле Electric Orange
 * Features:
 * - Parallelogram container (skewed -12deg)
 * - Animated bars that progressively fill the container
 * - Bars appear sequentially, then clear and repeat
 *
 * @see docs/4-ux-design/00-design-system-migration/02-component-specs.md
 */

'use client';

import React from 'react';
import { cn } from '@/utils/cn';

// ============================================
// Types
// ============================================

export type ElectricSpinnerSize = 'sm' | 'md' | 'lg';

export interface ElectricSpinnerProps {
  /** Spinner size */
  size?: ElectricSpinnerSize;
  /** Additional class names */
  className?: string;
}

// ============================================
// Size Configuration
// ============================================

const sizeConfig: Record<
  ElectricSpinnerSize,
  { container: string; barCount: number; barWidth: string; gap: string }
> = {
  sm: { container: 'w-8 h-4', barCount: 5, barWidth: '3px', gap: '2px' },
  md: { container: 'w-12 h-6', barCount: 6, barWidth: '4px', gap: '3px' },
  lg: { container: 'w-16 h-8', barCount: 7, barWidth: '5px', gap: '4px' },
};

// ============================================
// Component
// ============================================

export function ElectricSpinner({ size = 'md', className }: ElectricSpinnerProps) {
  const config = sizeConfig[size];

  return (
    <div
      role="status"
      aria-label="Загрузка"
      className={cn(
        'inline-flex items-center justify-center',
        config.container,
        'transform -skew-x-12',
        'overflow-hidden',
        className
      )}
      style={{ gap: config.gap }}
    >
      {/* Skewed bars that animate sequentially */}
      {Array.from({ length: config.barCount }).map((_, index) => (
        <span
          key={index}
          className="electric-spinner-bar"
          style={{
            width: config.barWidth,
            height: '100%',
            backgroundColor: 'var(--color-primary)',
            animationDelay: `${index * 150}ms`,
          }}
        />
      ))}
      <span className="sr-only">Загрузка...</span>
    </div>
  );
}

ElectricSpinner.displayName = 'ElectricSpinner';

// ============================================
// Full Page Loading
// ============================================

export interface ElectricLoadingProps {
  /** Loading text */
  text?: string;
  /** Additional class names */
  className?: string;
}

export function ElectricLoading({ text = 'Загрузка...', className }: ElectricLoadingProps) {
  return (
    <div className={cn('flex flex-col items-center justify-center gap-4', className)}>
      <ElectricSpinner size="lg" />
      <span className="text-[var(--color-text-secondary)] text-sm">{text}</span>
    </div>
  );
}

ElectricLoading.displayName = 'ElectricLoading';

export default ElectricSpinner;
