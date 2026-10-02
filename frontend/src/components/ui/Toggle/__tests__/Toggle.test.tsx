/**
 * Toggle (Switch) Component Tests
 * Покрытие disabled состояния, prefers-reduced-motion и accessibility
 */

import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { Toggle } from '../Toggle';

describe('Toggle', () => {
  // Трек идёт сразу после input, бегунок — его единственный потомок
  const getTrack = () => screen.getByRole('switch').nextElementSibling as HTMLElement;
  const getThumb = () => getTrack().firstElementChild as HTMLElement;

  // Базовый рендеринг
  it('renders toggle switch', () => {
    render(<Toggle />);

    const toggle = screen.getByRole('switch');
    expect(toggle).toBeInTheDocument();
  });

  it('renders with label', () => {
    render(<Toggle label="Enable notifications" />);

    expect(screen.getByText('Enable notifications')).toBeInTheDocument();
    expect(screen.getByRole('switch')).toHaveAttribute('aria-label', 'Enable notifications');
  });

  // Checked state
  describe('Checked State', () => {
    it('is unchecked by default', () => {
      render(<Toggle />);

      const toggle = screen.getByRole('switch');
      expect(toggle).not.toBeChecked();
      expect(toggle).toHaveAttribute('aria-checked', 'false');
    });

    it('is checked when checked prop is true', () => {
      render(<Toggle checked />);

      const toggle = screen.getByRole('switch');
      expect(toggle).toBeChecked();
      expect(toggle).toHaveAttribute('aria-checked', 'true');
    });

    it('toggles checked state on click', () => {
      const handleChange = vi.fn();
      render(<Toggle onChange={handleChange} />);

      const toggle = screen.getByRole('switch');
      fireEvent.click(toggle);

      expect(handleChange).toHaveBeenCalledTimes(1);
    });
  });

  // Disabled state
  describe('Disabled State', () => {
    it('is disabled when disabled prop is true', () => {
      render(<Toggle disabled />);

      const toggle = screen.getByRole('switch');
      expect(toggle).toBeDisabled();
    });

    it('applies disabled styles', () => {
      render(<Toggle label="Test" disabled />);

      const track = getTrack();
      expect(track).toHaveClass('opacity-50', 'cursor-not-allowed');
    });

    it('does not toggle when disabled', () => {
      const handleChange = vi.fn();
      render(<Toggle disabled onChange={handleChange} />);

      const toggle = screen.getByRole('switch');
      fireEvent.click(toggle);

      expect(handleChange).not.toHaveBeenCalled();
    });

    it('applies disabled cursor to label text', () => {
      render(<Toggle label="Test" disabled />);

      const labelText = screen.getByText('Test');
      expect(labelText).toHaveClass('cursor-not-allowed', 'opacity-50');
    });
  });

  // Edge Case: prefers-reduced-motion
  it('has motion-reduce classes for accessibility', () => {
    render(<Toggle />);

    const track = getTrack();
    const thumb = getThumb();

    expect(track).toHaveClass('motion-reduce:transition-none');
    expect(thumb).toHaveClass('motion-reduce:transition-none');
  });

  // Transition animations
  it('has transition duration of 180ms (Design System v2.0)', () => {
    render(<Toggle />);

    const track = getTrack();
    const thumb = getThumb();

    expect(track).toHaveClass('duration-[180ms]');
    expect(thumb).toHaveClass('duration-[180ms]');
  });

  // Thumb movement
  it('moves thumb when checked', () => {
    render(<Toggle checked />);

    const thumb = getThumb();
    expect(thumb).toHaveClass('translate-x-5');
  });

  // Accessibility
  describe('Accessibility', () => {
    it('has role="switch"', () => {
      render(<Toggle />);

      const toggle = screen.getByRole('switch');
      expect(toggle).toHaveAttribute('role', 'switch');
    });

    it('has aria-checked attribute', () => {
      const { rerender } = render(<Toggle checked={false} />);

      let toggle = screen.getByRole('switch');
      expect(toggle).toHaveAttribute('aria-checked', 'false');

      rerender(<Toggle checked={true} />);
      toggle = screen.getByRole('switch');
      expect(toggle).toHaveAttribute('aria-checked', 'true');
    });

    it('has aria-label when label prop is provided', () => {
      render(<Toggle label="Test Toggle" />);

      const toggle = screen.getByRole('switch');
      expect(toggle).toHaveAttribute('aria-label', 'Test Toggle');
    });

    it('has focus ring on focus', () => {
      render(<Toggle />);

      const track = getTrack();
      expect(track).toHaveClass('peer-focus:ring-2', 'peer-focus:ring-primary');
    });

    it('forwards ref correctly', () => {
      const ref = React.createRef<HTMLInputElement>();
      render(<Toggle ref={ref} />);

      expect(ref.current).toBeInstanceOf(HTMLInputElement);
    });

    it('associates label with toggle', () => {
      render(<Toggle label="Test Toggle" />);

      const toggle = screen.getByRole('switch');
      const labelText = screen.getByText('Test Toggle');
      expect(labelText).toHaveAttribute('for', toggle.id);
    });
  });

  // Visual states
  describe('Visual States', () => {
    it('has unchecked background color', () => {
      render(<Toggle checked={false} />);

      const track = getTrack();
      expect(track).toHaveClass('bg-neutral-300');
    });

    it('has checked background color', () => {
      render(<Toggle checked />);

      const track = getTrack();
      expect(track).toHaveClass('peer-checked:bg-primary');
    });

    it('thumb has shadow', () => {
      render(<Toggle />);

      const thumb = getThumb();
      expect(thumb).toHaveClass('shadow-[0_2px_8px_rgba(0,0,0,0.16)]');
    });
  });

  // Custom className
  it('accepts custom className', () => {
    render(<Toggle className="custom-class" />);

    const track = getTrack();
    expect(track).toHaveClass('custom-class');
  });

  // Custom ID
  it('generates ID from label', () => {
    render(<Toggle label="Enable Feature" />);

    const toggle = screen.getByRole('switch');
    expect(toggle.id).toBe('toggle-enable-feature');
  });

  it('uses custom ID when provided', () => {
    render(<Toggle id="custom-toggle" />);

    const toggle = screen.getByRole('switch');
    expect(toggle.id).toBe('custom-toggle');
  });

  // Одна подпись: трек — не <label>, иначе у input две подписи и первая пустая
  // (её и видит простой анализатор HTML через input.labels[0]).
  describe('Single label', () => {
    it('links exactly one label — the text — when label prop is set', () => {
      render(<Toggle label="Test" />);
      const toggle = screen.getByRole('switch') as HTMLInputElement;
      expect(toggle.labels).toHaveLength(1);
      expect(toggle.labels?.[0]).toHaveTextContent('Test');
    });

    it('links no labels without label prop', () => {
      render(<Toggle />);
      const toggle = screen.getByRole('switch') as HTMLInputElement;
      expect(toggle.labels).toHaveLength(0);
    });

    it('renders the track as aria-hidden span, not label', () => {
      render(<Toggle label="Test" />);
      const track = getTrack();
      expect(track.tagName).toBe('SPAN');
      expect(track).toHaveAttribute('aria-hidden', 'true');
    });

    it('lays the native input transparently over the track instead of sr-only', () => {
      render(<Toggle label="Test" />);
      const toggle = screen.getByRole('switch');
      expect(toggle).not.toHaveClass('sr-only');
      expect(toggle).toHaveClass('opacity-0', 'absolute', 'inset-0', 'z-10');
      // Без isolate z-10 вышел бы в общий порядок наложения страницы
      expect(toggle.parentElement).toHaveClass('isolate');
    });

    it('calls onChange once when the label text is clicked', async () => {
      const user = userEvent.setup();
      const handleChange = vi.fn();
      render(<Toggle label="Test" onChange={handleChange} />);

      await user.click(screen.getByText('Test'));
      expect(handleChange).toHaveBeenCalledTimes(1);
      expect(handleChange.mock.calls[0][0].target.checked).toBe(true);
    });
  });
});
