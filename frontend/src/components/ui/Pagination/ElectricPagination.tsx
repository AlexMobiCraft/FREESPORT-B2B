/**
 * Electric Orange Pagination Component
 *
 * Пагинация в стиле Electric Orange
 * Features:
 * - Skewed buttons (-12deg)
 * - Orange active state with glow
 * - Dark theme colors
 *
 * @see docs/4-ux-design/00-design-system-migration/02-component-specs.md
 */

'use client';

import React from 'react';
import { ChevronLeft, ChevronRight } from 'lucide-react';
import { cn } from '@/utils/cn';

// ============================================
// Types
// ============================================

export interface ElectricPaginationProps {
  /** Current page (1-indexed) */
  currentPage: number;
  /** Total number of pages */
  totalPages: number;
  /** Callback when page changes */
  onPageChange: (page: number) => void;
  /** Max visible page numbers (default: 5) */
  maxVisiblePages?: number;
  /** Additional class names */
  className?: string;
}

// ============================================
// Helpers
// ============================================

const generatePageNumbers = (
  currentPage: number,
  totalPages: number,
  maxVisible: number
): (number | string)[] => {
  if (totalPages <= maxVisible) {
    return Array.from({ length: totalPages }, (_, i) => i + 1);
  }

  const pages: (number | string)[] = [];
  const halfVisible = Math.floor(maxVisible / 2);

  pages.push(1);

  if (currentPage <= halfVisible + 1) {
    for (let i = 2; i <= maxVisible - 1; i++) {
      pages.push(i);
    }
    pages.push('ellipsis-end');
    pages.push(totalPages);
  } else if (currentPage >= totalPages - halfVisible) {
    pages.push('ellipsis-start');
    for (let i = totalPages - maxVisible + 2; i <= totalPages; i++) {
      pages.push(i);
    }
  } else {
    pages.push('ellipsis-start');
    for (let i = currentPage - halfVisible + 1; i <= currentPage + halfVisible - 1; i++) {
      pages.push(i);
    }
    pages.push('ellipsis-end');
    pages.push(totalPages);
  }

  return pages;
};

// ============================================
// Component
// ============================================

export function ElectricPagination({
  currentPage,
  totalPages,
  onPageChange,
  maxVisiblePages = 5,
  className,
}: ElectricPaginationProps) {
  // Validation
  if (totalPages <= 0 || currentPage < 1 || currentPage > totalPages) {
    return null;
  }

  if (totalPages === 1) {
    return null;
  }

  const pages = generatePageNumbers(currentPage, totalPages, maxVisiblePages);
  const isFirstPage = currentPage === 1;
  const isLastPage = currentPage === totalPages;

  const handlePageChange = (page: number) => {
    if (page >= 1 && page <= totalPages && page !== currentPage) {
      onPageChange(page);
    }
  };

  // Skewed button styles
  const baseButtonStyles = cn(
    'flex items-center justify-center',
    'w-8 h-8 sm:w-10 sm:h-10',
    'font-medium text-xs sm:text-sm',
    'transition-all duration-200',
    'transform -skew-x-12',
    'focus:outline-none focus:ring-2 focus:ring-[var(--color-primary)] focus:ring-offset-2 focus:ring-offset-[var(--bg-body)]'
  );

  const activeStyles = cn('bg-[var(--color-primary)] text-black', 'shadow-[var(--shadow-glow)]');

  const inactiveStyles = cn(
    'bg-transparent border border-[var(--border-default)] text-[var(--foreground)]',
    'hover:border-[var(--color-primary)] hover:text-[var(--color-primary)]'
  );

  const disabledStyles = cn(
    'text-[var(--color-text-muted)] border border-[var(--border-default)]',
    'cursor-not-allowed opacity-50'
  );

  return (
    <nav aria-label="Pagination" className={cn('flex items-center justify-center', className)}>
      <ul className="flex items-center gap-2">
        {/* Previous Page Button */}
        <li>
          <button
            onClick={() => handlePageChange(currentPage - 1)}
            disabled={isFirstPage}
            aria-label="Предыдущая страница"
            className={cn(baseButtonStyles, isFirstPage ? disabledStyles : inactiveStyles)}
          >
            <span className="transform skew-x-12">
              <ChevronLeft className="w-5 h-5" aria-hidden="true" />
            </span>
          </button>
        </li>

        {/* Page Numbers */}
        {pages.map((page, index) => {
          const isEllipsis = typeof page === 'string';
          const isActive = page === currentPage;
          const key = isEllipsis ? `${page}-${index}` : `page-${page}`;

          if (isEllipsis) {
            return (
              <li key={key} aria-hidden="true">
                <span className="flex items-center justify-center w-10 h-10 text-[var(--color-text-muted)]">
                  &hellip;
                </span>
              </li>
            );
          }

          return (
            <li key={key}>
              <button
                onClick={() => handlePageChange(page as number)}
                aria-label={`Страница ${page}`}
                aria-current={isActive ? 'page' : undefined}
                className={cn(baseButtonStyles, isActive ? activeStyles : inactiveStyles)}
              >
                <span className="transform skew-x-12">{page}</span>
              </button>
            </li>
          );
        })}

        {/* Next Page Button */}
        <li>
          <button
            onClick={() => handlePageChange(currentPage + 1)}
            disabled={isLastPage}
            aria-label="Следующая страница"
            className={cn(baseButtonStyles, isLastPage ? disabledStyles : inactiveStyles)}
          >
            <span className="transform skew-x-12">
              <ChevronRight className="w-5 h-5" aria-hidden="true" />
            </span>
          </button>
        </li>
      </ul>
    </nav>
  );
}

ElectricPagination.displayName = 'ElectricPagination';

export default ElectricPagination;
