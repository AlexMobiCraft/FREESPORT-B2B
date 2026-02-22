/**
 * Badge Component Tests
 * Покрытие всех вариантов, иконок и text overflow
 */

import React from 'react';
import { render, screen } from '@testing-library/react';
import { Badge, BadgeVariant } from '../Badge';

describe('Badge', () => {
  // Базовый рендеринг
  it('renders badge with text', () => {
    render(<Badge variant="delivered">Delivered</Badge>);

    expect(screen.getByText('Delivered')).toBeInTheDocument();
  });

  // Все варианты
  describe('Variants', () => {
    const variants: { variant: BadgeVariant; text: string; hasIcon: boolean }[] = [
      { variant: 'delivered', text: 'Delivered', hasIcon: true },
      { variant: 'transit', text: 'In Transit', hasIcon: true },
      { variant: 'cancelled', text: 'Cancelled', hasIcon: true },
      { variant: 'promo', text: 'Promo', hasIcon: false },
      { variant: 'sale', text: 'Sale', hasIcon: false },
      { variant: 'discount', text: 'Discount', hasIcon: false },
      { variant: 'premium', text: 'Premium', hasIcon: true },
      { variant: 'new', text: 'New', hasIcon: false },
      { variant: 'hit', text: 'Hit', hasIcon: false },
    ];

    variants.forEach(({ variant, text, hasIcon }) => {
      it(`renders ${variant} variant correctly`, () => {
        const { container } = render(<Badge variant={variant}>{text}</Badge>);

        expect(screen.getByText(text)).toBeInTheDocument();

        if (hasIcon) {
          const icon = container.querySelector('svg');
          expect(icon).toBeInTheDocument();
          expect(icon).toHaveAttribute('aria-hidden', 'true');
        }
      });
    });

    it('applies delivered variant styles', () => {
      render(<Badge variant="delivered">Delivered</Badge>);

      const badge = screen.getByText('Delivered');
      expect(badge).toHaveClass('bg-[#E0F5E0]', 'text-[#1F7A1F]');
    });

    it('applies transit variant styles', () => {
      render(<Badge variant="transit">In Transit</Badge>);

      const badge = screen.getByText('In Transit');
      expect(badge).toHaveClass('bg-[#FFF1CC]', 'text-[#8C5A00]');
    });

    it('applies cancelled variant styles', () => {
      render(<Badge variant="cancelled">Cancelled</Badge>);

      const badge = screen.getByText('Cancelled');
      expect(badge).toHaveClass('bg-[#FFE1E1]', 'text-[#A62828]');
    });

    it('applies promo variant styles', () => {
      render(<Badge variant="promo">Promo</Badge>);

      const badge = screen.getByText('Promo');
      expect(badge).toHaveClass('bg-[#FFF0F5]', 'text-accent-promo');
    });

    it('applies premium variant styles', () => {
      render(<Badge variant="premium">Premium</Badge>);

      const badge = screen.getByText('Premium');
      expect(badge).toHaveClass('bg-[#F6F0E4]', 'text-[#6D4C1F]');
    });
  });

  // Icons
  describe('Icons', () => {
    it('renders icon for delivered variant', () => {
      const { container } = render(<Badge variant="delivered">Delivered</Badge>);

      const icon = container.querySelector('svg');
      expect(icon).toBeInTheDocument();
      expect(icon).toHaveClass('w-3', 'h-3');
    });

    it('renders icon for transit variant', () => {
      const { container } = render(<Badge variant="transit">In Transit</Badge>);

      const icon = container.querySelector('svg');
      expect(icon).toBeInTheDocument();
    });

    it('renders icon for premium variant', () => {
      const { container } = render(<Badge variant="premium">Premium</Badge>);

      const icon = container.querySelector('svg');
      expect(icon).toBeInTheDocument();
    });

    it('does not render icon for promo variant', () => {
      const { container } = render(<Badge variant="promo">Promo</Badge>);

      const icon = container.querySelector('svg');
      expect(icon).not.toBeInTheDocument();
    });

    it('icon has aria-hidden attribute', () => {
      const { container } = render(<Badge variant="delivered">Delivered</Badge>);

      const icon = container.querySelector('svg');
      expect(icon).toHaveAttribute('aria-hidden', 'true');
    });
  });

  // Edge Case: Text overflow
  describe('Text Overflow', () => {
    it('truncates long text with ellipsis', () => {
      const longText = 'This is a very long badge text that should be truncated';
      render(<Badge variant="delivered">{longText}</Badge>);

      const badge = screen.getByText(longText);
      expect(badge).toHaveClass('truncate', 'max-w-[200px]');
    });

    it('has max width of 200px', () => {
      render(<Badge variant="new">Text</Badge>);

      const badge = screen.getByText('Text');
      expect(badge).toHaveClass('max-w-[200px]');
    });
  });

  // Styling
  describe('Styling', () => {
    it('has inline-flex layout', () => {
      render(<Badge variant="hit">Hit</Badge>);

      const badge = screen.getByText('Hit');
      expect(badge).toHaveClass('inline-flex', 'items-center');
    });

    it('has rounded-full shape', () => {
      render(<Badge variant="sale">Sale</Badge>);

      const badge = screen.getByText('Sale');
      expect(badge).toHaveClass('rounded-full');
    });

    it('has proper font weight', () => {
      render(<Badge variant="discount">Discount</Badge>);

      const badge = screen.getByText('Discount');
      expect(badge).toHaveClass('font-medium');
    });

    it('has proper padding', () => {
      render(<Badge variant="new">New</Badge>);

      const badge = screen.getByText('New');
      expect(badge).toHaveClass('px-2');
      expect(badge).toHaveClass('py-0.5');
    });
  });

  // Accessibility
  describe('Accessibility', () => {
    it('forwards ref correctly', () => {
      const ref = React.createRef<HTMLSpanElement>();
      render(
        <Badge ref={ref} variant="delivered">
          Delivered
        </Badge>
      );

      expect(ref.current).toBeInstanceOf(HTMLSpanElement);
    });

    it('renders as span element', () => {
      const { container } = render(<Badge variant="hit">Hit</Badge>);

      const badge = container.querySelector('span');
      expect(badge).toBeInTheDocument();
    });
  });

  // Custom className
  it('accepts custom className', () => {
    render(
      <Badge variant="delivered" className="custom-class">
        Delivered
      </Badge>
    );

    const badge = screen.getByText('Delivered');
    expect(badge).toHaveClass('custom-class');
  });

  // Custom props
  it('accepts custom HTML attributes', () => {
    render(
      <Badge variant="delivered" data-testid="custom-badge">
        Delivered
      </Badge>
    );

    expect(screen.getByTestId('custom-badge')).toBeInTheDocument();
  });
});
