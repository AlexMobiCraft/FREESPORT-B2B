/**
 * Checkbox Component Tests
 * Проверка indeterminate, disabled, prefers-reduced-motion, единственной подписи
 */

import React from 'react';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { Checkbox } from '../Checkbox';

describe('Checkbox', () => {
  it('renders checkbox with label', () => {
    render(<Checkbox label="Accept terms" />);
    expect(screen.getByLabelText('Accept terms')).toBeInTheDocument();
  });

  it('renders checkbox without label', () => {
    render(<Checkbox />);
    const checkbox = screen.getByRole('checkbox', { hidden: true });
    expect(checkbox).toBeInTheDocument();
  });

  // Edge Case: Indeterminate state
  describe('Edge Case: Indeterminate State', () => {
    it('sets indeterminate state', () => {
      const ref = React.createRef<HTMLInputElement>();
      render(<Checkbox ref={ref} indeterminate={true} label="Select All" />);

      expect(ref.current?.indeterminate).toBe(true);
    });

    it('displays minus icon for indeterminate', () => {
      render(<Checkbox indeterminate={true} label="Test" />);
      const checkbox = screen.getByRole('checkbox', { hidden: true });
      const label = checkbox.nextElementSibling as HTMLElement;
      expect(label).toHaveClass('bg-primary');
    });
  });

  // Disabled state
  describe('Disabled State', () => {
    it('applies disabled styles', () => {
      render(<Checkbox label="Disabled" disabled />);
      const checkbox = screen.getByRole('checkbox', { hidden: true });
      expect(checkbox).toBeDisabled();

      const label = checkbox.nextElementSibling as HTMLElement;
      expect(label).toHaveClass('opacity-50');
      expect(label).toHaveClass('cursor-not-allowed');
    });
  });

  // Edge Case: prefers-reduced-motion
  it('has motion-reduce class for animations', () => {
    render(<Checkbox label="Test" checked />);
    const checkbox = screen.getByRole('checkbox', { hidden: true });
    const label = checkbox.nextElementSibling as HTMLElement;
    expect(label).toHaveClass('motion-reduce:transition-none');
  });

  it('keeps checked scale animation on label', () => {
    render(<Checkbox label="Test" />);
    const checkbox = screen.getByRole('checkbox', { hidden: true });
    const label = checkbox.nextElementSibling as HTMLElement;
    expect(label).toHaveClass('peer-checked:scale-100');
  });

  // Accessibility
  describe('Accessibility', () => {
    it('has focus ring styles', () => {
      render(<Checkbox label="Test" />);
      const checkbox = screen.getByRole('checkbox', { hidden: true });
      const label = checkbox.nextElementSibling as HTMLElement;
      expect(label).toHaveClass('peer-focus:ring-2');
      expect(label).toHaveClass('peer-focus:ring-primary/12');
    });
  });

  // Одна подпись: декоративный квадрат — не <label>, иначе у input две подписи и
  // первая пустая (её и видит простой анализатор HTML через input.labels[0]).
  describe('Single label', () => {
    it('links exactly one label — the text — when label prop is set', () => {
      render(<Checkbox label="Test" />);
      const checkbox = screen.getByRole('checkbox') as HTMLInputElement;
      expect(checkbox.labels).toHaveLength(1);
      expect(checkbox.labels?.[0]).toHaveTextContent('Test');
    });

    it('links no labels without label prop', () => {
      render(<Checkbox />);
      const checkbox = screen.getByRole('checkbox') as HTMLInputElement;
      expect(checkbox.labels).toHaveLength(0);
    });

    it('renders the box as aria-hidden span, not label', () => {
      render(<Checkbox label="Test" />);
      const box = screen.getByRole('checkbox').nextElementSibling as HTMLElement;
      expect(box.tagName).toBe('SPAN');
      expect(box).toHaveAttribute('aria-hidden', 'true');
    });

    it('lays the native input transparently over the box instead of sr-only', () => {
      render(<Checkbox label="Test" />);
      const checkbox = screen.getByRole('checkbox');
      expect(checkbox).not.toHaveClass('sr-only');
      expect(checkbox).toHaveClass('opacity-0', 'absolute', 'inset-0');
    });

    it('toggles when the label text is clicked', async () => {
      const user = userEvent.setup();
      render(<Checkbox label="Test" />);
      const checkbox = screen.getByRole('checkbox');

      await user.click(screen.getByText('Test'));
      expect(checkbox).toBeChecked();
      await user.click(screen.getByText('Test'));
      expect(checkbox).not.toBeChecked();
    });
  });
});
