'use client';

/**
 * ToastProvider Component
 * Контекст и провайдер для управления toast уведомлениями
 * Design System v2.0
 */

import React, { createContext, useContext, useState, useCallback, useEffect } from 'react';
import { createPortal } from 'react-dom';
import { Toast, ToastVariant, ToastPosition } from './Toast';

export interface ToastOptions {
  variant?: ToastVariant;
  title?: string;
  message: string;
  duration?: number;
  position?: ToastPosition;
}

export interface ToastContextValue {
  toast: (options: ToastOptions) => string;
  success: (message: string, title?: string) => string;
  error: (message: string, title?: string) => string;
  warning: (message: string, title?: string) => string;
  info: (message: string, title?: string) => string;
  dismiss: (id: string) => void;
  dismissAll: () => void;
}

interface ToastItem extends ToastOptions {
  id: string;
  variant: ToastVariant;
}

const ToastContext = createContext<ToastContextValue | null>(null);

const POSITION_CLASSES: Record<ToastPosition, string> = {
  'top-right': 'top-4 right-4',
  'top-center': 'top-4 left-1/2 -translate-x-1/2',
  'bottom-right': 'bottom-4 right-4',
  'bottom-center': 'bottom-4 left-1/2 -translate-x-1/2',
};

const MAX_VISIBLE_TOASTS = 5;

export const ToastProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [toasts, setToasts] = useState<ToastItem[]>([]);
  const [isMounted, setIsMounted] = useState(false);

  // Проверяем, что компонент смонтирован (клиент)
  useEffect(() => {
    setIsMounted(true);
  }, []);

  const generateId = useCallback(() => {
    return `toast-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
  }, []);

  const toast = useCallback(
    (options: ToastOptions): string => {
      const id = generateId();
      const newToast: ToastItem = {
        ...options,
        id,
        variant: options.variant || 'info',
      };

      setToasts(prev => {
        const updated = [...prev, newToast];
        // Ограничиваем количество видимых toasts
        if (updated.length > MAX_VISIBLE_TOASTS) {
          return updated.slice(-MAX_VISIBLE_TOASTS);
        }
        return updated;
      });

      return id;
    },
    [generateId]
  );

  const success = useCallback(
    (message: string, title?: string): string => {
      return toast({ variant: 'success', message, title });
    },
    [toast]
  );

  const error = useCallback(
    (message: string, title?: string): string => {
      return toast({ variant: 'error', message, title });
    },
    [toast]
  );

  const warning = useCallback(
    (message: string, title?: string): string => {
      return toast({ variant: 'warning', message, title });
    },
    [toast]
  );

  const info = useCallback(
    (message: string, title?: string): string => {
      return toast({ variant: 'info', message, title });
    },
    [toast]
  );

  const dismiss = useCallback((id: string) => {
    setToasts(prev => prev.filter(t => t.id !== id));
  }, []);

  const dismissAll = useCallback(() => {
    setToasts([]);
  }, []);

  const value: ToastContextValue = {
    toast,
    success,
    error,
    warning,
    info,
    dismiss,
    dismissAll,
  };

  // Группируем toasts по позиции
  const toastsByPosition = toasts.reduce(
    (acc, toast) => {
      const position = toast.position || 'top-right';
      if (!acc[position]) {
        acc[position] = [];
      }
      acc[position].push(toast);
      return acc;
    },
    {} as Record<ToastPosition, ToastItem[]>
  );

  return (
    <ToastContext.Provider value={value}>
      {children}
      {/* Render toast containers для каждой позиции (только на клиенте) */}
      {isMounted &&
        Object.entries(toastsByPosition).map(([position, positionToasts]) => {
          if (positionToasts.length === 0) return null;

          const positionClass = POSITION_CLASSES[position as ToastPosition];

          return createPortal(
            <div
              key={position}
              className={`fixed z-[100] flex flex-col gap-3 ${positionClass}`}
              aria-live="polite"
              aria-atomic="true"
            >
              {positionToasts.map(toastItem => (
                <Toast
                  key={toastItem.id}
                  id={toastItem.id}
                  variant={toastItem.variant}
                  title={toastItem.title}
                  message={toastItem.message}
                  duration={toastItem.duration}
                  position={toastItem.position}
                  onClose={dismiss}
                />
              ))}
            </div>,
            document.body
          );
        })}
    </ToastContext.Provider>
  );
};

/**
 * useToast Hook
 * Хук для использования toast уведомлений
 *
 * @example
 * const { success, error } = useToast();
 * success('Товар добавлен в корзину');
 * error('Ошибка при оформлении заказа');
 */
export const useToast = (): ToastContextValue => {
  const context = useContext(ToastContext);

  if (!context) {
    throw new Error('useToast must be used within ToastProvider');
  }

  return context;
};
