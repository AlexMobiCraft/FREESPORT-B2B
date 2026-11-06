/**
 * FeatureCard Unit Tests
 * Story 19.1 - AC 6 (покрытие ≥ 80%)
 */

import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { Factory } from 'lucide-react';
import { FeatureCard } from './FeatureCard';

describe('FeatureCard', () => {
  const mockProps = {
    icon: Factory,
    title: 'Собственное производство',
    description: 'Контроль качества на всех этапах',
  };

  it('renders title and description', () => {
    render(<FeatureCard {...mockProps} />);

    expect(screen.getByText('Собственное производство')).toBeInTheDocument();
    expect(screen.getByText('Контроль качества на всех этапах')).toBeInTheDocument();
  });

  it('renders without description', () => {
    const { icon, title } = mockProps;
    render(<FeatureCard icon={icon} title={title} />);

    expect(screen.getByText(title)).toBeInTheDocument();
    expect(screen.queryByText('Контроль качества на всех этапах')).not.toBeInTheDocument();
  });

  it('displays icon correctly', () => {
    const { container } = render(<FeatureCard {...mockProps} />);
    const iconWrapper = container.querySelector('[aria-hidden="true"]');

    expect(iconWrapper).toBeInTheDocument();
    expect(iconWrapper?.querySelector('svg')).toBeInTheDocument();
  });

  it('applies default variant by default', () => {
    const { container } = render(<FeatureCard {...mockProps} />);
    const card = container.firstChild as HTMLElement;

    expect(card.className).toContain('default');
  });

  it('applies horizontal variant styles', () => {
    const { container } = render(<FeatureCard {...mockProps} variant="horizontal" />);
    const card = container.firstChild as HTMLElement;

    expect(card.className).toContain('horizontal');
  });

  it('applies compact variant styles', () => {
    const { container } = render(<FeatureCard {...mockProps} variant="compact" />);
    const card = container.firstChild as HTMLElement;

    expect(card.className).toContain('compact');
  });

  it('applies custom className', () => {
    const { container } = render(<FeatureCard {...mockProps} className="custom-class" />);
    const card = container.firstChild as HTMLElement;

    expect(card.className).toContain('custom-class');
  });

  it('has correct ARIA role', () => {
    render(<FeatureCard {...mockProps} />);
    const card = screen.getByRole('article');

    expect(card).toBeInTheDocument();
    expect(card).toHaveAttribute('aria-label', 'Собственное производство');
  });

  it('icon wrapper is hidden from screen readers', () => {
    const { container } = render(<FeatureCard {...mockProps} />);
    const iconWrapper = container.querySelector('[aria-hidden="true"]');

    expect(iconWrapper).toHaveAttribute('aria-hidden', 'true');
  });
});
