/**
 * Electric Orange Breadcrumbs Component
 *
 * Линейная навигация в стиле Electric Orange
 * Features:
 * - Straight text (0deg) - для читаемости
 * - Orange hover color (#FF6B00)
 * - Chevron separators
 *
 * @see docs/4-ux-design/00-design-system-migration/02-component-specs.md
 */

'use client';

import React from 'react';
import Link from 'next/link';
import { ChevronRight, Home } from 'lucide-react';
import { cn } from '@/utils/cn';

// ============================================
// Types
// ============================================

export interface ElectricBreadcrumbItem {
  label: string;
  href?: string;
}

export interface ElectricBreadcrumbsProps {
  /** Breadcrumb items */
  items: ElectricBreadcrumbItem[];
  /** Show home icon for first item */
  showHomeIcon?: boolean;
  /** Additional class names */
  className?: string;
}

// ============================================
// Component
// ============================================

export function ElectricBreadcrumbs({
  items,
  showHomeIcon = true,
  className,
}: ElectricBreadcrumbsProps) {
  // Collapse if more than 5 items
  const shouldCollapse = items.length > 5;
  const displayItems = shouldCollapse ? [items[0], { label: '...' }, ...items.slice(-2)] : items;

  return (
    <nav
      aria-label="Breadcrumb"
      className={cn('flex items-center gap-2', 'font-inter text-sm', className)}
    >
      <ol className="flex items-center gap-2">
        {displayItems.map((item, index) => {
          const isFirst = index === 0;
          const isLast = index === displayItems.length - 1;
          const isEllipsis = item.label === '...';

          return (
            <li key={`${item.label}-${index}`} className="flex items-center gap-2">
              {/* Breadcrumb Item */}
              {item.href && !isLast && !isEllipsis ? (
                <Link
                  href={item.href}
                  className={cn(
                    'flex items-center gap-1.5',
                    'text-[var(--color-text-secondary)]',
                    'hover:text-[var(--color-primary)] transition-colors duration-200',
                    'max-w-[150px] truncate'
                  )}
                  title={item.label}
                >
                  {isFirst && showHomeIcon && <Home className="w-4 h-4 flex-shrink-0" />}
                  <span>{item.label}</span>
                </Link>
              ) : (
                <span
                  className={cn(
                    'flex items-center gap-1.5',
                    isLast
                      ? 'text-[var(--foreground)] font-medium'
                      : 'text-[var(--color-text-secondary)]',
                    isEllipsis && 'cursor-help',
                    !isLast && !isEllipsis && 'max-w-[150px] truncate'
                  )}
                  title={
                    isEllipsis
                      ? items
                          .slice(1, -2)
                          .map(i => i.label)
                          .join(' > ')
                      : item.label
                  }
                  aria-current={isLast ? 'page' : undefined}
                >
                  {isFirst && showHomeIcon && !item.href && (
                    <Home className="w-4 h-4 flex-shrink-0" />
                  )}
                  {item.label}
                </span>
              )}

              {/* Separator - Chevron */}
              {!isLast && (
                <ChevronRight
                  className="w-4 h-4 text-[var(--color-text-muted)] flex-shrink-0"
                  aria-hidden="true"
                />
              )}
            </li>
          );
        })}
      </ol>
    </nav>
  );
}

ElectricBreadcrumbs.displayName = 'ElectricBreadcrumbs';

export default ElectricBreadcrumbs;
