/**
 * InfoPanel Component
 * Информационный баннер с иконкой
 *
 * @see frontend/docs/design-system.json#components.InfoPanel
 *
 * Story 15.2: Расширен API для поддержки variant, title, message props
 */

'use client';

import React, { useState } from 'react';
import { Info, AlertCircle, AlertTriangle, CheckCircle, X } from 'lucide-react';
import { cn } from '@/utils/cn';

/** Варианты отображения InfoPanel */
export type InfoPanelVariant = 'info' | 'warning' | 'error' | 'success';

export interface InfoPanelProps extends React.HTMLAttributes<HTMLDivElement> {
  /** Текст сообщения (можно использовать вместо message) */
  children?: React.ReactNode;
  /** Вариант отображения: info (default), warning, error, success */
  variant?: InfoPanelVariant;
  /** Заголовок панели (опционально) */
  title?: string;
  /** Текст сообщения (альтернатива children) */
  message?: React.ReactNode;
  /** Кастомная иконка (переопределяет иконку варианта) */
  icon?: React.ReactNode;
  /** Callback для закрытия панели */
  onDismiss?: () => void;
}

/**
 * Конфигурация стилей для каждого варианта
 */
const variantConfig: Record<
  InfoPanelVariant,
  {
    bgColor: string;
    borderColor: string;
    iconBgColor: string;
    iconColor: string;
    Icon: React.ElementType;
  }
> = {
  info: {
    bgColor: 'bg-primary-subtle',
    borderColor: 'border-primary/20',
    iconBgColor: 'bg-primary/10',
    iconColor: 'text-primary',
    Icon: Info,
  },
  warning: {
    bgColor: 'bg-amber-50',
    borderColor: 'border-amber-200',
    iconBgColor: 'bg-amber-100',
    iconColor: 'text-amber-600',
    Icon: AlertTriangle,
  },
  error: {
    bgColor: 'bg-red-50',
    borderColor: 'border-red-200',
    iconBgColor: 'bg-red-100',
    iconColor: 'text-red-600',
    Icon: AlertCircle,
  },
  success: {
    bgColor: 'bg-green-50',
    borderColor: 'border-green-200',
    iconBgColor: 'bg-green-100',
    iconColor: 'text-green-600',
    Icon: CheckCircle,
  },
};

export const InfoPanel = React.forwardRef<HTMLDivElement, InfoPanelProps>(
  ({ children, variant = 'info', title, message, icon, onDismiss, className, ...props }, ref) => {
    const [isVisible, setIsVisible] = useState(true);

    const handleDismiss = () => {
      setIsVisible(false);
      onDismiss?.();
    };

    if (!isVisible) return null;

    const config = variantConfig[variant];
    const IconComponent = config.Icon;

    // Контент: children имеет приоритет над message
    const content = children ?? message;

    return (
      <div
        ref={ref}
        role="alert"
        className={cn(
          // Базовые стили
          'relative',
          'grid grid-cols-[auto_1fr] gap-4',
          'p-5 rounded-md',
          // Динамические стили на основе variant
          config.bgColor,
          'border',
          config.borderColor,
          // Edge Case: fade-out анимация при закрытии
          'transition-opacity duration-[200ms]',
          !isVisible && 'opacity-0',
          className
        )}
        {...props}
      >
        {/* Icon Container */}
        <div
          className={cn(
            'flex items-start justify-center',
            'w-12 h-12 rounded-xl',
            config.iconBgColor
          )}
        >
          <div className={cn('w-6 h-6 flex items-center justify-center mt-3', config.iconColor)}>
            {/* Кастомная иконка или иконка варианта */}
            {icon || <IconComponent className="w-full h-full" aria-hidden="true" />}
          </div>
        </div>

        {/* Text Content */}
        <div className="flex-1">
          {/* Заголовок (если указан) */}
          {title && <div className="text-body-m font-semibold text-text-primary mb-1">{title}</div>}
          {/* Основной контент */}
          {content && (
            <div className="text-body-m text-text-secondary whitespace-normal break-words pr-8">
              {content}
            </div>
          )}
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

InfoPanel.displayName = 'InfoPanel';
