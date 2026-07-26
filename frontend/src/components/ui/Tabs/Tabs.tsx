/**
 * Tabs Component
 * Горизонтальные табы с underline индикатором и keyboard navigation
 *
 * @see frontend/docs/design-system.json#components.Tabs
 */

'use client';

import React, { useRef, useState } from 'react';
import { cn } from '@/utils/cn';

export interface Tab {
  id: string;
  label: string;
  content: React.ReactNode;
  disabled?: boolean;
}

export interface TabsProps {
  /** Массив табов */
  tabs: Tab[];
  /** Активный таб по умолчанию */
  defaultTab?: string;
  /** Callback при изменении */
  onChange?: (tabId: string) => void;
  /** CSS класс */
  className?: string;
}

export const Tabs: React.FC<TabsProps> = ({ tabs, defaultTab, onChange, className }) => {
  const [activeTab, setActiveTab] = useState(defaultTab || tabs[0]?.id);
  const tabListRef = useRef<HTMLDivElement>(null);

  const handleTabClick = (tabId: string, disabled?: boolean) => {
    if (disabled) return;

    setActiveTab(tabId);
    onChange?.(tabId);

    // Edge Case: Активный таб автоматически прокручивается в видимую область
    const tabElement = tabListRef.current?.querySelector(`[data-tab-id="${tabId}"]`);
    if (tabElement) {
      tabElement.scrollIntoView({ behavior: 'smooth', block: 'nearest', inline: 'center' });
    }
  };

  // Edge Case: Keyboard navigation
  const handleKeyDown = (e: React.KeyboardEvent, currentIndex: number) => {
    const enabledTabs = tabs.filter(tab => !tab.disabled);
    const currentEnabledIndex = enabledTabs.findIndex(tab => tab.id === tabs[currentIndex].id);

    let nextIndex = currentEnabledIndex;

    switch (e.key) {
      case 'ArrowLeft':
        e.preventDefault();
        nextIndex = currentEnabledIndex > 0 ? currentEnabledIndex - 1 : enabledTabs.length - 1;
        break;
      case 'ArrowRight':
        e.preventDefault();
        nextIndex = currentEnabledIndex < enabledTabs.length - 1 ? currentEnabledIndex + 1 : 0;
        break;
      case 'Home':
        e.preventDefault();
        nextIndex = 0;
        break;
      case 'End':
        e.preventDefault();
        nextIndex = enabledTabs.length - 1;
        break;
      case 'Enter':
      case ' ':
        e.preventDefault();
        handleTabClick(tabs[currentIndex].id, tabs[currentIndex].disabled);
        return;
      default:
        return;
    }

    const nextTab = enabledTabs[nextIndex];
    if (nextTab) {
      handleTabClick(nextTab.id);
      // Фокус на следующий таб
      const nextTabElement = tabListRef.current?.querySelector(
        `[data-tab-id="${nextTab.id}"]`
      ) as HTMLElement;
      nextTabElement?.focus();
    }
  };

  // Active tab content rendered in Tab Panels below

  return (
    <div className={cn('w-full', className)}>
      {/* Tab List - Edge Case: Overflow - горизонтальный скролл */}
      <div
        ref={tabListRef}
        className="flex items-center gap-6 border-b border-neutral-300 overflow-x-auto scrollbar-hide"
        role="tablist"
      >
        {tabs.map((tab, index) => {
          const isActive = tab.id === activeTab;

          return (
            <button
              key={tab.id}
              data-tab-id={tab.id}
              role="tab"
              aria-selected={isActive}
              aria-controls={`tabpanel-${tab.id}`}
              aria-disabled={tab.disabled}
              tabIndex={isActive ? 0 : -1}
              disabled={tab.disabled}
              onClick={() => handleTabClick(tab.id, tab.disabled)}
              onKeyDown={e => handleKeyDown(e, index)}
              className={cn(
                // Базовые стили
                'relative px-1 pb-3 text-body-m font-medium',
                'transition-colors duration-short',
                'focus:outline-none focus:ring-2 focus:ring-primary focus:ring-offset-2',
                'whitespace-nowrap',

                // Активный таб
                isActive ? 'text-primary' : 'text-text-secondary',

                // Hover
                !tab.disabled && !isActive && 'hover:text-primary',

                // Edge Case: Disabled состояние
                tab.disabled && 'opacity-50 cursor-not-allowed'
              )}
            >
              {tab.label}

              {/* Underline индикатор */}
              {isActive && (
                <span
                  className="absolute bottom-0 left-0 right-0 h-[3px] bg-primary rounded-full"
                  aria-hidden="true"
                />
              )}
            </button>
          );
        })}
      </div>

      {/* Tab Panels */}
      <div className="mt-6">
        {tabs.map(tab => (
          <div
            key={tab.id}
            id={`tabpanel-${tab.id}`}
            role="tabpanel"
            aria-labelledby={tab.id}
            hidden={tab.id !== activeTab}
          >
            {tab.content}
          </div>
        ))}
      </div>
    </div>
  );
};

Tabs.displayName = 'Tabs';
