/**
 * InfoPanel Component Tests
 * Покрытие variant, title, message, dismissible, icons
 *
 * Story 15.2: Расширены тесты для нового API
 */

import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import { InfoPanel } from '../InfoPanel';

describe('InfoPanel', () => {
  // Базовый рендеринг
  describe('Basic Rendering', () => {
    it('renders info panel with children', () => {
      render(<InfoPanel>Important information</InfoPanel>);

      expect(screen.getByText('Important information')).toBeInTheDocument();
    });

    it('renders with message prop', () => {
      render(<InfoPanel message="Message from prop" />);

      expect(screen.getByText('Message from prop')).toBeInTheDocument();
    });

    it('renders with title prop', () => {
      render(<InfoPanel title="Test Title">Content</InfoPanel>);

      expect(screen.getByText('Test Title')).toBeInTheDocument();
      expect(screen.getByText('Content')).toBeInTheDocument();
    });

    it('renders with both title and message', () => {
      render(<InfoPanel title="Error Title" message="Error message" />);

      expect(screen.getByText('Error Title')).toBeInTheDocument();
      expect(screen.getByText('Error message')).toBeInTheDocument();
    });

    it('children takes priority over message', () => {
      render(<InfoPanel message="From message">From children</InfoPanel>);

      expect(screen.getByText('From children')).toBeInTheDocument();
      expect(screen.queryByText('From message')).not.toBeInTheDocument();
    });

    it('has role="alert" for accessibility', () => {
      render(<InfoPanel>Message</InfoPanel>);

      expect(screen.getByRole('alert')).toBeInTheDocument();
    });
  });

  // Variants
  describe('Variants', () => {
    it('renders info variant by default with primary styling', () => {
      const { container } = render(<InfoPanel>Message</InfoPanel>);

      const panel = container.firstChild as HTMLElement;
      expect(panel).toHaveClass('bg-primary-subtle', 'border-primary/20');
    });

    it('renders warning variant with amber styling', () => {
      const { container } = render(<InfoPanel variant="warning">Message</InfoPanel>);

      const panel = container.firstChild as HTMLElement;
      expect(panel).toHaveClass('bg-amber-50', 'border-amber-200');
    });

    it('renders error variant with red styling', () => {
      const { container } = render(<InfoPanel variant="error">Message</InfoPanel>);

      const panel = container.firstChild as HTMLElement;
      expect(panel).toHaveClass('bg-red-50', 'border-red-200');
    });

    it('renders success variant with green styling', () => {
      const { container } = render(<InfoPanel variant="success">Message</InfoPanel>);

      const panel = container.firstChild as HTMLElement;
      expect(panel).toHaveClass('bg-green-50', 'border-green-200');
    });
  });

  // Icon
  describe('Icon', () => {
    it('renders default icon based on variant', () => {
      const { container } = render(<InfoPanel>Message</InfoPanel>);

      const icon = container.querySelector('svg[aria-hidden="true"]');
      expect(icon).toBeInTheDocument();
    });

    it('renders custom icon when provided', () => {
      const CustomIcon = () => <svg data-testid="custom-icon" />;
      render(<InfoPanel icon={<CustomIcon />}>Message</InfoPanel>);

      expect(screen.getByTestId('custom-icon')).toBeInTheDocument();
    });

    it('icon container has proper styling', () => {
      const { container } = render(<InfoPanel>Message</InfoPanel>);

      const iconContainer = container.querySelector('.w-12.h-12');
      expect(iconContainer).toHaveClass('rounded-xl');
    });

    it('error variant shows error icon with red color', () => {
      const { container } = render(<InfoPanel variant="error">Message</InfoPanel>);

      const iconWrapper = container.querySelector('.text-red-600');
      expect(iconWrapper).toBeInTheDocument();
    });

    it('warning variant shows warning icon with amber color', () => {
      const { container } = render(<InfoPanel variant="warning">Message</InfoPanel>);

      const iconWrapper = container.querySelector('.text-amber-600');
      expect(iconWrapper).toBeInTheDocument();
    });
  });

  // Edge Case: Dismissible
  describe('Dismissible', () => {
    it('does not show close button when onDismiss is not provided', () => {
      render(<InfoPanel>Message</InfoPanel>);

      const closeButton = screen.queryByLabelText('Закрыть');
      expect(closeButton).not.toBeInTheDocument();
    });

    it('shows close button when onDismiss is provided', () => {
      const handleDismiss = vi.fn();
      render(<InfoPanel onDismiss={handleDismiss}>Message</InfoPanel>);

      const closeButton = screen.getByLabelText('Закрыть');
      expect(closeButton).toBeInTheDocument();
    });

    it('calls onDismiss when close button is clicked', () => {
      const handleDismiss = vi.fn();
      render(<InfoPanel onDismiss={handleDismiss}>Message</InfoPanel>);

      const closeButton = screen.getByLabelText('Закрыть');
      fireEvent.click(closeButton);

      expect(handleDismiss).toHaveBeenCalledTimes(1);
    });

    it('hides panel when close button is clicked', () => {
      const handleDismiss = vi.fn();
      render(<InfoPanel onDismiss={handleDismiss}>Message</InfoPanel>);

      const closeButton = screen.getByLabelText('Закрыть');
      fireEvent.click(closeButton);

      expect(screen.queryByText('Message')).not.toBeInTheDocument();
    });

    it('close button has hover effect', () => {
      const handleDismiss = vi.fn();
      render(<InfoPanel onDismiss={handleDismiss}>Message</InfoPanel>);

      const closeButton = screen.getByLabelText('Закрыть');
      expect(closeButton).toHaveClass('hover:bg-neutral-200');
    });

    it('close button has focus ring', () => {
      const handleDismiss = vi.fn();
      render(<InfoPanel onDismiss={handleDismiss}>Message</InfoPanel>);

      const closeButton = screen.getByLabelText('Закрыть');
      expect(closeButton).toHaveClass('focus:ring-2', 'focus:ring-primary');
    });
  });

  // Edge Case: Длинный текст
  describe('Long Text', () => {
    it('wraps long text to multiple lines', () => {
      const longText =
        'This is a very long informational message that should wrap to multiple lines and not overflow the container. It should be readable and properly formatted.';
      const { container } = render(<InfoPanel>{longText}</InfoPanel>);

      const textContainer = container.querySelector('.whitespace-normal');
      expect(textContainer).toHaveClass('break-words');
    });

    it('has proper text styling', () => {
      const { container } = render(<InfoPanel>Message</InfoPanel>);

      const textContainer = container.querySelector('.text-body-m');
      expect(textContainer).toBeInTheDocument();
    });
  });

  // Edge Case: Fade-out анимация
  describe('Fade-out Animation', () => {
    it('has transition duration of 200ms', () => {
      const { container } = render(<InfoPanel>Message</InfoPanel>);

      const panel = container.firstChild as HTMLElement;
      expect(panel).toHaveClass('transition-opacity', 'duration-[200ms]');
    });
  });

  // Styling
  describe('Styling', () => {
    it('has grid layout', () => {
      const { container } = render(<InfoPanel>Message</InfoPanel>);

      const panel = container.firstChild as HTMLElement;
      expect(panel).toHaveClass('grid', 'grid-cols-[auto_1fr]', 'gap-4');
    });

    it('has rounded corners', () => {
      const { container } = render(<InfoPanel>Message</InfoPanel>);

      const panel = container.firstChild as HTMLElement;
      expect(panel).toHaveClass('rounded-md');
    });

    it('has proper padding', () => {
      const { container } = render(<InfoPanel>Message</InfoPanel>);

      const panel = container.firstChild as HTMLElement;
      expect(panel).toHaveClass('p-5');
    });
  });

  // Accessibility
  describe('Accessibility', () => {
    it('forwards ref correctly', () => {
      const ref = React.createRef<HTMLDivElement>();
      render(<InfoPanel ref={ref}>Message</InfoPanel>);

      expect(ref.current).toBeInstanceOf(HTMLDivElement);
    });

    it('close button has aria-label', () => {
      const handleDismiss = vi.fn();
      render(<InfoPanel onDismiss={handleDismiss}>Message</InfoPanel>);

      const closeButton = screen.getByLabelText('Закрыть');
      expect(closeButton).toHaveAttribute('aria-label', 'Закрыть');
    });

    it('icon has aria-hidden', () => {
      const { container } = render(<InfoPanel>Message</InfoPanel>);

      const icon = container.querySelector('svg');
      expect(icon).toHaveAttribute('aria-hidden', 'true');
    });
  });

  // Custom className
  it('accepts custom className', () => {
    const { container } = render(<InfoPanel className="custom-class">Message</InfoPanel>);

    const panel = container.firstChild as HTMLElement;
    expect(panel).toHaveClass('custom-class');
  });

  // Custom props
  it('accepts custom HTML attributes', () => {
    render(<InfoPanel data-testid="custom-panel">Message</InfoPanel>);

    expect(screen.getByTestId('custom-panel')).toBeInTheDocument();
  });

  // Complex content
  it('renders complex nested content', () => {
    render(
      <InfoPanel>
        <div>
          <strong>Important:</strong> This is a message with <em>formatting</em>.
        </div>
      </InfoPanel>
    );

    expect(screen.getByText(/Important:/)).toBeInTheDocument();
    expect(screen.getByText(/formatting/)).toBeInTheDocument();
  });

  // Story 15.2 specific tests
  describe('Checkout Form Integration', () => {
    it('renders error variant with title and message for API errors', () => {
      render(
        <InfoPanel variant="error" title="Ошибка оформления заказа" message="Недостаточно товара" />
      );

      expect(screen.getByText('Ошибка оформления заказа')).toBeInTheDocument();
      expect(screen.getByText('Недостаточно товара')).toBeInTheDocument();
    });

    it('renders warning variant for empty cart', () => {
      render(
        <InfoPanel variant="warning" title="Корзина пуста" message="Добавьте товары в корзину" />
      );

      expect(screen.getByText('Корзина пуста')).toBeInTheDocument();
      expect(screen.getByText('Добавьте товары в корзину')).toBeInTheDocument();
    });
  });
});
