/**
 * Tag Component Tests
 * Покрытие всех вариантов и text overflow
 */

import React from 'react';
import { render, screen } from '@testing-library/react';
import { Tag, TagVariant } from '../Tag';

describe('Tag', () => {
  // Базовый рендеринг
  it('renders tag with text', () => {
    render(<Tag>Default Tag</Tag>);

    expect(screen.getByText('Default Tag')).toBeInTheDocument();
  });

  it('uses default variant when not specified', () => {
    render(<Tag>Default</Tag>);

    const tag = screen.getByText('Default');
    expect(tag).toHaveClass('bg-neutral-200', 'text-text-secondary');
  });

  // Все варианты
  describe('Variants', () => {
    const variants: { variant: TagVariant; text: string; bgClass: string; textClass: string }[] = [
      {
        variant: 'default',
        text: 'Default',
        bgClass: 'bg-neutral-200',
        textClass: 'text-text-secondary',
      },
      {
        variant: 'highlight',
        text: 'Highlight',
        bgClass: 'bg-primary-subtle',
        textClass: 'text-primary',
      },
      {
        variant: 'success',
        text: 'Success',
        bgClass: 'bg-accent-success-bg',
        textClass: 'text-accent-success',
      },
      {
        variant: 'warning',
        text: 'Warning',
        bgClass: 'bg-accent-warning-bg',
        textClass: 'text-accent-warning',
      },
      {
        variant: 'danger',
        text: 'Danger',
        bgClass: 'bg-accent-danger-bg',
        textClass: 'text-accent-danger',
      },
    ];

    variants.forEach(({ variant, text, bgClass, textClass }) => {
      it(`renders ${variant} variant correctly`, () => {
        render(<Tag variant={variant}>{text}</Tag>);

        const tag = screen.getByText(text);
        expect(tag).toBeInTheDocument();
        expect(tag).toHaveClass(bgClass, textClass);
      });
    });
  });

  // Edge Case: Text overflow
  describe('Text Overflow', () => {
    it('truncates long text with ellipsis', () => {
      const longText = 'This is a very long tag text that should be truncated with ellipsis';
      render(<Tag>{longText}</Tag>);

      const tag = screen.getByText(longText);
      expect(tag).toHaveClass('truncate', 'max-w-[200px]');
    });

    it('has max width of 200px', () => {
      render(<Tag>Text</Tag>);

      const tag = screen.getByText('Text');
      expect(tag).toHaveClass('max-w-[200px]');
    });

    it('enforces single-line with whitespace-nowrap', () => {
      render(<Tag>Multi line text</Tag>);

      const tag = screen.getByText('Multi line text');
      expect(tag).toHaveClass('whitespace-nowrap');
    });
  });

  // Styling
  describe('Styling', () => {
    it('has inline-flex layout', () => {
      render(<Tag>Tag</Tag>);

      const tag = screen.getByText('Tag');
      expect(tag).toHaveClass('inline-flex', 'items-center');
    });

    it('has rounded-xl shape', () => {
      render(<Tag>Tag</Tag>);

      const tag = screen.getByText('Tag');
      expect(tag).toHaveClass('rounded-xl');
    });

    it('has proper font weight', () => {
      render(<Tag variant="default">Tag</Tag>);

      const tag = screen.getByText('Tag');
      expect(tag).toHaveClass('font-medium');
    });

    it('has proper padding', () => {
      render(<Tag>Tag</Tag>);

      const tag = screen.getByText('Tag');
      expect(tag).toHaveClass('px-2', 'py-1');
    });
  });

  // Accessibility
  describe('Accessibility', () => {
    it('forwards ref correctly', () => {
      const ref = React.createRef<HTMLSpanElement>();
      render(<Tag ref={ref}>Tag</Tag>);

      expect(ref.current).toBeInstanceOf(HTMLSpanElement);
    });

    it('renders as span element', () => {
      const { container } = render(<Tag>Tag</Tag>);

      const tag = container.querySelector('span');
      expect(tag).toBeInTheDocument();
    });
  });

  // Custom className
  it('accepts custom className', () => {
    render(<Tag className="custom-class">Tag</Tag>);

    const tag = screen.getByText('Tag');
    expect(tag).toHaveClass('custom-class');
  });

  // Custom props
  it('accepts custom HTML attributes', () => {
    render(<Tag data-testid="custom-tag">Tag</Tag>);

    expect(screen.getByTestId('custom-tag')).toBeInTheDocument();
  });

  // Variant combinations
  describe('Variant Combinations', () => {
    it('combines highlight variant with custom className', () => {
      render(
        <Tag variant="highlight" className="extra-class">
          Highlight
        </Tag>
      );

      const tag = screen.getByText('Highlight');
      expect(tag).toHaveClass('bg-primary-subtle', 'text-primary', 'extra-class');
    });

    it('combines success variant with truncate', () => {
      render(<Tag variant="success">Success Tag</Tag>);

      const tag = screen.getByText('Success Tag');
      expect(tag).toHaveClass('bg-accent-success-bg', 'text-accent-success', 'truncate');
    });
  });
});
