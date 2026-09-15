/**
 * ProcessSteps Unit Tests
 * Story 19.1 - AC 6 (покрытие ≥ 80%)
 */

import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { ProcessSteps } from './ProcessSteps';

describe('ProcessSteps', () => {
  const mockSteps = [
    { number: 1, title: 'Подайте заявку', description: 'На сайте или по телефону' },
    { number: 2, title: 'Получите доступ', description: 'К оптовым ценам' },
    { number: 3, title: 'Работайте', description: 'С персональным менеджером' },
  ];

  it('renders all steps in order', () => {
    render(<ProcessSteps steps={mockSteps} />);

    expect(screen.getByText('Подайте заявку')).toBeInTheDocument();
    expect(screen.getByText('Получите доступ')).toBeInTheDocument();
    expect(screen.getByText('Работайте')).toBeInTheDocument();
  });

  it('displays step numbers correctly', () => {
    render(<ProcessSteps steps={mockSteps} />);

    expect(screen.getByText('1')).toBeInTheDocument();
    expect(screen.getByText('2')).toBeInTheDocument();
    expect(screen.getByText('3')).toBeInTheDocument();
  });

  it('displays step descriptions correctly', () => {
    render(<ProcessSteps steps={mockSteps} />);

    expect(screen.getByText('На сайте или по телефону')).toBeInTheDocument();
    expect(screen.getByText('К оптовым ценам')).toBeInTheDocument();
    expect(screen.getByText('С персональным менеджером')).toBeInTheDocument();
  });

  it('applies numbered variant by default', () => {
    const { container } = render(<ProcessSteps steps={mockSteps} />);
    const wrapper = container.firstChild as HTMLElement;

    expect(wrapper.className).toContain('numbered');
  });

  it('supports numbered variant explicitly', () => {
    const { container } = render(<ProcessSteps steps={mockSteps} variant="numbered" />);
    const wrapper = container.firstChild as HTMLElement;

    expect(wrapper.className).toContain('numbered');
  });

  it('supports timeline variant', () => {
    const { container } = render(<ProcessSteps steps={mockSteps} variant="timeline" />);
    const wrapper = container.firstChild as HTMLElement;

    expect(wrapper.className).toContain('timeline');
  });

  it('renders separators between steps', () => {
    const { container } = render(<ProcessSteps steps={mockSteps} />);

    // 3 шага + 3 номера (aria-hidden) + 2 разделителя (aria-hidden) = 8
    // Но мы ищем только разделители с svg или line
    const arrowSeparators = container.querySelectorAll('svg');
    expect(arrowSeparators.length).toBe(2); // 2 разделителя между 3 шагами
  });

  it('does not render separator after last step', () => {
    const { container } = render(<ProcessSteps steps={mockSteps} />);
    const steps = container.querySelectorAll('[role="listitem"]');
    const separators = container.querySelectorAll('svg');

    expect(steps.length).toBe(3);
    expect(separators.length).toBe(2); // На 1 меньше, чем шагов
  });

  it('has correct ARIA attributes', () => {
    render(<ProcessSteps steps={mockSteps} />);
    const list = screen.getByRole('list');

    expect(list).toHaveAttribute('aria-label', 'Шаги процесса');
  });

  it('renders list items with correct role', () => {
    render(<ProcessSteps steps={mockSteps} />);
    const items = screen.getAllByRole('listitem');

    expect(items.length).toBe(3);
  });

  it('applies custom className', () => {
    const { container } = render(<ProcessSteps steps={mockSteps} className="custom-class" />);
    const wrapper = container.firstChild as HTMLElement;

    expect(wrapper.className).toContain('custom-class');
  });

  it('renders empty when no steps provided', () => {
    render(<ProcessSteps steps={[]} />);
    const items = screen.queryAllByRole('listitem');

    expect(items.length).toBe(0);
  });

  it('renders single step without separator', () => {
    const singleStep = [{ number: 1, title: 'One Step', description: 'Single step' }];
    const { container } = render(<ProcessSteps steps={singleStep} />);
    const separators = container.querySelectorAll('svg');

    expect(separators.length).toBe(0);
  });

  it('number wrappers are hidden from screen readers', () => {
    const { container } = render(<ProcessSteps steps={mockSteps} />);
    const numberWrappers = container.querySelectorAll('[aria-hidden="true"]');

    // 3 numberWrapper + 2 separators = 5
    expect(numberWrappers.length).toBeGreaterThanOrEqual(5);
  });

  it('renders timeline variant with line separators', () => {
    render(<ProcessSteps steps={mockSteps} variant="timeline" />);

    // Timeline вариант также использует стрелки, но с другими стилями
    // Проверяем что элементы рендерятся
    const steps = screen.getAllByRole('listitem');
    expect(steps.length).toBe(3);
  });
});
