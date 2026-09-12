/**
 * Electric Orange Toast Component
 *
 * Уведомления в стиле Electric Orange
 * Features:
 * - Skewed container (-12deg)
 * - Dark background (#1A1A1A)
 * - Color-coded left border (success/error/warning/info)
 * - Slide-in animation from right
 *
 * @see docs/4-ux-design/00-design-system-migration/02-component-specs.md
 */

'use client';

import React, { useEffect, useState, useCallback } from 'react';
import { CheckCircle, XCircle, AlertTriangle, Info, X } from 'lucide-react';
import { cn } from '@/utils/cn';

// ============================================
// Types
// ============================================

export type ElectricToastVariant = 'success' | 'error' | 'warning' | 'info';

export interface ElectricToastProps {
  /** Unique toast ID */
  id: string;
  /** Toast variant */
  variant: ElectricToastVariant;
  /** Title (optional) */
  title?: string;
  /** Message text */
  message: string;
  /** Auto-dismiss duration in ms (0 = no auto-dismiss) */
  duration?: number;
  /** Close callback */
  onClose: (id: string) => void;
}

// ============================================
// Config
// ============================================

const TOAST_VARIANTS = {
  success: {
    borderColor: 'var(--color-success)',
    icon: CheckCircle,
    iconColor: 'var(--color-success)',
  },
  error: {
    borderColor: 'var(--color-danger)',
    icon: XCircle,
    iconColor: 'var(--color-danger)',
  },
  warning: {
    borderColor: 'var(--color-warning)',
    icon: AlertTriangle,
    iconColor: 'var(--color-warning)',
  },
  info: {
    borderColor: 'var(--color-primary)',
    icon: Info,
    iconColor: 'var(--color-primary)',
  },
} as const;

// ============================================
// Component
// ============================================

export function ElectricToast({
  id,
  variant,
  title,
  message,
  duration = 5000,
  onClose,
}: ElectricToastProps) {
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
        'min-w-[320px] max-w-[420px]',
        'bg-[var(--bg-card)] border border-[var(--border-default)]',
        'p-4',
        'flex gap-3 items-start',
        'transform -skew-x-12',
        'shadow-[0_8px_24px_rgba(0,0,0,0.4)]',
        isExiting ? 'animate-slideOutRight' : 'animate-slideInRight'
      )}
      style={{
        borderLeftWidth: '4px',
        borderLeftColor: variantConfig.borderColor,
      }}
    >
      {/* Icon - Counter-skewed */}
      <div className="transform skew-x-12">
        <Icon
          className="flex-shrink-0 mt-0.5"
          size={24}
          strokeWidth={2}
          style={{ color: variantConfig.iconColor }}
        />
      </div>

      {/* Content - Counter-skewed */}
      <div className="flex-1 min-w-0 transform skew-x-12">
        {title && (
          <div className="text-[16px] leading-[24px] font-semibold text-[var(--foreground)] mb-1">
            {title}
          </div>
        )}
        <div className="text-[14px] leading-[20px] text-[var(--color-text-secondary)]">
          {message}
        </div>
      </div>

      {/* Close button - Counter-skewed */}
      <button
        onClick={handleClose}
        className={cn(
          'flex-shrink-0 transform skew-x-12',
          'hover:text-[var(--color-primary)] transition-colors duration-200',
          'focus:outline-none'
        )}
        aria-label="Закрыть уведомление"
      >
        <X size={16} className="text-[var(--color-text-muted)]" strokeWidth={2} />
      </button>
    </div>
  );
}

ElectricToast.displayName = 'ElectricToast';

// ============================================
// Toast Container (for demo purposes)
// ============================================

export interface ElectricToastContainerProps {
  toasts: Array<{
    id: string;
    variant: ElectricToastVariant;
    title?: string;
    message: string;
    duration?: number;
  }>;
  onClose: (id: string) => void;
}

export function ElectricToastContainer({ toasts, onClose }: ElectricToastContainerProps) {
  return (
    <div className="fixed top-4 right-4 z-50 flex flex-col gap-3">
      {toasts.map(toast => (
        <ElectricToast key={toast.id} {...toast} onClose={onClose} />
      ))}
    </div>
  );
}

export default ElectricToast;
