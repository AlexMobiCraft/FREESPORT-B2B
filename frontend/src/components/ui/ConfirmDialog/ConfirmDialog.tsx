/**
 * ConfirmDialog Component
 * Диалог подтверждения действия
 * Design System v2.0
 *
 * @see docs/frontend/design-system.json#components.ConfirmDialog
 */

'use client';

import React, { useState } from 'react';
import { AlertTriangle } from 'lucide-react';
import { Modal } from '../Modal';
import { Button } from '../Button';

export interface ConfirmDialogProps {
  /** Открыт ли диалог */
  isOpen: boolean;
  /** Callback при закрытии */
  onClose: () => void;
  /** Callback при подтверждении */
  onConfirm: () => void | Promise<void>;
  /** Заголовок */
  title: string;
  /** Сообщение */
  message: string;
  /** Текст кнопки подтверждения */
  confirmText?: string;
  /** Текст кнопки отмены */
  cancelText?: string;
  /** Вариант диалога */
  variant?: 'default' | 'danger';
  /** Состояние загрузки */
  isLoading?: boolean;
}

export const ConfirmDialog: React.FC<ConfirmDialogProps> = ({
  isOpen,
  onClose,
  onConfirm,
  title,
  message,
  confirmText = 'Подтвердить',
  cancelText = 'Отмена',
  variant = 'default',
  isLoading: externalLoading,
}) => {
  const [internalLoading, setInternalLoading] = useState(false);
  const isLoading = externalLoading !== undefined ? externalLoading : internalLoading;

  const handleConfirm = async () => {
    try {
      setInternalLoading(true);
      const result = onConfirm();

      // Проверяем если это Promise
      if (result instanceof Promise) {
        await result;
      }

      onClose();
    } catch (error) {
      console.error('ConfirmDialog: Error during confirmation:', error);
      // Не закрываем диалог при ошибке, позволяя пользователю попробовать снова
    } finally {
      setInternalLoading(false);
    }
  };

  const isDanger = variant === 'danger';

  return (
    <Modal isOpen={isOpen} onClose={onClose} size="sm" showCloseButton={false}>
      {/* Icon */}
      {isDanger && (
        <div className="flex justify-center mb-4">
          <div className="w-12 h-12 rounded-full bg-[#FFE1E1] flex items-center justify-center">
            <AlertTriangle className="w-6 h-6 text-[#C23B3B]" strokeWidth={2} />
          </div>
        </div>
      )}

      {/* Title */}
      <h2 className="text-[20px] leading-[28px] font-semibold text-[#1B1B1B] text-center mb-2">
        {title}
      </h2>

      {/* Message */}
      <p className="text-[16px] leading-[24px] font-medium text-[#4D4D4D] text-center mb-6">
        {message}
      </p>

      {/* Actions */}
      <div className="flex gap-3 justify-center">
        <Button variant="tertiary" onClick={onClose} disabled={isLoading} size="medium">
          {cancelText}
        </Button>
        <Button
          variant={isDanger ? 'danger' : 'primary'}
          onClick={handleConfirm}
          loading={isLoading}
          disabled={isLoading}
          size="medium"
        >
          {confirmText}
        </Button>
      </div>
    </Modal>
  );
};

ConfirmDialog.displayName = 'ConfirmDialog';
