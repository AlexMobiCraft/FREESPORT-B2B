/**
 * Checkbox Component Tests
 * Проверка indeterminate, disabled, prefers-reduced-motion
 */

import React from 'react';
import { render, screen } from '@testing-library/react';
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
});
