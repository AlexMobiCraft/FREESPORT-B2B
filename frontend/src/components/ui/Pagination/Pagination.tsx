/**
 * Pagination Component
 * Компонент пагинации с поддержкой навигации и ellipsis для больших страниц
 *
 * @see frontend/docs/design-system.json#components.Pagination
 */

import React from 'react';
import { ChevronLeft, ChevronRight } from 'lucide-react';
import { cn } from '@/utils/cn';

export interface PaginationProps {
  /** Текущая страница (начинается с 1) */
  currentPage: number;
  /** Общее количество страниц */
  totalPages: number;
  /** Callback при изменении страницы */
  onPageChange: (page: number) => void;
  /** Показывать кнопки первая/последняя страница */
  showFirstLast?: boolean;
  /** Максимальное количество видимых страниц (default: 5) */
  maxVisiblePages?: number;
  /** CSS класс */
  className?: string;
}

/**
 * Генерирует массив номеров страниц с ellipsis
 */
const generatePageNumbers = (
  currentPage: number,
  totalPages: number,
  maxVisible: number
): (number | string)[] => {
  // Edge Case: Если страниц меньше или равно maxVisible - показываем все
  if (totalPages <= maxVisible) {
    return Array.from({ length: totalPages }, (_, i) => i + 1);
  }

  const pages: (number | string)[] = [];
  const halfVisible = Math.floor(maxVisible / 2);

  // Всегда показываем первую страницу
  pages.push(1);

  // Edge Case: Текущая страница близко к началу
  if (currentPage <= halfVisible + 1) {
    for (let i = 2; i <= maxVisible - 1; i++) {
      pages.push(i);
    }
    pages.push('ellipsis-end');
    pages.push(totalPages);
  }
  // Edge Case: Текущая страница близко к концу
  else if (currentPage >= totalPages - halfVisible) {
    pages.push('ellipsis-start');
    for (let i = totalPages - maxVisible + 2; i <= totalPages; i++) {
      pages.push(i);
    }
  }
  // Текущая страница в середине
  else {
    pages.push('ellipsis-start');
    for (let i = currentPage - halfVisible + 1; i <= currentPage + halfVisible - 1; i++) {
      pages.push(i);
    }
    pages.push('ellipsis-end');
    pages.push(totalPages);
  }

  return pages;
};

export const Pagination: React.FC<PaginationProps> = ({
  currentPage,
  totalPages,
  onPageChange,
  showFirstLast = false,
  maxVisiblePages = 5,
  className,
}) => {
  // Edge Case: Невалидные значения
  if (totalPages <= 0 || currentPage < 1 || currentPage > totalPages) {
    return null;
  }

  // Edge Case: Только одна страница - не показываем пагинацию
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

  return (
    <nav aria-label="Pagination" className={cn('flex items-center justify-center', className)}>
      <ul className="flex items-center gap-2">
        {/* First Page Button (optional) */}
        {showFirstLast && (
          <li>
            <button
              onClick={() => handlePageChange(1)}
              disabled={isFirstPage}
              aria-label="Первая страница"
              className={cn(
                'flex items-center justify-center w-10 h-10 rounded-sm',
                'text-body-s font-medium transition-colors duration-short',
                'focus:outline-none focus:ring-2 focus:ring-primary focus:ring-offset-2',
                isFirstPage
                  ? 'text-neutral-500 cursor-not-allowed opacity-50'
                  : 'text-primary hover:bg-neutral-200'
              )}
            >
              <ChevronLeft className="w-4 h-4" />
              <ChevronLeft className="w-4 h-4 -ml-3" />
            </button>
          </li>
        )}

        {/* Previous Page Button */}
        <li>
          <button
            onClick={() => handlePageChange(currentPage - 1)}
            disabled={isFirstPage}
            aria-label="Предыдущая страница"
            className={cn(
              'flex items-center justify-center w-10 h-10 rounded-sm',
              'text-body-s font-medium transition-colors duration-short',
              'focus:outline-none focus:ring-2 focus:ring-primary focus:ring-offset-2',
              isFirstPage
                ? 'text-neutral-500 cursor-not-allowed opacity-50'
                : 'text-primary hover:bg-neutral-200'
            )}
          >
            <ChevronLeft className="w-4 h-4" aria-hidden="true" />
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
                <span className="flex items-center justify-center w-10 h-10 text-body-s text-neutral-600">
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
                className={cn(
                  'flex items-center justify-center w-10 h-10 rounded-sm',
                  'text-body-s font-medium transition-colors duration-short',
                  'focus:outline-none focus:ring-2 focus:ring-primary focus:ring-offset-2',
                  isActive
                    ? 'bg-primary text-text-inverse'
                    : 'bg-transparent text-primary hover:bg-neutral-200'
                )}
              >
                {page}
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
            className={cn(
              'flex items-center justify-center w-10 h-10 rounded-sm',
              'text-body-s font-medium transition-colors duration-short',
              'focus:outline-none focus:ring-2 focus:ring-primary focus:ring-offset-2',
              isLastPage
                ? 'text-neutral-500 cursor-not-allowed opacity-50'
                : 'text-primary hover:bg-neutral-200'
            )}
          >
            <ChevronRight className="w-4 h-4" aria-hidden="true" />
          </button>
        </li>

        {/* Last Page Button (optional) */}
        {showFirstLast && (
          <li>
            <button
              onClick={() => handlePageChange(totalPages)}
              disabled={isLastPage}
              aria-label="Последняя страница"
              className={cn(
                'flex items-center justify-center w-10 h-10 rounded-sm',
                'text-body-s font-medium transition-colors duration-short',
                'focus:outline-none focus:ring-2 focus:ring-primary focus:ring-offset-2',
                isLastPage
                  ? 'text-neutral-500 cursor-not-allowed opacity-50'
                  : 'text-primary hover:bg-neutral-200'
              )}
            >
              <ChevronRight className="w-4 h-4" />
              <ChevronRight className="w-4 h-4 -ml-3" />
            </button>
          </li>
        )}
      </ul>
    </nav>
  );
};

Pagination.displayName = 'Pagination';
