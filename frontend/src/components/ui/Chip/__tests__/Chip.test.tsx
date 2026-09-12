/**
 * Chip Component Tests
 * Покрытие selected состояния, onRemove callback, минимальной ширины
 */

import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import { Chip } from '../Chip';

describe('Chip', () => {
  // Базовый рендеринг
  it('renders chip with text', () => {
    render(<Chip>Filter</Chip>);

    expect(screen.getByText('Filter')).toBeInTheDocument();
  });

  // Selected state
  describe('Selected State', () => {
    it('is not selected by default', () => {
      render(<Chip>Filter</Chip>);

      const chip = screen.getByText('Filter').parentElement;
      expect(chip).toHaveClass('bg-white', 'border-neutral-300', 'text-text-secondary');
    });

    it('applies selected styles when selected prop is true', () => {
      render(<Chip selected>Selected</Chip>);

      const chip = screen.getByText('Selected').parentElement;
      expect(chip).toHaveClass('bg-primary', 'text-white');
      expect(chip).not.toHaveClass('border');
    });
  });

  // Icon
  describe('Icon', () => {
    it('renders icon when provided', () => {
      const TestIcon = () => <svg data-testid="test-icon" />;
      render(<Chip icon={<TestIcon />}>With Icon</Chip>);

      expect(screen.getByTestId('test-icon')).toBeInTheDocument();
    });

    it('does not render icon when not provided', () => {
      const { container } = render(<Chip>No Icon</Chip>);

      const iconContainer = container.querySelector('span.w-4');
      expect(iconContainer).not.toBeInTheDocument();
    });

    it('icon has fixed size', () => {
      const TestIcon = () => <svg data-testid="test-icon" />;
      const { container } = render(<Chip icon={<TestIcon />}>Icon</Chip>);

      const iconContainer = container.querySelector('span.w-4');
      expect(iconContainer).toHaveClass('w-4', 'h-4', 'flex-shrink-0');
    });
  });

  // Edge Case: onRemove callback
  describe('Remove Button', () => {
    it('renders remove button when onRemove is provided', () => {
      const handleRemove = vi.fn();
      render(<Chip onRemove={handleRemove}>Removable</Chip>);

      const removeButton = screen.getByLabelText('Удалить');
      expect(removeButton).toBeInTheDocument();
    });

    it('does not render remove button when onRemove is not provided', () => {
      render(<Chip>Not Removable</Chip>);

      const removeButton = screen.queryByLabelText('Удалить');
      expect(removeButton).not.toBeInTheDocument();
    });

    it('calls onRemove when remove button is clicked', () => {
      const handleRemove = vi.fn();
      render(<Chip onRemove={handleRemove}>Removable</Chip>);

      const removeButton = screen.getByLabelText('Удалить');
      fireEvent.click(removeButton);

      expect(handleRemove).toHaveBeenCalledTimes(1);
    });

    it('stops event propagation when remove button is clicked', () => {
      const handleRemove = vi.fn();
      const handleChipClick = vi.fn();

      render(
        <Chip onRemove={handleRemove} onClick={handleChipClick}>
          Removable
        </Chip>
      );

      const removeButton = screen.getByLabelText('Удалить');
      fireEvent.click(removeButton);

      expect(handleRemove).toHaveBeenCalledTimes(1);
      expect(handleChipClick).not.toHaveBeenCalled();
    });

    it('remove button has focus ring', () => {
      const handleRemove = vi.fn();
      render(<Chip onRemove={handleRemove}>Removable</Chip>);

      const removeButton = screen.getByLabelText('Удалить');
      expect(removeButton).toHaveClass('focus:ring-2', 'focus:ring-primary');
    });

    it('remove button has hover effect', () => {
      const handleRemove = vi.fn();
      render(<Chip onRemove={handleRemove}>Removable</Chip>);

      const removeButton = screen.getByLabelText('Удалить');
      expect(removeButton).toHaveClass('hover:bg-neutral-300/50');
    });
  });

  // Edge Case: Минимальная ширина
  describe('Minimum Width', () => {
    it('has minimum width of 60px for easy clicking', () => {
      render(<Chip>A</Chip>);

      const chip = screen.getByText('A').parentElement;
      expect(chip).toHaveClass('min-w-[60px]');
    });
  });

  // Edge Case: Text overflow
  describe('Text Overflow', () => {
    it('truncates long text with ellipsis', () => {
      const longText = 'This is a very long chip text that should be truncated';
      render(<Chip>{longText}</Chip>);

      const textSpan = screen.getByText(longText);
      expect(textSpan).toHaveClass('truncate');
    });

    it('has max width of 200px', () => {
      render(<Chip>Text</Chip>);

      const chip = screen.getByText('Text').parentElement;
      expect(chip).toHaveClass('max-w-[200px]');
    });
  });

  // Styling
  describe('Styling', () => {
    it('has inline-flex layout', () => {
      render(<Chip>Chip</Chip>);

      const chip = screen.getByText('Chip').parentElement;
      expect(chip).toHaveClass('inline-flex', 'items-center');
    });

    it('has rounded-2xl shape', () => {
      render(<Chip>Chip</Chip>);

      const chip = screen.getByText('Chip').parentElement;
      expect(chip).toHaveClass('rounded-2xl');
    });

    it('has proper font weight', () => {
      render(<Chip>Chip</Chip>);

      const chip = screen.getByText('Chip').parentElement;
      expect(chip).toHaveClass('font-medium');
    });

    it('has transition animation', () => {
      render(<Chip>Chip</Chip>);

      const chip = screen.getByText('Chip').parentElement;
      expect(chip).toHaveClass('transition-colors');
      expect(chip).toHaveClass('duration-[180ms]');
    });

    it('has proper padding', () => {
      render(<Chip>Chip</Chip>);

      const chip = screen.getByText('Chip').parentElement;
      expect(chip).toHaveClass('px-3', 'py-1');
    });
  });

  // Accessibility
  describe('Accessibility', () => {
    it('forwards ref correctly', () => {
      const ref = React.createRef<HTMLDivElement>();
      render(<Chip ref={ref}>Chip</Chip>);

      expect(ref.current).toBeInstanceOf(HTMLDivElement);
    });

    it('renders as div element', () => {
      const { container } = render(<Chip>Chip</Chip>);

      const chip = container.querySelector('div');
      expect(chip).toBeInTheDocument();
    });

    it('remove button has aria-label', () => {
      const handleRemove = vi.fn();
      render(<Chip onRemove={handleRemove}>Chip</Chip>);

      const removeButton = screen.getByLabelText('Удалить');
      expect(removeButton).toHaveAttribute('aria-label', 'Удалить');
    });
  });

  // Custom className
  it('accepts custom className', () => {
    render(<Chip className="custom-class">Chip</Chip>);

    const chip = screen.getByText('Chip').parentElement;
    expect(chip).toHaveClass('custom-class');
  });

  // Custom props
  it('accepts custom HTML attributes', () => {
    render(<Chip data-testid="custom-chip">Chip</Chip>);

    expect(screen.getByTestId('custom-chip')).toBeInTheDocument();
  });

  // Combined features
  describe('Combined Features', () => {
    it('renders selected chip with icon and remove button', () => {
      const TestIcon = () => <svg data-testid="test-icon" />;
      const handleRemove = vi.fn();

      render(
        <Chip selected icon={<TestIcon />} onRemove={handleRemove}>
          Complete
        </Chip>
      );

      expect(screen.getByText('Complete')).toBeInTheDocument();
      expect(screen.getByTestId('test-icon')).toBeInTheDocument();
      expect(screen.getByLabelText('Удалить')).toBeInTheDocument();

      const chip = screen.getByText('Complete').parentElement;
      expect(chip).toHaveClass('bg-primary', 'text-white');
    });
  });
});
