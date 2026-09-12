/**
 * Chip Component
 * Фильтровый чип с иконкой и кнопкой удаления
 *
 * @see frontend/docs/design-system.json#components.Chip
 */

import React from 'react';
import { X } from 'lucide-react';
import { cn } from '@/utils/cn';

export interface ChipProps extends React.HTMLAttributes<HTMLDivElement> {
  /** Выбран ли чип */
  selected?: boolean;
  /** Иконка (опционально) */
  icon?: React.ReactNode;
  /** Callback при удалении */
  onRemove?: () => void;
  /** Текст */
  children: React.ReactNode;
}

export const Chip = React.forwardRef<HTMLDivElement, ChipProps>(
  ({ selected = false, icon, onRemove, children, className, ...props }, ref) => {
    return (
      <div
        ref={ref}
        className={cn(
          // Базовые стили - Design System v2.0
          'inline-flex items-center gap-2', // 8px gap
          'px-3 py-1 rounded-2xl', // 16px radius
          'text-caption font-medium', // caption typography
          'transition-colors duration-[180ms]',
          // Edge Case: Минимальная ширина 60px для удобного клика
          'min-w-[60px]',
          // Edge Case: Переполнение текста - max 200px, single-line
          'max-w-[200px]',

          // Состояния - Design System v2.0
          selected
            ? 'bg-primary text-white border-transparent' // Selected: Primary Orange
            : 'bg-white border border-neutral-300 text-text-secondary hover:border-primary hover:text-primary', // Default: Neutral with Primary Hover

          className
        )}
        {...props}
      >
        {/* Icon (опционально) */}
        {icon && <span className="w-4 h-4 flex-shrink-0">{icon}</span>}

        {/* Text */}
        <span className="truncate">{children}</span>

        {/* Remove Button - Edge Case: только если передан onRemove */}
        {onRemove && (
          <button
            onClick={e => {
              e.stopPropagation();
              onRemove();
            }}
            className={cn(
              'flex items-center justify-center',
              'w-4 h-4 rounded-full',
              'transition-colors duration-short',
              'hover:bg-neutral-300/50',
              'focus:outline-none focus:ring-2 focus:ring-primary'
            )}
            aria-label="Удалить"
          >
            <X className="w-3 h-3" />
          </button>
        )}
      </div>
    );
  }
);

Chip.displayName = 'Chip';
