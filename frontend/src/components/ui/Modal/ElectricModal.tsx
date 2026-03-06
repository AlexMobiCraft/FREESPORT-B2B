/**
 * Electric Orange Modal Component
 *
 * Модальное окно в стиле Electric Orange
 * Features:
 * - Dark overlay (rgba(15,15,15,0.9))
 * - Dark card background (#1A1A1A)
 * - Skewed title (-12deg)
 * - Skewed close button
 *
 * @see docs/4-ux-design/00-design-system-migration/02-component-specs.md
 */

'use client';

import React, { useEffect, useRef, useId } from 'react';
import { createPortal } from 'react-dom';
import { X } from 'lucide-react';
import { cn } from '@/utils/cn';

// ============================================
// Types
// ============================================

export interface ElectricModalProps {
  /** Is modal open */
  isOpen: boolean;
  /** Close callback */
  onClose: () => void;
  /** Modal title */
  title?: string;
  /** Modal size */
  size?: 'sm' | 'md' | 'lg' | 'xl' | 'full';
  /** Content */
  children: React.ReactNode;
  /** Footer (optional) */
  footer?: React.ReactNode;
  /** Close on backdrop click */
  closeOnBackdrop?: boolean;
  /** Close on Escape key */
  closeOnEscape?: boolean;
  /** Show close button */
  showCloseButton?: boolean;
  /** Additional class names */
  className?: string;
}

const SIZE_CLASSES = {
  sm: 'max-w-[400px]',
  md: 'max-w-[560px]',
  lg: 'max-w-[720px]',
  xl: 'max-w-[960px]',
  full: 'max-w-full m-4',
} as const;

// ============================================
// Component
// ============================================

export function ElectricModal({
  isOpen,
  onClose,
  title,
  size = 'md',
  children,
  footer,
  closeOnBackdrop = true,
  closeOnEscape = true,
  showCloseButton = true,
  className,
}: ElectricModalProps) {
  const modalRef = useRef<HTMLDivElement>(null);
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

    const focusableElements = modalRef.current?.querySelectorAll<HTMLElement>(
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
      const focusableElements = modalRef.current?.querySelectorAll<HTMLElement>(
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

  const modalContent = (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
      onClick={handleBackdropClick}
      role="presentation"
      style={{ animation: 'fadeIn 0.2s ease-out' }}
    >
      {/* Dark Backdrop */}
      <div
        className="absolute inset-0 bg-[rgba(15,15,15,0.9)] backdrop-blur-sm"
        aria-hidden="true"
      />

      {/* Modal Content */}
      <div
        ref={modalRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby={title ? titleId : undefined}
        aria-describedby={descriptionId}
        className={cn(
          'relative w-full max-h-[calc(100vh-2rem)]',
          'bg-[var(--bg-card)] border border-[var(--border-default)]',
          'flex flex-col',
          SIZE_CLASSES[size],
          className
        )}
        onKeyDown={handleKeyDown}
        style={{ animation: 'scaleIn 0.2s ease-out' }}
      >
        {/* Header */}
        {(title || showCloseButton) && (
          <div className="flex items-start justify-between p-6 border-b border-[var(--border-default)]">
            {title && (
              <h2
                id={titleId}
                className="font-roboto-condensed font-bold text-xl uppercase text-[var(--foreground)] transform -skew-x-12 pr-8"
              >
                <span className="transform skew-x-12 inline-block">{title}</span>
              </h2>
            )}

            {/* Close Button - Skewed */}
            {showCloseButton && (
              <button
                onClick={onClose}
                className={cn(
                  'flex items-center justify-center',
                  'w-10 h-10',
                  'border border-[var(--border-default)]',
                  'transform -skew-x-12',
                  'transition-all duration-200',
                  'hover:border-[var(--color-primary)] hover:bg-[var(--color-primary)]',
                  'group',
                  'focus:outline-none focus:ring-2 focus:ring-[var(--color-primary)]'
                )}
                aria-label="Закрыть модальное окно"
              >
                <X
                  className="w-5 h-5 text-[var(--color-text-secondary)] group-hover:text-black transform skew-x-12"
                  strokeWidth={2}
                />
              </button>
            )}
          </div>
        )}

        {/* Content */}
        <div
          id={descriptionId}
          className="flex-1 overflow-y-auto p-6 max-h-[calc(100vh-200px)] text-[var(--color-text-secondary)]"
        >
          {children}
        </div>

        {/* Footer */}
        {footer && (
          <div className="border-t border-[var(--border-default)] p-6 flex items-center justify-end gap-3">
            {footer}
          </div>
        )}
      </div>
    </div>
  );

  // Render via Portal
  if (typeof document === 'undefined') return null;
  return createPortal(modalContent, document.body);
}

ElectricModal.displayName = 'ElectricModal';

export default ElectricModal;
