/**
 * SupportPanel Component
 * Панели доставки/наличия
 *
 * @see frontend/docs/design-system.json#components.SupportPanel
 */

'use client';

import React, { useState } from 'react';
import { Truck, CheckCircle2, X } from 'lucide-react';
import { cn } from '@/utils/cn';

export type SupportPanelVariant = 'delivery' | 'availability';

export interface SupportPanelProps extends React.HTMLAttributes<HTMLDivElement> {
  /** Вариант панели */
  variant: SupportPanelVariant;
  /** Основной текст */
  value: string;
  /** Описание (опционально) */
  description?: string;
  /** Дополнительная информация (опционально) */
  meta?: string;
  /** Иконка (опционально, по умолчанию зависит от варианта) */
  icon?: React.ReactNode;
  /** Можно ли закрыть панель */
  onDismiss?: () => void;
}

const variantConfig: Record<
  SupportPanelVariant,
  { bg: string; border?: string; iconBg: string; iconColor: string; defaultIcon: React.ReactNode }
> = {
  delivery: {
    bg: 'bg-neutral-100',
    border: 'border border-primary/12',
    iconBg: 'bg-primary/10',
    iconColor: 'text-primary',
    defaultIcon: <Truck className="w-full h-full" aria-hidden="true" />,
  },
  availability: {
    bg: 'bg-neutral-200',
    iconBg: 'bg-accent-success-bg',
    iconColor: 'text-accent-success',
    defaultIcon: <CheckCircle2 className="w-full h-full" aria-hidden="true" />,
  },
};

export const SupportPanel = React.forwardRef<HTMLDivElement, SupportPanelProps>(
  ({ variant, value, description, meta, icon, onDismiss, className, ...props }, ref) => {
    const [isVisible, setIsVisible] = useState(true);
    const config = variantConfig[variant];

    const handleDismiss = () => {
      setIsVisible(false);
      onDismiss?.();
    };

    if (!isVisible) return null;

    return (
      <div
        ref={ref}
        className={cn(
          // Базовые стили
          'relative',
          'grid grid-cols-[auto_1fr] gap-4',
          'p-5 rounded-md',
          config.bg,
          config.border,
          // Edge Case: fade-out анимация при закрытии
          'transition-opacity duration-[200ms]',
          !isVisible && 'opacity-0',

          className
        )}
        {...props}
      >
        {/* Icon Container */}
        <div
          className={cn('flex items-center justify-center', 'w-24 h-24 rounded-xl', config.iconBg)}
        >
          <div className={cn('w-18 h-18', config.iconColor)}>{icon || config.defaultIcon}</div>
        </div>

        {/* Content */}
        <div className="flex flex-col gap-1">
          {/* Value - основной текст */}
          <div className="text-body-l font-semibold text-text-primary">{value}</div>

          {/* Description - вторичный текст */}
          {description && <div className="text-body-s text-text-secondary">{description}</div>}

          {/* Meta - дополнительная информация */}
          {meta && <div className="text-caption text-text-muted">{meta}</div>}
        </div>

        {/* Edge Case: Кнопка закрытия (dismissible) */}
        {onDismiss && (
          <button
            onClick={handleDismiss}
            className={cn(
              'absolute top-3 right-3',
              'flex items-center justify-center',
              'w-8 h-8 rounded-lg',
              'transition-colors duration-short',
              'hover:bg-neutral-200',
              'focus:outline-none focus:ring-2 focus:ring-primary'
            )}
            aria-label="Закрыть"
          >
            <X className="w-5 h-5 text-neutral-600" />
          </button>
        )}
      </div>
    );
  }
);

SupportPanel.displayName = 'SupportPanel';
