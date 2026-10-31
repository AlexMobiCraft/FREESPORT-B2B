/**
 * Pagination Component
 * Компонент пагинации плитками: номера страниц, многоточие и стрелки.
 * При выборе страницы плавно возвращает окно к началу страницы.
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

/** Общий вид плитки: номер, стрелка и ячейка многоточия одного размера */
const TILE_BASE = 'flex h-10 min-w-10 items-center justify-center rounded-sm px-2 sm:min-w-12';

/** Интерактивная плитка: шрифт и фокус */
const TILE_BUTTON = cn(
  TILE_BASE,
  'text-sm font-medium transition-colors duration-short',
  'focus:outline-none focus:ring-2 focus:ring-primary focus:ring-offset-2'
);

/** Плитка номера или стрелки в обычном состоянии */
const TILE_IDLE =
  'bg-primary-subtle text-primary hover:bg-primary hover:text-text-inverse disabled:cursor-not-allowed disabled:opacity-50 disabled:hover:bg-primary-subtle disabled:hover:text-primary';

/**
 * Генерирует ряд номеров страниц: числа и 'ellipsis' на месте разрыва.
 *
 * Ряд — множество номеров (W = maxVisible, mid = ceil(N / 2)). Разрыв в одну
 * страницу заполняется её номером, разрыв от двух — многоточием.
 * В начальной ветке многоточие ставится только на первый разрыв
 * (разрыв «середина → последняя» не помечается, как на макете).
 */
const generatePageNumbers = (
  currentPage: number,
  totalPages: number,
  maxVisible: number
): (number | 'ellipsis')[] => {
  // Edge Case: страниц немного — показываем все
  if (totalPages <= maxVisible + 2) {
    return Array.from({ length: totalPages }, (_, i) => i + 1);
  }

  const mid = Math.ceil(totalPages / 2);
  const half = Math.floor(maxVisible / 2);
  const isStartBranch = currentPage <= maxVisible - 1;
  const anchors = new Set<number>([1, mid, totalPages]);

  if (isStartBranch) {
    // Текущая страница близко к началу: 1..W, середина, последняя
    for (let i = 1; i <= maxVisible; i++) anchors.add(i);
  } else if (currentPage >= totalPages - maxVisible + 2) {
    // Текущая страница близко к концу: первая, середина, N-W+1..N
    for (let i = totalPages - maxVisible + 1; i <= totalPages; i++) anchors.add(i);
  } else {
    // Середина ряда: первая, окно вокруг текущей, последняя
    anchors.delete(mid);
    for (let i = currentPage - half; i <= currentPage + half; i++) anchors.add(i);
  }

  const sorted = Array.from(anchors).sort((a, b) => a - b);
  const pages: (number | 'ellipsis')[] = [];
  let ellipsisPlaced = false;

  sorted.forEach((page, index) => {
    if (index > 0) {
      const gap = page - sorted[index - 1] - 1;
      if (gap === 1) {
        pages.push(page - 1);
      } else if (gap >= 2 && !(isStartBranch && ellipsisPlaced)) {
        pages.push('ellipsis');
        ellipsisPlaced = true;
      }
    }
    pages.push(page);
  });

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
      // Правило prefers-reduced-motion из globals.css на scrollTo не действует
      const reduceMotion =
        window.matchMedia?.('(prefers-reduced-motion: reduce)')?.matches ?? false;
      window.scrollTo({ top: 0, behavior: reduceMotion ? 'auto' : 'smooth' });
    }
  };

  /**
   * Стрелка исчезает на крайней странице, и фокус клавиатуры упал бы на body.
   * Поэтому при нажатии с клавиатуры (detail === 0) фокус до смены страницы
   * переводится на плитку первой или последней страницы. preventScroll нужен,
   * чтобы браузер не вернул страницу вниз и не оборвал подъём.
   */
  const handleArrowClick = (event: React.MouseEvent<HTMLButtonElement>, target: number) => {
    if (event.detail === 0 && (target === 1 || target === totalPages)) {
      event.currentTarget
        .closest('ul')
        ?.querySelector<HTMLButtonElement>(`[data-page="${target}"]`)
        ?.focus({ preventScroll: true });
    }
    handlePageChange(target);
  };

  return (
    <nav aria-label="Pagination" className={cn('flex items-center justify-center', className)}>
      <ul className="flex flex-wrap items-center justify-center gap-2">
        {/* First Page Button (optional) */}
        {showFirstLast && (
          <li>
            <button
              onClick={() => handlePageChange(1)}
              disabled={isFirstPage}
              aria-label="Первая страница"
              className={cn(TILE_BUTTON, TILE_IDLE)}
            >
              <ChevronLeft className="w-4 h-4" />
              <ChevronLeft className="w-4 h-4 -ml-3" />
            </button>
          </li>
        )}

        {/* Previous Page Button: на первой странице не показывается */}
        {!isFirstPage && (
          <li>
            <button
              onClick={event => handleArrowClick(event, currentPage - 1)}
              aria-label="Предыдущая страница"
              className={cn(TILE_BUTTON, TILE_IDLE)}
            >
              <ChevronLeft className="w-4 h-4" aria-hidden="true" />
            </button>
          </li>
        )}

        {/* Page Numbers */}
        {pages.map((page, index) => {
          if (page === 'ellipsis') {
            return (
              <li key={`ellipsis-${index}`} aria-hidden="true">
                <span className={cn(TILE_BASE, 'text-sm text-neutral-600')}>&hellip;</span>
              </li>
            );
          }

          const isActive = page === currentPage;

          return (
            <li key={`page-${page}`}>
              <button
                onClick={() => handlePageChange(page)}
                data-page={page}
                aria-label={`Страница ${page}`}
                aria-current={isActive ? 'page' : undefined}
                className={cn(
                  TILE_BUTTON,
                  isActive
                    ? 'bg-primary text-text-inverse hover:bg-primary-hover'
                    : 'bg-primary-subtle text-primary hover:bg-primary hover:text-text-inverse'
                )}
              >
                {page}
              </button>
            </li>
          );
        })}

        {/* Next Page Button: на последней странице не показывается */}
        {!isLastPage && (
          <li>
            <button
              onClick={event => handleArrowClick(event, currentPage + 1)}
              aria-label="Следующая страница"
              className={cn(TILE_BUTTON, TILE_IDLE)}
            >
              <ChevronRight className="w-4 h-4" aria-hidden="true" />
            </button>
          </li>
        )}

        {/* Last Page Button (optional) */}
        {showFirstLast && (
          <li>
            <button
              onClick={() => handlePageChange(totalPages)}
              disabled={isLastPage}
              aria-label="Последняя страница"
              className={cn(TILE_BUTTON, TILE_IDLE)}
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
