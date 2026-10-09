/**
 * Electric Orange Badge Component
 *
 * Skewed badge for product labels, notifications, tags
 * Features:
 * - Skewed geometry (-12deg)
 * - Counter-skewed text (12deg)
 * - Multiple variants (primary, sale, new, hit)
 *
 * @see docs/4-ux-design/00-design-system-migration/02-component-specs.md#badge
 */

'use client';

import React from 'react';
import { cn } from '@/utils/cn';

// ============================================
// Types
// ============================================

export interface ElectricBadgeProps {
  /** Badge variant */
  variant?: 'primary' | 'sale' | 'new' | 'hit' | 'outline';
  /** Badge size */
  size?: 'sm' | 'md';
  /** Badge content */
  children: React.ReactNode;
  /** Additional class names */
  className?: string;
}

// ============================================
// Variant Styles
// ============================================

const variantStyles = {
  primary: 'bg-[var(--color-primary)] text-black',
  sale: 'bg-[var(--color-danger)] text-white',
  new: 'bg-[var(--color-text-primary)] text-black',
  hit: 'bg-[var(--color-success)] text-black',
  outline: 'bg-transparent border-2 border-[var(--color-primary)] text-[var(--color-primary)]',
};

const sizeStyles = {
  sm: 'px-2 py-0.5 text-[10px]',
  md: 'px-3 py-1 text-xs',
};

// ============================================
// Badge Component
// ============================================

export function ElectricBadge({
  variant = 'primary',
  size = 'md',
  children,
  className,
}: ElectricBadgeProps) {
  return (
    <span
      className={cn(
        // Base styles
        'inline-flex items-center font-bold uppercase tracking-wider',

        // Variant
        variantStyles[variant],

        // Size
        sizeStyles[size],

        className
      )}
      style={{
        fontFamily: "'Roboto Condensed', sans-serif",
        transform: 'skewX(-12deg)',
      }}
    >
      <span style={{ transform: 'skewX(12deg)', display: 'inline-block' }}>{children}</span>
    </span>
  );
}

export default ElectricBadge;
