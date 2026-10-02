/**
 * Electric Orange Drawer Component
 *
 * Slide-in панель для мобильных фильтров в стиле Electric Orange
 * Features:
 * - Slide-in анимация слева
 * - Dark overlay (rgba(15,15,15,0.9))
 * - Skewed title (-12deg)
 * - Body scroll lock
 */

'use client';

import React, { useEffect, useRef, useId } from 'react';
import { createPortal } from 'react-dom';
import { X } from 'lucide-react';
import { cn } from '@/utils/cn';

// ============================================
// Types
// ============================================

export interface ElectricDrawerProps {
  /** Is drawer open */
  isOpen: boolean;
  /** Close callback */
  onClose: () => void;
  /** Drawer title */
  title?: string;
  /** Content */
  children: React.ReactNode;
  /** Footer (optional) */
  footer?: React.ReactNode;
  /** Width on larger screens */
  width?: 'sm' | 'md' | 'lg';
  /** Close on backdrop click */
  closeOnBackdrop?: boolean;
  /** Close on Escape key */
  closeOnEscape?: boolean;
  /** Additional class names */
  className?: string;
}

const WIDTH_CLASSES = {
  sm: 'max-w-[280px]',
  md: 'max-w-[320px]',
  lg: 'max-w-[400px]',
} as const;

// ============================================
// Component
// ============================================

export function ElectricDrawer({
  isOpen,
  onClose,
  title,
  children,
  footer,
  width = 'md',
  closeOnBackdrop = true,
  closeOnEscape = true,
  className,
}: ElectricDrawerProps) {
  const drawerRef = useRef<HTMLDivElement>(null);
  const previouslyFocusedElement = useRef<HTMLElement | null>(null);
  const titleId = useId();
  const descriptionId = useId();

  // Body scroll lock
  useEffect(() => {
    if (!isOpen) return;

    const originalOverflow = document.body.style.overflow;
    const scrollbarWidth = window.innerWidth - document.documentElement.clientWidth;

    document.body.style.overflow = 'hidden';
    if (scrollbarWidth > 0) {
      document.body.style.paddingRight = `${scrollbarWidth}px`;
    }

    return () => {
      document.body.style.overflow = originalOverflow;
      document.body.style.paddingRight = '';
    };
  }, [isOpen]);

  // Focus management
  useEffect(() => {
    if (!isOpen) return;

    previouslyFocusedElement.current = document.activeElement as HTMLElement;

    const focusableElements = drawerRef.current?.querySelectorAll<HTMLElement>(
      'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
    );

    if (focusableElements && focusableElements.length > 0) {
      setTimeout(() => {
        focusableElements[0].focus();
      }, 100);
    }

    return () => {
      if (previouslyFocusedElement.current) {
        previouslyFocusedElement.current.focus();
      }
    };
  }, [isOpen]);

  // Keyboard handling
  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Escape' && closeOnEscape) {
      onClose();
      return;
    }

    if (e.key === 'Tab') {
      const focusableElements = drawerRef.current?.querySelectorAll<HTMLElement>(
        'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
      );

      if (!focusableElements || focusableElements.length === 0) return;

      const firstElement = focusableElements[0];
      const lastElement = focusableElements[focusableElements.length - 1];

      if (e.shiftKey) {
        if (document.activeElement === firstElement) {
          e.preventDefault();
          lastElement.focus();
        }
      } else {
        if (document.activeElement === lastElement) {
          e.preventDefault();
          firstElement.focus();
        }
      }
    }
  };

  // Backdrop click
  const handleBackdropClick = (e: React.MouseEvent) => {
    if (closeOnBackdrop && e.target === e.currentTarget) {
      onClose();
    }
  };

  if (!isOpen) return null;

  const drawerContent = (
    <div className="fixed inset-0 z-50" onClick={handleBackdropClick} role="presentation">
      {/* Dark Backdrop with fade-in */}
      <div
        className="absolute inset-0 bg-[rgba(15,15,15,0.9)] backdrop-blur-sm"
        aria-hidden="true"
        style={{ animation: 'fadeIn 0.2s ease-out' }}
      />

      {/* Drawer Panel - slides in from left */}
      <div
        ref={drawerRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby={title ? titleId : undefined}
        aria-describedby={descriptionId}
        className={cn(
          'absolute left-0 top-0 h-full w-full',
          'bg-[var(--bg-card)] border-r border-[var(--border-default)]',
          'flex flex-col',
          'overflow-hidden',
          WIDTH_CLASSES[width],
          className
        )}
        onKeyDown={handleKeyDown}
        style={{
          animation: 'slideInLeft 0.3s ease-out',
        }}
      >
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b border-[var(--border-default)] flex-shrink-0">
          {title && (
            <h2
              id={titleId}
              className="font-roboto-condensed font-bold text-lg uppercase text-[var(--foreground)] transform -skew-x-12"
            >
              <span className="transform skew-x-12 inline-block">{title}</span>
            </h2>
          )}

          {/* Close Button - Skewed */}
          <button
            onClick={onClose}
            className={cn(
              'flex items-center justify-center',
              'w-10 h-10 ml-auto',
              'border border-[var(--border-default)]',
              'transform -skew-x-12',
              'transition-all duration-200',
              'hover:border-[var(--color-primary)] hover:bg-[var(--color-primary)]',
              'group',
              'focus:outline-none focus:ring-2 focus:ring-[var(--color-primary)]'
            )}
            aria-label="Закрыть панель"
          >
            <X
              className="w-5 h-5 text-[var(--color-text-secondary)] group-hover:text-black transform skew-x-12"
              strokeWidth={2}
            />
          </button>
        </div>

        {/* Content - Scrollable */}
        <div id={descriptionId} className="flex-1 overflow-y-auto p-4 pr-2">
          {children}
        </div>

        {/* Footer */}
        {footer && (
          <div className="border-t border-[var(--border-default)] p-4 flex-shrink-0">{footer}</div>
        )}
      </div>

      {/* CSS Keyframes */}
      <style jsx global>{`
        @keyframes slideInLeft {
          from {
            transform: translateX(-100%);
          }
          to {
            transform: translateX(0);
          }
        }
        @keyframes fadeIn {
          from {
            opacity: 0;
          }
          to {
            opacity: 1;
          }
        }
      `}</style>
    </div>
  );

  // Render via Portal
  if (typeof document === 'undefined') return null;
  return createPortal(drawerContent, document.body);
}

ElectricDrawer.displayName = 'ElectricDrawer';

export default ElectricDrawer;
