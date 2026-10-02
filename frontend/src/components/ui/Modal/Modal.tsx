/**
 * Modal Component
 * Центрированное окно с backdrop blur и управлением фокусом
 * Design System v2.0
 *
 * @see docs/frontend/design-system.json#components.Modal
 */

'use client';

import React, { useEffect, useRef, useId } from 'react';
import { createPortal } from 'react-dom';
import { X } from 'lucide-react';
import { cn } from '@/utils/cn';

export interface ModalProps {
  /** Открыт ли модал */
  isOpen: boolean;
  /** Callback при закрытии */
  onClose: () => void;
  /** Заголовок */
  title?: string;
  /** Размер модала */
  size?: 'sm' | 'md' | 'lg' | 'xl' | 'full';
  /** Контент */
  children: React.ReactNode;
  /** Footer (опционально) */
  footer?: React.ReactNode;
  /** Закрывать при клике на backdrop */
  closeOnBackdrop?: boolean;
  /** Закрывать по Escape */
  closeOnEscape?: boolean;
  /** Показывать кнопку закрытия */
  showCloseButton?: boolean;
  /** CSS класс для кастомизации */
  className?: string;
}

const SIZE_CLASSES = {
  sm: 'max-w-[400px]',
  md: 'max-w-[560px]',
  lg: 'max-w-[720px]',
  xl: 'max-w-[960px]',
  full: 'max-w-full m-4',
} as const;

export const Modal: React.FC<ModalProps> = ({
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
}) => {
  const modalRef = useRef<HTMLDivElement>(null);
  const previouslyFocusedElement = useRef<HTMLElement | null>(null);
  const titleId = useId();
  const descriptionId = useId();

  // Body scroll lock
  useEffect(() => {
    if (!isOpen) return;

    const originalOverflow = document.body.style.overflow;
    const originalPaddingRight = document.body.style.paddingRight;

    // Вычисляем ширину scrollbar
    const scrollbarWidth = window.innerWidth - document.documentElement.clientWidth;

    document.body.style.overflow = 'hidden';
    if (scrollbarWidth > 0) {
      document.body.style.paddingRight = `${scrollbarWidth}px`;
    }

    return () => {
      document.body.style.overflow = originalOverflow;
      document.body.style.paddingRight = originalPaddingRight;
    };
  }, [isOpen]);

  // Focus management
  useEffect(() => {
    if (!isOpen) return;

    // Сохраняем элемент, который был в фокусе
    previouslyFocusedElement.current = document.activeElement as HTMLElement;

    // Фокус на первый интерактивный элемент
    const focusableElements = modalRef.current?.querySelectorAll<HTMLElement>(
      'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
    );

    if (focusableElements && focusableElements.length > 0) {
      // Небольшая задержка для завершения анимации
      setTimeout(() => {
        focusableElements[0].focus();
      }, 100);
    }

    // Возвращаем фокус при закрытии
    return () => {
      if (previouslyFocusedElement.current) {
        previouslyFocusedElement.current.focus();
      }
    };
  }, [isOpen]);

  // Focus trap
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
        // Shift+Tab
        if (document.activeElement === firstElement) {
          e.preventDefault();
          lastElement.focus();
        }
      } else {
        // Tab
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
      className="fixed inset-0 z-50 flex items-center justify-center p-4 animate-fadeIn"
      onClick={handleBackdropClick}
      role="presentation"
    >
      {/* Backdrop with blur */}
      <div
        className="absolute inset-0 bg-black/50 backdrop-blur-sm transition-opacity duration-[180ms]"
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
          'bg-white rounded-[24px]',
          'shadow-[0_24px_64px_rgba(15,23,42,0.24)]',
          'flex flex-col',
          'animate-scaleIn',
          SIZE_CLASSES[size],
          className
        )}
        onKeyDown={handleKeyDown}
      >
        {/* Header */}
        {(title || showCloseButton) && (
          <div className="flex items-start justify-between p-6 border-b border-[#E3E8F2]">
            {title && (
              <h2
                id={titleId}
                className="text-[20px] leading-[28px] font-semibold text-[#1B1B1B] pr-8"
              >
                {title}
              </h2>
            )}

            {/* Close Button */}
            {showCloseButton && (
              <button
                onClick={onClose}
                className={cn(
                  'flex items-center justify-center',
                  'w-11 h-11 rounded-xl',
                  'transition-colors duration-[180ms]',
                  'hover:bg-[#E3E8F2]',
                  'focus:outline-none focus:ring-2 focus:ring-[#1F1F1F]'
                )}
                aria-label="Закрыть модальное окно"
              >
                <X className="w-10 h-10 text-[#7A7A7A]" strokeWidth={1.5} />
              </button>
            )}
          </div>
        )}

        {/* Content */}
        <div id={descriptionId} className="flex-1 overflow-y-auto p-6 max-h-[calc(100vh-200px)]">
          {children}
        </div>

        {/* Footer */}
        {footer && (
          <div className="border-t border-[#E3E8F2] p-6 flex items-center justify-end gap-3">
            {footer}
          </div>
        )}
      </div>
    </div>
  );

  // Render через Portal
  return createPortal(modalContent, document.body);
};

Modal.displayName = 'Modal';
