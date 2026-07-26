/**
 * Breadcrumb Component
 * Линейная навигация с ChevronRight разделителем
 *
 * @see frontend/docs/design-system.json#components.Breadcrumb
 */

import React from 'react';
import Link from 'next/link';
import { ChevronRight } from 'lucide-react';
import { cn } from '@/utils/cn';

export interface BreadcrumbItem {
  label: string;
  href?: string;
}

export interface BreadcrumbProps {
  /** Элементы хлебных крошек */
  items: BreadcrumbItem[];
  /** CSS класс */
  className?: string;
}

export const Breadcrumb: React.FC<BreadcrumbProps> = ({ items, className }) => {
  // Edge Case: Если элементов больше 5 - показываем первый, последний и "..."
  const shouldCollapse = items.length > 5;
  const displayItems = shouldCollapse ? [items[0], { label: '...' }, ...items.slice(-2)] : items;

  return (
    <nav aria-label="Breadcrumb" className={cn('flex items-center gap-2', className)}>
      <ol className="flex items-center gap-2">
        {displayItems.map((item, index) => {
          const isLast = index === displayItems.length - 1;
          const isEllipsis = item.label === '...';

          return (
            <li key={`${item.label}-${index}`} className="flex items-center gap-2">
              {/* Breadcrumb Item */}
              {item.href && !isLast && !isEllipsis ? (
                <Link
                  href={item.href}
                  className={cn(
                    'text-body-s text-neutral-700',
                    'hover:text-primary transition-colors duration-short',
                    // Edge Case: Текст длиннее 150px - обрезка с ellipsis
                    'max-w-[150px] truncate'
                  )}
                  title={item.label} // Edge Case: Tooltip с полным текстом
                >
                  {item.label}
                </Link>
              ) : (
                <span
                  className={cn(
                    'text-body-s',
                    isLast ? 'text-text-primary font-medium' : 'text-neutral-700',
                    // Edge Case: Для ellipsis - показываем Tooltip при наведении
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
                  {item.label}
                </span>
              )}

              {/* Separator */}
              {!isLast && <ChevronRight className="w-4 h-4 text-neutral-600" aria-hidden="true" />}
            </li>
          );
        })}
      </ol>
    </nav>
  );
};

Breadcrumb.displayName = 'Breadcrumb';
