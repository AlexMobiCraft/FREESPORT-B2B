/**
 * Electric Orange Tabs Component
 *
 * Tab navigation for product details, content sections
 * Features:
 * - Skewed active indicator (-12deg)
 * - Orange underline for active tab
 * - Hover effects
 *
 * @see docs/4-ux-design/00-design-system-migration/02-component-specs.md#tabs
 */

'use client';

import React, { useState } from 'react';
import { cn } from '@/utils/cn';

// ============================================
// Types
// ============================================

export interface Tab {
  id: string;
  label: string;
  count?: number;
}

export interface ElectricTabsProps {
  /** Tabs configuration */
  tabs: Tab[];
  /** Default active tab ID */
  defaultActiveId?: string;
  /** Controlled active tab ID */
  activeId?: string;
  /** Callback when tab changes */
  onChange?: (tabId: string) => void;
  /** Additional class names */
  className?: string;
}

// ============================================
// Tabs Component
// ============================================

export function ElectricTabs({
  tabs,
  defaultActiveId,
  activeId: controlledActiveId,
  onChange,
  className,
}: ElectricTabsProps) {
  const [internalActiveId, setInternalActiveId] = useState(defaultActiveId || tabs[0]?.id);

  const activeId = controlledActiveId ?? internalActiveId;

  const handleTabClick = (tabId: string) => {
    if (!controlledActiveId) {
      setInternalActiveId(tabId);
    }
    onChange?.(tabId);
  };

  return (
    <div
      className={cn('flex gap-6 md:gap-8 border-b border-[var(--border-default)]', className)}
      role="tablist"
    >
      {tabs.map(tab => {
        const isActive = tab.id === activeId;

        return (
          <button
            key={tab.id}
            role="tab"
            aria-selected={isActive}
            onClick={() => handleTabClick(tab.id)}
            className={cn(
              'relative pb-3 font-medium text-sm md:text-base uppercase tracking-wide',
              'transition-colors duration-200',
              isActive
                ? 'text-[var(--foreground)]'
                : 'text-[var(--color-text-secondary)] hover:text-[var(--color-primary)]'
            )}
            style={{ fontFamily: "'Inter', sans-serif" }}
          >
            {tab.label}
            {tab.count !== undefined && (
              <span className="ml-1.5 text-[var(--color-text-muted)]">({tab.count})</span>
            )}

            {/* Active Indicator - Skewed */}
            {isActive && (
              <span
                className="absolute bottom-0 left-0 right-0 h-[3px] bg-[var(--color-primary)]"
                style={{ transform: 'skewX(-12deg)' }}
              />
            )}
          </button>
        );
      })}
    </div>
  );
}

// ============================================
// Tab Panel Component
// ============================================

export interface ElectricTabPanelProps {
  /** Tab ID this panel belongs to */
  tabId: string;
  /** Currently active tab ID */
  activeId: string;
  /** Panel content */
  children: React.ReactNode;
  /** Additional class names */
  className?: string;
}

export function ElectricTabPanel({ tabId, activeId, children, className }: ElectricTabPanelProps) {
  if (tabId !== activeId) {
    return null;
  }

  return (
    <div
      role="tabpanel"
      className={cn('animate-fadeIn', className)}
      style={{ animationDuration: '0.3s' }}
    >
      {children}
    </div>
  );
}

export default ElectricTabs;
