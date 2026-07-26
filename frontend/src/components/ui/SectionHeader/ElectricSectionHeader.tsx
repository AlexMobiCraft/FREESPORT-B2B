/**
 * Electric Orange Section Header Component
 *
 * Skewed section header for homepage and catalog pages
 * Features:
 * - Skewed text (-12deg)
 * - Counter-skewed inner text (12deg)
 * - Orange underline
 * - Optional label above
 *
 * @see docs/4-ux-design/00-design-system-migration/02-component-specs.md#section-header
 */

'use client';

import React from 'react';
import { cn } from '@/utils/cn';

// ============================================
// Types
// ============================================

export interface ElectricSectionHeaderProps {
  /** Main title */
  title: string;
  /** Optional label above title */
  label?: string;
  /** Header size */
  size?: 'sm' | 'md' | 'lg';
  /** Text alignment */
  align?: 'left' | 'center';
  /** Show underline */
  showUnderline?: boolean;
  /** Additional class names */
  className?: string;
}

// ============================================
// Size Configurations
// ============================================

const sizeStyles = {
  sm: 'text-lg md:text-xl lg:text-2xl',
  md: 'text-xl md:text-2xl lg:text-3xl',
  lg: 'text-2xl md:text-3xl lg:text-4xl',
};

// ============================================
// Section Header Component
// ============================================

export function ElectricSectionHeader({
  title,
  label,
  size = 'md',
  align = 'left',
  showUnderline = true,
  className,
}: ElectricSectionHeaderProps) {
  return (
    <div className={cn('mb-8 md:mb-10', align === 'center' && 'text-center', className)}>
      {/* Label */}
      {label && (
        <span
          className="text-[var(--color-primary)] text-sm uppercase tracking-wider mb-2 block"
          style={{ fontFamily: "'Inter', sans-serif" }}
        >
          {label}
        </span>
      )}

      {/* Title - Skewed */}
      <h2
        className={cn(
          'font-black uppercase tracking-wide text-[var(--foreground)] inline-block',
          sizeStyles[size],
          showUnderline && 'pb-2 border-b-[3px] border-[var(--color-primary)]'
        )}
        style={{
          fontFamily: "'Roboto Condensed', sans-serif",
          transform: 'skewX(-12deg)',
        }}
      >
        <span style={{ transform: 'skewX(12deg)', display: 'inline-block' }}>{title}</span>
      </h2>
    </div>
  );
}

export default ElectricSectionHeader;
