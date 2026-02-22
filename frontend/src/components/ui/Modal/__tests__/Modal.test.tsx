/**
 * Modal Component Tests
 * Design System v2.0 - проверка размеров, Portal, body scroll lock, анимаций
 */

import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { Modal } from '../Modal';

describe('Modal', () => {
  const mockOnClose = vi.fn();

  beforeEach(() => {
    mockOnClose.mockClear();
    // Clear body styles
    document.body.style.overflow = '';
    document.body.style.paddingRight = '';
  });

  // Базовый рендеринг
  it('renders when isOpen is true', () => {
    render(
      <Modal isOpen={true} onClose={mockOnClose} title="Test Modal">
        <p>Modal content</p>
      </Modal>
    );

    expect(screen.getByRole('dialog')).toBeInTheDocument();
    expect(screen.getByText('Test Modal')).toBeInTheDocument();
    expect(screen.getByText('Modal content')).toBeInTheDocument();
  });

  it('does not render when isOpen is false', () => {
    render(
      <Modal isOpen={false} onClose={mockOnClose} title="Test Modal">
        <p>Modal content</p>
      </Modal>
    );

    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  });

  // Размеры
  describe('Sizes', () => {
    it('renders with sm size (400px)', () => {
      render(
        <Modal isOpen={true} onClose={mockOnClose} title="Small Modal" size="sm">
          Content
        </Modal>
      );

      const dialog = screen.getByRole('dialog');
      expect(dialog).toHaveClass('max-w-[400px]');
    });

    it('renders with md size (560px) as default', () => {
      render(
        <Modal isOpen={true} onClose={mockOnClose} title="Medium Modal">
          Content
        </Modal>
      );

      const dialog = screen.getByRole('dialog');
      expect(dialog).toHaveClass('max-w-[560px]');
    });

    it('renders with lg size (720px)', () => {
      render(
        <Modal isOpen={true} onClose={mockOnClose} title="Large Modal" size="lg">
          Content
        </Modal>
      );

      const dialog = screen.getByRole('dialog');
      expect(dialog).toHaveClass('max-w-[720px]');
    });

    it('renders with xl size (960px)', () => {
      render(
        <Modal isOpen={true} onClose={mockOnClose} title="XL Modal" size="xl">
          Content
        </Modal>
      );

      const dialog = screen.getByRole('dialog');
      expect(dialog).toHaveClass('max-w-[960px]');
    });

    it('renders with full size', () => {
      render(
        <Modal isOpen={true} onClose={mockOnClose} title="Full Modal" size="full">
          Content
        </Modal>
      );

      const dialog = screen.getByRole('dialog');
      expect(dialog).toHaveClass('max-w-full');
    });
  });

  // Стилизация Design System v2.0
  describe('Design System v2.0 Styling', () => {
    it('has border-radius 24px', () => {
      render(
        <Modal isOpen={true} onClose={mockOnClose} title="Test">
          Content
        </Modal>
      );

      const dialog = screen.getByRole('dialog');
      expect(dialog).toHaveClass('rounded-[24px]');
    });

    it('has modal shadow', () => {
      render(
        <Modal isOpen={true} onClose={mockOnClose} title="Test">
          Content
        </Modal>
      );

      const dialog = screen.getByRole('dialog');
      expect(dialog).toHaveClass('shadow-[0_24px_64px_rgba(15,23,42,0.24)]');
    });

    it('has animations', () => {
      render(
        <Modal isOpen={true} onClose={mockOnClose} title="Test">
          Content
        </Modal>
      );

      const dialog = screen.getByRole('dialog');
      expect(dialog).toHaveClass('animate-scaleIn');
    });
  });

  // ESC закрывает
  describe('Escape Key Close', () => {
    it('closes modal on ESC key press when closeOnEscape is true', async () => {
      render(
        <Modal isOpen={true} onClose={mockOnClose} title="Test" closeOnEscape={true}>
          Content
        </Modal>
      );

      const dialog = screen.getByRole('dialog');
      fireEvent.keyDown(dialog, { key: 'Escape' });
      expect(mockOnClose).toHaveBeenCalledTimes(1);
    });

    it('does not close on ESC when closeOnEscape is false', async () => {
      render(
        <Modal isOpen={true} onClose={mockOnClose} title="Test" closeOnEscape={false}>
          Content
        </Modal>
      );

      const dialog = screen.getByRole('dialog');
      fireEvent.keyDown(dialog, { key: 'Escape' });
      expect(mockOnClose).not.toHaveBeenCalled();
    });
  });

  // Backdrop click
  describe('Backdrop Click Close', () => {
    it('closes modal on backdrop click when closeOnBackdrop is true', async () => {
      render(
        <Modal isOpen={true} onClose={mockOnClose} title="Test" closeOnBackdrop={true}>
          Content
        </Modal>
      );

      const backdrop = screen.getByRole('presentation');
      await userEvent.click(backdrop);
      expect(mockOnClose).toHaveBeenCalledTimes(1);
    });

    it('does not close on backdrop click when closeOnBackdrop is false', async () => {
      render(
        <Modal isOpen={true} onClose={mockOnClose} title="Test" closeOnBackdrop={false}>
          Content
        </Modal>
      );

      const backdrop = screen.getByRole('presentation');
      await userEvent.click(backdrop);
      expect(mockOnClose).not.toHaveBeenCalled();
    });

    it('does not close on content area click', async () => {
      render(
        <Modal isOpen={true} onClose={mockOnClose} title="Test">
          <p>Content</p>
        </Modal>
      );

      const content = screen.getByText('Content');
      await userEvent.click(content);
      expect(mockOnClose).not.toHaveBeenCalled();
    });
  });

  // Close button
  describe('Close Button', () => {
    it('shows close button by default', () => {
      render(
        <Modal isOpen={true} onClose={mockOnClose} title="Test">
          Content
        </Modal>
      );

      expect(screen.getByLabelText('Закрыть модальное окно')).toBeInTheDocument();
    });

    it('hides close button when showCloseButton is false', () => {
      render(
        <Modal isOpen={true} onClose={mockOnClose} title="Test" showCloseButton={false}>
          Content
        </Modal>
      );

      expect(screen.queryByLabelText('Закрыть модальное окно')).not.toBeInTheDocument();
    });

    it('closes modal when close button is clicked', async () => {
      render(
        <Modal isOpen={true} onClose={mockOnClose} title="Test">
          Content
        </Modal>
      );

      const closeButton = screen.getByLabelText('Закрыть модальное окно');
      await userEvent.click(closeButton);
      expect(mockOnClose).toHaveBeenCalledTimes(1);
    });
  });

  // Footer
  describe('Footer', () => {
    it('renders footer when provided', () => {
      render(
        <Modal isOpen={true} onClose={mockOnClose} title="Test" footer={<button>Save</button>}>
          Content
        </Modal>
      );

      expect(screen.getByRole('button', { name: 'Save' })).toBeInTheDocument();
    });

    it('does not render footer when not provided', () => {
      render(
        <Modal isOpen={true} onClose={mockOnClose} title="Test">
          Content
        </Modal>
      );

      // Footer элемент не существует если footer не передан
      const dialog = screen.getByRole('dialog');
      const footerBorder = dialog.querySelector('.border-t.border-\\[\\#E3E8F2\\]');
      expect(footerBorder).not.toBeInTheDocument();
    });
  });

  // Accessibility
  describe('Accessibility', () => {
    it('has correct ARIA attributes', () => {
      render(
        <Modal isOpen={true} onClose={mockOnClose} title="Test Modal">
          Modal content description
        </Modal>
      );

      const dialog = screen.getByRole('dialog');
      expect(dialog).toHaveAttribute('aria-modal', 'true');
      expect(dialog).toHaveAttribute('aria-labelledby');
      expect(dialog).toHaveAttribute('aria-describedby');
    });

    it('sets aria-labelledby to title id when title is provided', () => {
      render(
        <Modal isOpen={true} onClose={mockOnClose} title="Test Modal">
          Content
        </Modal>
      );

      const dialog = screen.getByRole('dialog');
      const titleId = dialog.getAttribute('aria-labelledby');
      expect(titleId).toBeTruthy();

      const title = document.getElementById(titleId!);
      expect(title).toHaveTextContent('Test Modal');
    });
  });

  // Body scroll lock
  describe('Body Scroll Lock', () => {
    it('locks body scroll when modal opens', () => {
      render(
        <Modal isOpen={true} onClose={mockOnClose} title="Test">
          Content
        </Modal>
      );

      expect(document.body.style.overflow).toBe('hidden');
    });

    it('restores body scroll when modal closes', () => {
      const { rerender } = render(
        <Modal isOpen={true} onClose={mockOnClose} title="Test">
          Content
        </Modal>
      );

      expect(document.body.style.overflow).toBe('hidden');

      rerender(
        <Modal isOpen={false} onClose={mockOnClose} title="Test">
          Content
        </Modal>
      );

      expect(document.body.style.overflow).toBe('');
    });
  });

  // Focus trap
  describe('Focus Trap', () => {
    it('focuses first focusable element on open', async () => {
      render(
        <Modal isOpen={true} onClose={mockOnClose} title="Test">
          <button>First</button>
          <button>Second</button>
        </Modal>
      );

      // Close button должен получить фокус первым (так как он первый в DOM)
      await waitFor(() => {
        const closeButton = screen.getByLabelText('Закрыть модальное окно');
        expect(closeButton).toHaveFocus();
      });
    });

    it('traps Tab navigation inside modal', async () => {
      render(
        <Modal isOpen={true} onClose={mockOnClose} title="Test">
          <button>First</button>
          <button>Second</button>
        </Modal>
      );

      const closeButton = screen.getByLabelText('Закрыть модальное окно');
      const firstButton = screen.getByText('First');
      const secondButton = screen.getByText('Second');

      // Focus starts at close button
      await waitFor(() => {
        expect(closeButton).toHaveFocus();
      });

      // Tab to first button
      await userEvent.tab();
      expect(firstButton).toHaveFocus();

      // Tab to second button
      await userEvent.tab();
      expect(secondButton).toHaveFocus();

      // Tab should cycle back to close button
      await userEvent.tab();
      expect(closeButton).toHaveFocus();
    });

    it('traps Shift+Tab navigation inside modal', async () => {
      render(
        <Modal isOpen={true} onClose={mockOnClose} title="Test">
          <button>First</button>
          <button>Second</button>
        </Modal>
      );

      const closeButton = screen.getByLabelText('Закрыть модальное окно');
      const secondButton = screen.getByText('Second');

      await waitFor(() => {
        expect(closeButton).toHaveFocus();
      });

      // Shift+Tab should cycle to last element
      await userEvent.tab({ shift: true });
      expect(secondButton).toHaveFocus();
    });
  });

  // Content overflow
  describe('Content Overflow', () => {
    it('applies scrollable class to content area', () => {
      render(
        <Modal isOpen={true} onClose={mockOnClose} title="Test">
          <div style={{ height: '2000px' }}>Very long content</div>
        </Modal>
      );

      const dialog = screen.getByRole('dialog');
      const contentArea = dialog.querySelector('.overflow-y-auto');
      expect(contentArea).toBeInTheDocument();
    });
  });

  // Custom className
  it('accepts custom className', () => {
    render(
      <Modal isOpen={true} onClose={mockOnClose} title="Test" className="custom-modal">
        Content
      </Modal>
    );

    const dialog = screen.getByRole('dialog');
    expect(dialog).toHaveClass('custom-modal');
  });

  // Render without title
  it('renders without title', () => {
    render(
      <Modal isOpen={true} onClose={mockOnClose}>
        Content only
      </Modal>
    );

    expect(screen.getByRole('dialog')).toBeInTheDocument();
    expect(screen.getByText('Content only')).toBeInTheDocument();
  });
});
