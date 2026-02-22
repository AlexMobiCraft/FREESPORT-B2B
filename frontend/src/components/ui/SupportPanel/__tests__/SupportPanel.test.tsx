/**
 * SupportPanel Component Tests
 * Покрытие вариантов (delivery, availability), dismissible, длинного текста
 */

import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import { SupportPanel } from '../SupportPanel';

describe('SupportPanel', () => {
  // Базовый рендеринг
  it('renders support panel with value', () => {
    render(<SupportPanel variant="delivery" value="Доставка завтра" />);

    expect(screen.getByText('Доставка завтра')).toBeInTheDocument();
  });

  // Варианты
  describe('Variants', () => {
    it('renders delivery variant with correct styles', () => {
      const { container } = render(<SupportPanel variant="delivery" value="Delivery" />);

      const panel = container.firstChild as HTMLElement;
      expect(panel).toHaveClass('bg-neutral-100', 'border-primary/12');
    });

    it('renders availability variant with correct styles', () => {
      const { container } = render(<SupportPanel variant="availability" value="In Stock" />);

      const panel = container.firstChild as HTMLElement;
      expect(panel).toHaveClass('bg-neutral-200');
    });

    it('delivery variant has default Truck icon', () => {
      const { container } = render(<SupportPanel variant="delivery" value="Delivery" />);

      const icon = container.querySelector('svg[aria-hidden="true"]');
      expect(icon).toBeInTheDocument();
    });

    it('availability variant has default CheckCircle icon', () => {
      const { container } = render(<SupportPanel variant="availability" value="Available" />);

      const icon = container.querySelector('svg[aria-hidden="true"]');
      expect(icon).toBeInTheDocument();
    });
  });

  // Content fields
  describe('Content Fields', () => {
    it('renders value (main text)', () => {
      render(<SupportPanel variant="delivery" value="Main text" />);

      const value = screen.getByText('Main text');
      expect(value).toHaveClass('text-body-l', 'font-semibold', 'text-text-primary');
    });

    it('renders description when provided', () => {
      render(<SupportPanel variant="delivery" value="Main" description="Secondary text" />);

      const description = screen.getByText('Secondary text');
      expect(description).toHaveClass('text-body-s', 'text-text-secondary');
    });

    it('does not render description when not provided', () => {
      const { container } = render(<SupportPanel variant="delivery" value="Main" />);

      const description = container.querySelector('.text-body-s');
      expect(description).not.toBeInTheDocument();
    });

    it('renders meta when provided', () => {
      render(<SupportPanel variant="delivery" value="Main" meta="Additional info" />);

      const meta = screen.getByText('Additional info');
      expect(meta).toHaveClass('text-caption', 'text-text-muted');
    });

    it('does not render meta when not provided', () => {
      const { container } = render(<SupportPanel variant="delivery" value="Main" />);

      const meta = container.querySelector('.text-caption');
      expect(meta).not.toBeInTheDocument();
    });

    it('renders all content fields together', () => {
      render(
        <SupportPanel
          variant="delivery"
          value="Main text"
          description="Description"
          meta="Meta info"
        />
      );

      expect(screen.getByText('Main text')).toBeInTheDocument();
      expect(screen.getByText('Description')).toBeInTheDocument();
      expect(screen.getByText('Meta info')).toBeInTheDocument();
    });
  });

  // Icon
  describe('Icon', () => {
    it('renders custom icon when provided', () => {
      const CustomIcon = () => <svg data-testid="custom-icon" />;
      render(<SupportPanel variant="delivery" value="Value" icon={<CustomIcon />} />);

      expect(screen.getByTestId('custom-icon')).toBeInTheDocument();
    });

    it('icon container has proper styling for delivery', () => {
      const { container } = render(<SupportPanel variant="delivery" value="Value" />);

      const iconContainer = container.querySelector('.w-24.h-24');
      expect(iconContainer).toHaveClass('bg-primary/10');
    });

    it('icon container has proper styling for availability', () => {
      const { container } = render(<SupportPanel variant="availability" value="Value" />);

      const iconContainer = container.querySelector('.w-24.h-24');
      expect(iconContainer).toHaveClass('bg-accent-success-bg');
    });
  });

  // Edge Case: Dismissible
  describe('Dismissible', () => {
    it('does not show close button when onDismiss is not provided', () => {
      render(<SupportPanel variant="delivery" value="Value" />);

      const closeButton = screen.queryByLabelText('Закрыть');
      expect(closeButton).not.toBeInTheDocument();
    });

    it('shows close button when onDismiss is provided', () => {
      const handleDismiss = vi.fn();
      render(<SupportPanel variant="delivery" value="Value" onDismiss={handleDismiss} />);

      const closeButton = screen.getByLabelText('Закрыть');
      expect(closeButton).toBeInTheDocument();
    });

    it('calls onDismiss when close button is clicked', () => {
      const handleDismiss = vi.fn();
      render(<SupportPanel variant="delivery" value="Value" onDismiss={handleDismiss} />);

      const closeButton = screen.getByLabelText('Закрыть');
      fireEvent.click(closeButton);

      expect(handleDismiss).toHaveBeenCalledTimes(1);
    });

    it('hides panel when close button is clicked', () => {
      const handleDismiss = vi.fn();
      render(<SupportPanel variant="delivery" value="Value" onDismiss={handleDismiss} />);

      const closeButton = screen.getByLabelText('Закрыть');
      fireEvent.click(closeButton);

      expect(screen.queryByText('Value')).not.toBeInTheDocument();
    });

    it('close button has hover effect', () => {
      const handleDismiss = vi.fn();
      render(<SupportPanel variant="delivery" value="Value" onDismiss={handleDismiss} />);

      const closeButton = screen.getByLabelText('Закрыть');
      expect(closeButton).toHaveClass('hover:bg-neutral-200');
    });

    it('close button has focus ring', () => {
      const handleDismiss = vi.fn();
      render(<SupportPanel variant="delivery" value="Value" onDismiss={handleDismiss} />);

      const closeButton = screen.getByLabelText('Закрыть');
      expect(closeButton).toHaveClass('focus:ring-2', 'focus:ring-primary');
    });
  });

  // Edge Case: Fade-out анимация
  describe('Fade-out Animation', () => {
    it('has transition duration of 200ms', () => {
      const { container } = render(<SupportPanel variant="delivery" value="Value" />);

      const panel = container.firstChild as HTMLElement;
      expect(panel).toHaveClass('transition-opacity', 'duration-[200ms]');
    });
  });

  // Styling
  describe('Styling', () => {
    it('has grid layout', () => {
      const { container } = render(<SupportPanel variant="delivery" value="Value" />);

      const panel = container.firstChild as HTMLElement;
      expect(panel).toHaveClass('grid', 'grid-cols-[auto_1fr]', 'gap-4');
    });

    it('has rounded corners', () => {
      const { container } = render(<SupportPanel variant="delivery" value="Value" />);

      const panel = container.firstChild as HTMLElement;
      expect(panel).toHaveClass('rounded-md');
    });

    it('has proper padding', () => {
      const { container } = render(<SupportPanel variant="delivery" value="Value" />);

      const panel = container.firstChild as HTMLElement;
      expect(panel).toHaveClass('p-5');
    });

    it('content has flex column layout', () => {
      const { container } = render(
        <SupportPanel variant="delivery" value="Value" description="Desc" />
      );

      const content = container.querySelector('.flex-col');
      expect(content).toHaveClass('gap-1');
    });
  });

  // Accessibility
  describe('Accessibility', () => {
    it('forwards ref correctly', () => {
      const ref = React.createRef<HTMLDivElement>();
      render(<SupportPanel ref={ref} variant="delivery" value="Value" />);

      expect(ref.current).toBeInstanceOf(HTMLDivElement);
    });

    it('close button has aria-label', () => {
      const handleDismiss = vi.fn();
      render(<SupportPanel variant="delivery" value="Value" onDismiss={handleDismiss} />);

      const closeButton = screen.getByLabelText('Закрыть');
      expect(closeButton).toHaveAttribute('aria-label', 'Закрыть');
    });

    it('icon has aria-hidden', () => {
      const { container } = render(<SupportPanel variant="delivery" value="Value" />);

      const icon = container.querySelector('svg');
      expect(icon).toHaveAttribute('aria-hidden', 'true');
    });
  });

  // Custom className
  it('accepts custom className', () => {
    const { container } = render(
      <SupportPanel variant="delivery" value="Value" className="custom-class" />
    );

    const panel = container.firstChild as HTMLElement;
    expect(panel).toHaveClass('custom-class');
  });

  // Custom props
  it('accepts custom HTML attributes', () => {
    render(<SupportPanel variant="delivery" value="Value" data-testid="custom-panel" />);

    expect(screen.getByTestId('custom-panel')).toBeInTheDocument();
  });

  // Edge Case: Длинный текст
  describe('Long Text', () => {
    it('handles long value text', () => {
      const longValue = 'This is a very long value text that might wrap to multiple lines';
      render(<SupportPanel variant="delivery" value={longValue} />);

      expect(screen.getByText(longValue)).toBeInTheDocument();
    });

    it('handles long description text', () => {
      const longDescription =
        'This is a very long description that should wrap properly without breaking the layout';
      render(<SupportPanel variant="delivery" value="Value" description={longDescription} />);

      expect(screen.getByText(longDescription)).toBeInTheDocument();
    });
  });
});
