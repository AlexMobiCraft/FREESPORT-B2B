/**
 * Toast Component
 * Уведомления с вариантами success/error/warning/info
 * Design System v2.0
 *
 * @see docs/frontend/design-system.json#components.Toast
 */

'use client';

import React, { useEffect, useState, useCallback } from 'react';
import { CheckCircle, XCircle, AlertTriangle, Info, X } from 'lucide-react';
import { cn } from '@/utils/cn';

export type ToastVariant = 'success' | 'error' | 'warning' | 'info';
export type ToastPosition = 'top-right' | 'top-center' | 'bottom-right' | 'bottom-center';

export interface ToastProps {
  /** Уникальный ID toast */
  id: string;
  /** Вариант toast */
  variant: ToastVariant;
  /** Заголовок (опционально) */
  title?: string;
  /** Текст сообщения */
  message: string;
  /** Длительность отображения в мс */
  duration?: number;
  /** Callback при закрытии */
  onClose: (id: string) => void;
  /** Позиция на экране */
  position?: ToastPosition;
}

const TOAST_VARIANTS = {
  success: {
    bg: '#E0F5E0',
    borderClass: 'border-accent-success',
    icon: CheckCircle,
    iconClass: 'text-accent-success',
  },
  error: {
    bg: '#FFE1E1',
    borderClass: 'border-accent-danger',
    icon: XCircle,
    iconClass: 'text-accent-danger',
  },
  warning: {
    bg: '#FFF1CC',
    borderClass: 'border-accent-warning',
    icon: AlertTriangle,
    iconClass: 'text-accent-warning',
  },
  info: {
    bg: '#E7F3FF',
    borderClass: 'border-primary',
    icon: Info,
    iconClass: 'text-primary',
  },
} as const;

export const Toast: React.FC<ToastProps> = ({
  id,
  variant,
  title,
  message,
  duration = 5000,
  onClose,
}) => {
  const [isExiting, setIsExiting] = useState(false);
  const variantConfig = TOAST_VARIANTS[variant];
  const Icon = variantConfig.icon;

  const handleClose = useCallback(() => {
    setIsExiting(true);
    // Таймаут синхронизирован с CSS-анимацией slideOutRight (280ms + буфер)
    setTimeout(() => {
      onClose(id);
    }, 300);
  }, [id, onClose]);

  // Auto-dismiss
  useEffect(() => {
    if (duration <= 0) return;

    const timer = setTimeout(() => {
      handleClose();
    }, duration);

    return () => clearTimeout(timer);
  }, [duration, handleClose]);

  return (
    <div
      role="alert"
      aria-live="polite"
      className={cn(
        'rounded-xl p-4 min-w-[320px] max-w-[420px]',
        'shadow-[0_8px_24px_rgba(15,23,42,0.12)]',
        'border-l-4',
        'flex gap-3 items-start',
        variantConfig.borderClass,
        isExiting ? 'animate-slideOutRight' : 'animate-slideInRight'
      )}
      style={{
        backgroundColor: variantConfig.bg,
      }}
    >
      {/* Icon */}
      <Icon
        className={cn('flex-shrink-0 mt-0.5', variantConfig.iconClass)}
        size={24}
        strokeWidth={2}
      />

      {/* Content */}
      <div className="flex-1 min-w-0">
        {title && (
          <div className="text-[16px] leading-[24px] font-semibold text-[#1B1B1B] mb-1">
            {title}
          </div>
        )}
        <div className="text-[14px] leading-[20px] font-medium text-[#4D4D4D]">{message}</div>
      </div>

      {/* Close button */}
      <button
        onClick={handleClose}
        className="flex-shrink-0 hover:opacity-70 transition-opacity duration-[180ms] focus:outline-none focus:ring-2 focus:ring-[#1F1F1F] rounded"
        aria-label="Закрыть уведомление"
      >
        <X size={16} className="text-[#7A7A7A]" strokeWidth={2} />
      </button>
    </div>
  );
};

Toast.displayName = 'Toast';
