/**
 * Electric Orange Accordion Component
 *
 * Аккордеон в стиле Electric Orange
 * Features:
 * - Skewed title (-12deg)
 * - Orange accent on active/hover
 * - Chevron rotation on expand
 * - Dark theme
 *
 * @see docs/4-ux-design/00-design-system-migration/02-component-specs.md
 */

'use client';

import React, { useState, useCallback } from 'react';
import { ChevronDown } from 'lucide-react';
import { cn } from '@/utils/cn';

// ============================================
// Types
// ============================================

export interface ElectricAccordionItem {
  id: string;
  title: string;
  content: React.ReactNode;
}

export interface ElectricAccordionProps {
  /** Accordion items */
  items: ElectricAccordionItem[];
  /** Allow multiple items open */
  allowMultiple?: boolean;
  /** Default open item ID */
  defaultOpenId?: string;
  /** Additional class names */
  className?: string;
}

// ============================================
// Component
// ============================================

export function ElectricAccordion({
  items,
  allowMultiple = false,
  defaultOpenId,
  className,
}: ElectricAccordionProps) {
  const [openIds, setOpenIds] = useState<Set<string>>(() => {
    const initial = new Set<string>();
    if (defaultOpenId) {
      initial.add(defaultOpenId);
    }
    return initial;
  });

  const handleToggle = useCallback(
    (id: string) => {
      setOpenIds(prev => {
        const newSet = new Set(prev);

        if (newSet.has(id)) {
          newSet.delete(id);
        } else {
          if (!allowMultiple) {
            newSet.clear();
          }
          newSet.add(id);
        }

        return newSet;
      });
    },
    [allowMultiple]
  );

  return (
    <div className={cn('space-y-2', className)}>
      {items.map(item => {
        const isOpen = openIds.has(item.id);

        return (
          <div key={item.id} className="border border-[var(--border-default)] bg-[var(--bg-card)]">
            {/* Header - Clickable */}
            <button
              onClick={() => handleToggle(item.id)}
              className={cn(
                'w-full flex items-center justify-between',
                'p-4',
                'transition-colors duration-200',
                'hover:bg-[var(--bg-card-hover)]',
                'focus:outline-none focus:ring-2 focus:ring-inset focus:ring-[var(--color-primary)]',
                isOpen && 'border-b border-[var(--border-default)]'
              )}
              aria-expanded={isOpen}
            >
              {/* Title - Skewed */}
              <span className="font-roboto-condensed font-bold text-base uppercase text-[var(--foreground)] transform -skew-x-12">
                <span className="transform skew-x-12 inline-block">{item.title}</span>
              </span>

              {/* Chevron */}
              <ChevronDown
                className={cn(
                  'w-5 h-5 text-[var(--color-primary)] transition-transform duration-200',
                  isOpen && 'rotate-180'
                )}
              />
            </button>

            {/* Content */}
            {isOpen && (
              <div className="p-4 text-[var(--color-text-secondary)] text-sm leading-relaxed animate-fadeIn">
                {item.content}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}

ElectricAccordion.displayName = 'ElectricAccordion';

export default ElectricAccordion;
