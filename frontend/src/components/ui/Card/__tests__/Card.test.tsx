/**
 * Card Component Tests
 * Покрытие hover эффектов и базовых стилей
 */

import React from 'react';
import { render, screen } from '@testing-library/react';
import { Card } from '../Card';

describe('Card', () => {
  // Базовый рендеринг
  it('renders card with children', () => {
    render(
      <Card>
        <h2>Card Title</h2>
        <p>Card content</p>
      </Card>
    );

    expect(screen.getByText('Card Title')).toBeInTheDocument();
    expect(screen.getByText('Card content')).toBeInTheDocument();
  });

  // Базовые стили
  describe('Base Styling', () => {
    it('has base styles applied', () => {
      const { container } = render(<Card>Content</Card>);

      const card = container.firstChild as HTMLElement;
      expect(card).toHaveClass('bg-neutral-100', 'rounded-md', 'p-6');
    });

    it('has default shadow', () => {
      const { container } = render(<Card>Content</Card>);

      const card = container.firstChild as HTMLElement;
      expect(card).toHaveClass('shadow-default');
    });

    it('has transition animation', () => {
      const { container } = render(<Card>Content</Card>);

      const card = container.firstChild as HTMLElement;
      expect(card).toHaveClass('transition-all', 'duration-medium');
    });
  });

  // Hover эффект
  describe('Hover Effect', () => {
    it('does not have hover effect by default', () => {
      const { container } = render(<Card>Content</Card>);

      const card = container.firstChild as HTMLElement;
      expect(card).not.toHaveClass('hover:shadow-hover');
      expect(card).not.toHaveClass('cursor-pointer');
    });

    it('applies hover effect when hover prop is true', () => {
      const { container } = render(<Card hover>Content</Card>);

      const card = container.firstChild as HTMLElement;
      expect(card).toHaveClass('hover:shadow-hover', 'hover:-translate-y-0.5', 'cursor-pointer');
    });
  });

  // Accessibility
  describe('Accessibility', () => {
    it('forwards ref correctly', () => {
      const ref = React.createRef<HTMLDivElement>();
      render(<Card ref={ref}>Content</Card>);

      expect(ref.current).toBeInstanceOf(HTMLDivElement);
    });

    it('renders as div element', () => {
      const { container } = render(<Card>Content</Card>);

      expect(container.firstChild?.nodeName).toBe('DIV');
    });
  });

  // Custom className
  it('accepts custom className', () => {
    const { container } = render(<Card className="custom-class">Content</Card>);

    const card = container.firstChild as HTMLElement;
    expect(card).toHaveClass('custom-class');
  });

  // Custom props
  it('accepts custom HTML attributes', () => {
    render(<Card data-testid="custom-card">Content</Card>);

    expect(screen.getByTestId('custom-card')).toBeInTheDocument();
  });

  // onClick handler
  it('can be clickable with onClick handler', () => {
    const handleClick = vi.fn();
    const { container } = render(
      <Card hover onClick={handleClick}>
        Clickable Card
      </Card>
    );

    const card = container.firstChild as HTMLElement;
    card.click();

    expect(handleClick).toHaveBeenCalledTimes(1);
  });

  // Complex content
  it('renders complex nested content', () => {
    render(
      <Card>
        <div>
          <h3>Title</h3>
          <p>Description</p>
          <button>Action</button>
        </div>
      </Card>
    );

    expect(screen.getByText('Title')).toBeInTheDocument();
    expect(screen.getByText('Description')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Action' })).toBeInTheDocument();
  });
});
