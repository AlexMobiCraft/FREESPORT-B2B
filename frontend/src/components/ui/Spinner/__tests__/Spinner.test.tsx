/**
 * Spinner Component Tests
 * Покрытие размеров, ARIA атрибутов, prefers-reduced-motion
 */

import React from 'react';
import { render, screen } from '@testing-library/react';
import { Spinner, SpinnerSize } from '../Spinner';

describe('Spinner', () => {
  // Базовый рендеринг
  it('renders spinner', () => {
    render(<Spinner />);

    const spinner = screen.getByRole('status');
    expect(spinner).toBeInTheDocument();
  });

  // Размеры
  describe('Sizes', () => {
    const sizes: { size: SpinnerSize; className: string }[] = [
      { size: 'small', className: 'w-4 h-4' },
      { size: 'medium', className: 'w-6 h-6' },
      { size: 'large', className: 'w-8 h-8' },
    ];

    sizes.forEach(({ size, className }) => {
      it(`renders ${size} size correctly`, () => {
        const { container } = render(<Spinner size={size} />);

        const icon = container.querySelector('svg');
        expect(icon).toHaveClass(className.split(' ')[0], className.split(' ')[1]);
      });
    });

    it('uses medium size by default', () => {
      const { container } = render(<Spinner />);

      const icon = container.querySelector('svg');
      expect(icon).toHaveClass('w-6', 'h-6');
    });
  });

  // Accessibility
  describe('Accessibility', () => {
    it('has role="status"', () => {
      render(<Spinner />);

      const spinner = screen.getByRole('status');
      expect(spinner).toHaveAttribute('role', 'status');
    });

    it('has aria-live="polite"', () => {
      render(<Spinner />);

      const spinner = screen.getByRole('status');
      expect(spinner).toHaveAttribute('aria-live', 'polite');
    });

    it('has default aria-label "Loading"', () => {
      render(<Spinner />);

      const spinner = screen.getByRole('status');
      expect(spinner).toHaveAttribute('aria-label', 'Loading');
    });

    it('accepts custom aria-label', () => {
      render(<Spinner label="Processing..." />);

      const spinner = screen.getByRole('status');
      expect(spinner).toHaveAttribute('aria-label', 'Processing...');
    });

    it('has screen reader only text', () => {
      render(<Spinner label="Loading data" />);

      const srText = screen.getByText('Loading data');
      expect(srText).toHaveClass('sr-only');
    });

    it('icon has aria-hidden', () => {
      const { container } = render(<Spinner />);

      const icon = container.querySelector('svg');
      expect(icon).toHaveAttribute('aria-hidden', 'true');
    });
  });

  // Animation
  describe('Animation', () => {
    it('has spin animation', () => {
      const { container } = render(<Spinner />);

      const icon = container.querySelector('svg');
      expect(icon).toHaveClass('animate-spin');
    });

    // Edge Case: prefers-reduced-motion
    it('has motion-reduce class for accessibility', () => {
      const { container } = render(<Spinner />);

      const icon = container.querySelector('svg');
      expect(icon).toHaveClass('motion-reduce:animate-none');
    });
  });

  // Styling
  describe('Styling', () => {
    it('has primary color', () => {
      const { container } = render(<Spinner />);

      const icon = container.querySelector('svg');
      expect(icon).toHaveClass('text-primary');
    });

    it('has flex centering', () => {
      render(<Spinner />);

      const spinner = screen.getByRole('status');
      expect(spinner).toHaveClass('flex', 'items-center', 'justify-center');
    });
  });

  // Ref forwarding
  describe('Ref Forwarding', () => {
    it('forwards ref correctly', () => {
      const ref = React.createRef<HTMLDivElement>();
      render(<Spinner ref={ref} />);

      expect(ref.current).toBeInstanceOf(HTMLDivElement);
    });
  });

  // Custom className
  it('accepts custom className', () => {
    render(<Spinner className="custom-class" />);

    const spinner = screen.getByRole('status');
    expect(spinner).toHaveClass('custom-class');
  });

  // Custom props
  it('accepts custom HTML attributes', () => {
    render(<Spinner data-testid="custom-spinner" />);

    expect(screen.getByTestId('custom-spinner')).toBeInTheDocument();
  });

  // Combined features
  describe('Combined Features', () => {
    it('renders large spinner with custom label', () => {
      render(<Spinner size="large" label="Uploading files..." />);

      const spinner = screen.getByRole('status');
      expect(spinner).toHaveAttribute('aria-label', 'Uploading files...');

      const { container } = render(<Spinner size="large" />);
      const icon = container.querySelector('svg');
      expect(icon).toHaveClass('w-8', 'h-8');
    });

    it('renders small spinner with custom className', () => {
      const { container } = render(<Spinner size="small" className="my-custom-class" />);

      const spinner = screen.getByRole('status');
      expect(spinner).toHaveClass('my-custom-class');

      const icon = container.querySelector('svg');
      expect(icon).toHaveClass('w-4', 'h-4');
    });
  });
});
