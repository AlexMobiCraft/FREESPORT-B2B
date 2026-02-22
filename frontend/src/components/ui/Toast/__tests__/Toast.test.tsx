/**
 * Toast Component Tests
 * Design System v2.0
 */

import React, { act } from 'react';
import { fireEvent, render, screen } from '@testing-library/react';
import { Toast } from '../Toast';

describe('Toast', () => {
  const mockOnClose = vi.fn();

  beforeEach(() => {
    mockOnClose.mockClear();
  });

  // Рендеринг вариантов
  describe('Variants', () => {
    it('renders success variant', () => {
      render(<Toast id="test" variant="success" message="Success message" onClose={mockOnClose} />);

      expect(screen.getByRole('alert')).toBeInTheDocument();
      expect(screen.getByText('Success message')).toBeInTheDocument();
    });

    it('renders error variant', () => {
      render(<Toast id="test" variant="error" message="Error message" onClose={mockOnClose} />);

      expect(screen.getByText('Error message')).toBeInTheDocument();
    });

    it('renders warning variant', () => {
      render(<Toast id="test" variant="warning" message="Warning message" onClose={mockOnClose} />);

      expect(screen.getByText('Warning message')).toBeInTheDocument();
    });

    it('renders info variant', () => {
      render(<Toast id="test" variant="info" message="Info message" onClose={mockOnClose} />);

      expect(screen.getByText('Info message')).toBeInTheDocument();
    });
  });

  // Title
  it('renders with title', () => {
    render(
      <Toast
        id="test"
        variant="success"
        title="Success Title"
        message="Success message"
        onClose={mockOnClose}
      />
    );

    expect(screen.getByText('Success Title')).toBeInTheDocument();
    expect(screen.getByText('Success message')).toBeInTheDocument();
  });

  it('renders without title', () => {
    render(<Toast id="test" variant="success" message="Success message" onClose={mockOnClose} />);

    expect(screen.getByText('Success message')).toBeInTheDocument();
  });

  // Auto-dismiss
  describe('Auto-dismiss', () => {
    beforeEach(() => {
      vi.useFakeTimers();
    });

    afterEach(() => {
      vi.useRealTimers();
    });

    it('calls onClose after duration', () => {
      render(
        <Toast
          id="test-1"
          variant="success"
          message="Auto close"
          duration={5000}
          onClose={mockOnClose}
        />
      );

      expect(mockOnClose).not.toHaveBeenCalled();

      // Advance timers by duration + animation time (300ms для fade out)
      act(() => {
        vi.advanceTimersByTime(5000 + 300);
      });

      expect(mockOnClose).toHaveBeenCalledWith('test-1');
    });

    it('does not auto-dismiss when duration is 0', () => {
      render(
        <Toast
          id="test"
          variant="success"
          message="No auto close"
          duration={0}
          onClose={mockOnClose}
        />
      );

      act(() => {
        vi.advanceTimersByTime(10000);
      });

      expect(mockOnClose).not.toHaveBeenCalled();
    });
  });

  // Close button
  describe('Close Button', () => {
    it('shows close button', () => {
      render(<Toast id="test" variant="success" message="Message" onClose={mockOnClose} />);

      expect(screen.getByLabelText('Закрыть уведомление')).toBeInTheDocument();
    });

    it('calls onClose when close button clicked', () => {
      vi.useFakeTimers();

      try {
        render(
          <Toast
            id="test-1"
            variant="success"
            message="Message"
            onClose={mockOnClose}
            duration={0}
          />
        );

        const closeButton = screen.getByLabelText('Закрыть уведомление');
        act(() => {
          fireEvent.click(closeButton);
        });

        // Wait for animation (300ms для fade out)
        act(() => {
          vi.advanceTimersByTime(300);
        });

        expect(mockOnClose).toHaveBeenCalledWith('test-1');
      } finally {
        vi.useRealTimers();
      }
    });
  });

  // Accessibility
  describe('Accessibility', () => {
    it('has correct ARIA attributes', () => {
      render(<Toast id="test" variant="success" message="Message" onClose={mockOnClose} />);

      const toast = screen.getByRole('alert');
      expect(toast).toHaveAttribute('aria-live', 'polite');
    });
  });

  // Animations
  it('has slide-in animation class', () => {
    render(<Toast id="test" variant="success" message="Message" onClose={mockOnClose} />);

    const toast = screen.getByRole('alert');
    expect(toast).toHaveClass('animate-slideInRight');
  });
});
