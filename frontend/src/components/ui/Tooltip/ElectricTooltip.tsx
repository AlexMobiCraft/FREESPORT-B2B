/**
 * Electric Orange Tooltip Component
 *
 * Всплывающие подсказки в стиле Electric Orange
 * Features:
 * - Skewed container (-12deg)
 * - Dark background with subtle border
 * - Skewed arrow pointing to trigger
 * - Appears on hover
 *
 * @see docs/4-ux-design/00-design-system-migration/02-component-specs.md
 */

'use client';

import React, { useState, useRef, useCallback } from 'react';
import { cn } from '@/utils/cn';

// ============================================
// Types
// ============================================

export type ElectricTooltipPosition = 'top' | 'bottom' | 'left' | 'right';

export interface ElectricTooltipProps {
  /** Tooltip content */
  content: React.ReactNode;
  /** Trigger element */
  children: React.ReactNode;
  /** Position relative to trigger */
  position?: ElectricTooltipPosition;
  /** Delay before showing (ms) */
  delay?: number;
  /** Additional class names for wrapper */
  className?: string;
}

// ============================================
// Component
// ============================================

export function ElectricTooltip({
  content,
  children,
  position = 'top',
  delay = 200,
  className,
}: ElectricTooltipProps) {
  const [isVisible, setIsVisible] = useState(false);
  const timeoutRef = useRef<NodeJS.Timeout | null>(null);

  const showTooltip = useCallback(() => {
    timeoutRef.current = setTimeout(() => {
      setIsVisible(true);
    }, delay);
  }, [delay]);

  const hideTooltip = useCallback(() => {
    if (timeoutRef.current) {
      clearTimeout(timeoutRef.current);
      timeoutRef.current = null;
    }
    setIsVisible(false);
  }, []);

  // Position classes
  const positionClasses = {
    top: 'bottom-full left-1/2 -translate-x-1/2 mb-2',
    bottom: 'top-full left-1/2 -translate-x-1/2 mt-2',
    left: 'right-full top-1/2 -translate-y-1/2 mr-2',
    right: 'left-full top-1/2 -translate-y-1/2 ml-2',
  };

  // Arrow position classes
  const arrowClasses = {
    top: 'top-full left-1/2 -translate-x-1/2 border-t-[var(--bg-card)] border-x-transparent border-b-transparent',
    bottom:
      'bottom-full left-1/2 -translate-x-1/2 border-b-[var(--bg-card)] border-x-transparent border-t-transparent',
    left: 'left-full top-1/2 -translate-y-1/2 border-l-[var(--bg-card)] border-y-transparent border-r-transparent',
    right:
      'right-full top-1/2 -translate-y-1/2 border-r-[var(--bg-card)] border-y-transparent border-l-transparent',
  };

  return (
    <div
      role="group"
      className={cn('relative inline-block', className)}
      onMouseEnter={showTooltip}
      onMouseLeave={hideTooltip}
      onFocus={showTooltip}
      onBlur={hideTooltip}
    >
      {/* Trigger */}
      {children}

      {/* Tooltip */}
      {isVisible && (
        <div
          role="tooltip"
          className={cn(
            'absolute z-50',
            'px-3 py-2',
            'bg-[var(--bg-card)] border border-[var(--border-default)]',
            'text-[var(--color-text-secondary)] text-xs',
            'whitespace-nowrap',
            'transform -skew-x-12',
            'shadow-[0_4px_12px_rgba(0,0,0,0.4)]',
            'animate-fadeIn',
            positionClasses[position]
          )}
        >
          {/* Content - Counter-skewed */}
          <span className="transform skew-x-12 inline-block">{content}</span>

          {/* Arrow */}
          <span className={cn('absolute w-0 h-0', 'border-4', arrowClasses[position])} />
        </div>
      )}
    </div>
  );
}

ElectricTooltip.displayName = 'ElectricTooltip';

export default ElectricTooltip;
