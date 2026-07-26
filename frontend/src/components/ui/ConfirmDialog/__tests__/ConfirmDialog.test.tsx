/**
 * ConfirmDialog Component Tests
 * Design System v2.0
 */

import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { ConfirmDialog } from '../ConfirmDialog';

describe('ConfirmDialog', () => {
  const mockOnClose = vi.fn();
  const mockOnConfirm = vi.fn();

  beforeEach(() => {
    mockOnClose.mockClear();
    mockOnConfirm.mockClear();
  });

  // Базовый рендеринг
  it('renders when open', () => {
    render(
      <ConfirmDialog
        isOpen={true}
        onClose={mockOnClose}
        onConfirm={mockOnConfirm}
        title="Confirm Action"
        message="Are you sure?"
      />
    );

    expect(screen.getByText('Confirm Action')).toBeInTheDocument();
    expect(screen.getByText('Are you sure?')).toBeInTheDocument();
  });

  it('does not render when closed', () => {
    render(
      <ConfirmDialog
        isOpen={false}
        onClose={mockOnClose}
        onConfirm={mockOnConfirm}
        title="Confirm Action"
        message="Are you sure?"
      />
    );

    expect(screen.queryByText('Confirm Action')).not.toBeInTheDocument();
  });

  // Варианты
  describe('Variants', () => {
    it('renders default variant without icon', () => {
      render(
        <ConfirmDialog
          isOpen={true}
          onClose={mockOnClose}
          onConfirm={mockOnConfirm}
          title="Confirm"
          message="Message"
          variant="default"
        />
      );

      expect(screen.getByText('Confirm')).toBeInTheDocument();
    });

    it('renders danger variant with warning icon', () => {
      render(
        <ConfirmDialog
          isOpen={true}
          onClose={mockOnClose}
          onConfirm={mockOnConfirm}
          title="Delete Item"
          message="This action cannot be undone"
          variant="danger"
        />
      );

      expect(screen.getByText('Delete Item')).toBeInTheDocument();
      // Check for icon container with danger background
      const iconContainer = document.querySelector('.bg-\\[\\#FFE1E1\\]');
      expect(iconContainer).toBeInTheDocument();
    });
  });

  // Кнопки
  describe('Buttons', () => {
    it('renders default button texts', () => {
      render(
        <ConfirmDialog
          isOpen={true}
          onClose={mockOnClose}
          onConfirm={mockOnConfirm}
          title="Confirm"
          message="Message"
        />
      );

      expect(screen.getByRole('button', { name: 'Отмена' })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: 'Подтвердить' })).toBeInTheDocument();
    });

    it('renders custom button texts', () => {
      render(
        <ConfirmDialog
          isOpen={true}
          onClose={mockOnClose}
          onConfirm={mockOnConfirm}
          title="Confirm"
          message="Message"
          confirmText="Yes"
          cancelText="No"
        />
      );

      expect(screen.getByRole('button', { name: 'No' })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: 'Yes' })).toBeInTheDocument();
    });
  });

  // Действия
  describe('Actions', () => {
    it('calls onClose when cancel button clicked', async () => {
      render(
        <ConfirmDialog
          isOpen={true}
          onClose={mockOnClose}
          onConfirm={mockOnConfirm}
          title="Confirm"
          message="Message"
        />
      );

      const cancelButton = screen.getByRole('button', { name: 'Отмена' });
      await userEvent.click(cancelButton);

      expect(mockOnClose).toHaveBeenCalledTimes(1);
      expect(mockOnConfirm).not.toHaveBeenCalled();
    });

    it('calls onConfirm and onClose when confirm button clicked', async () => {
      render(
        <ConfirmDialog
          isOpen={true}
          onClose={mockOnClose}
          onConfirm={mockOnConfirm}
          title="Confirm"
          message="Message"
        />
      );

      const confirmButton = screen.getByRole('button', { name: 'Подтвердить' });
      await userEvent.click(confirmButton);

      await waitFor(() => {
        expect(mockOnConfirm).toHaveBeenCalledTimes(1);
        expect(mockOnClose).toHaveBeenCalledTimes(1);
      });
    });

    it('handles async onConfirm', async () => {
      const asyncConfirm = vi.fn().mockResolvedValue(undefined);

      render(
        <ConfirmDialog
          isOpen={true}
          onClose={mockOnClose}
          onConfirm={asyncConfirm}
          title="Confirm"
          message="Message"
        />
      );

      const confirmButton = screen.getByRole('button', { name: 'Подтвердить' });
      await userEvent.click(confirmButton);

      await waitFor(() => {
        expect(asyncConfirm).toHaveBeenCalledTimes(1);
        expect(mockOnClose).toHaveBeenCalledTimes(1);
      });
    });
  });

  // Loading state
  describe('Loading State', () => {
    it('disables buttons when loading', () => {
      render(
        <ConfirmDialog
          isOpen={true}
          onClose={mockOnClose}
          onConfirm={mockOnConfirm}
          title="Confirm"
          message="Message"
          isLoading={true}
        />
      );

      const cancelButton = screen.getByRole('button', { name: 'Отмена' });
      const confirmButton = screen.getByRole('button', { name: 'Подтвердить' });

      expect(cancelButton).toBeDisabled();
      expect(confirmButton).toBeDisabled();
    });

    it('shows loading state during async confirm', async () => {
      let resolvePromise: () => void;
      const asyncConfirm = vi.fn(
        () =>
          new Promise<void>(resolve => {
            resolvePromise = resolve;
          })
      );

      render(
        <ConfirmDialog
          isOpen={true}
          onClose={mockOnClose}
          onConfirm={asyncConfirm}
          title="Confirm"
          message="Message"
        />
      );

      const confirmButton = screen.getByRole('button', { name: 'Подтвердить' });
      await userEvent.click(confirmButton);

      // Should be disabled during loading
      await waitFor(() => {
        expect(confirmButton).toBeDisabled();
      });

      // Resolve promise
      resolvePromise!();

      await waitFor(() => {
        expect(mockOnClose).toHaveBeenCalled();
      });
    });
  });

  // Size
  it('uses small size from Modal', () => {
    render(
      <ConfirmDialog
        isOpen={true}
        onClose={mockOnClose}
        onConfirm={mockOnConfirm}
        title="Confirm"
        message="Message"
      />
    );

    const dialog = screen.getByRole('dialog');
    expect(dialog).toHaveClass('max-w-[400px]'); // sm size
  });
});
