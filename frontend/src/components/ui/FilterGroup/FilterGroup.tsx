/**
 * FilterGroup Component
 * Collapsible группа фильтров согласно Design System v2.0
 *
 * @see docs/stories/epic-12/12.5.story.md#AC1
 */

'use client';

import React, { useState } from 'react';
import { ChevronDown } from 'lucide-react';
import { cn } from '@/utils/cn';

export interface FilterGroupProps {
  /** Заголовок группы */
  title: string;
  /** Можно ли сворачивать */
  collapsible?: boolean;
  /** Развернута по умолчанию */
  defaultExpanded?: boolean;
  /** Содержимое группы */
  children: React.ReactNode;
  /** Дополнительные классы */
  className?: string;
}

/**
 * FilterGroup - collapsible группа фильтров
 */
export const FilterGroup = React.forwardRef<HTMLDivElement, FilterGroupProps>(
  ({ title, collapsible = true, defaultExpanded = true, children, className }, ref) => {
    const [isExpanded, setIsExpanded] = useState(defaultExpanded);

    const toggleExpanded = () => {
      if (collapsible) {
        setIsExpanded(!isExpanded);
      }
    };

    return (
      <div ref={ref} className={cn('w-full', className)}>
        {/* Header */}
        <button
          type="button"
          onClick={toggleExpanded}
          className={cn(
            'w-full flex items-center justify-between',
            'text-title-s font-semibold text-text-primary', // title-s, font-weight: 600
            'mb-3',
            collapsible ? 'cursor-pointer' : 'cursor-default'
          )}
          aria-expanded={isExpanded}
          aria-controls={`filter-group-${title.toLowerCase().replace(/\s+/g, '-')}`}
        >
          <span>{title}</span>

          {/* ChevronDown Icon */}
          {collapsible && (
            <ChevronDown
              className={cn(
                'w-5 h-5 text-text-secondary',
                'transition-transform duration-[180ms]',
                isExpanded && 'rotate-180'
              )}
              aria-hidden="true"
            />
          )}
        </button>

        {/* Content */}
        <div
          id={`filter-group-${title.toLowerCase().replace(/\s+/g, '-')}`}
          className={cn(
            'overflow-hidden transition-all duration-[180ms]',
            isExpanded ? 'max-h-[1000px] opacity-100' : 'max-h-0 opacity-0'
          )}
        >
          <div className="space-y-2">{children}</div>
        </div>
      </div>
    );
  }
);

FilterGroup.displayName = 'FilterGroup';
