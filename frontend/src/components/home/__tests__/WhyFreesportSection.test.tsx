/**
 * WhyFreesportSection Component Tests
 * Story 19.2
 */

import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { WhyFreesportSection } from '../WhyFreesportSection';

describe('WhyFreesportSection', () => {
  it('renders section title correctly', () => {
    render(<WhyFreesportSection />);

    const title = screen.getByText('Почему партнёры выбирают FREESPORT?');
    expect(title).toBeInTheDocument();
    expect(title.tagName).toBe('H2');
  });

  it('renders 4 advantage cards', () => {
    render(<WhyFreesportSection />);

    // Проверяем наличие всех 4 карточек преимуществ
    expect(screen.getByText('Собственное производство')).toBeInTheDocument();
    expect(screen.getByText('Бесплатная доставка')).toBeInTheDocument();
    expect(screen.getByText('Персональный менеджер')).toBeInTheDocument();
    expect(screen.getByText('Минимальный заказ')).toBeInTheDocument();
  });

  it('renders advantage descriptions correctly', () => {
    render(<WhyFreesportSection />);

    expect(screen.getByText('Контроль качества')).toBeInTheDocument();
    expect(screen.getByText('До ТК от 35 000 ₽')).toBeInTheDocument();
    expect(screen.getByText('Сопровождение на всех этапах')).toBeInTheDocument();
    expect(screen.getByText('От 1 500 ₽ самовывоз')).toBeInTheDocument();
  });

  it('renders CTA button with link to /partners', () => {
    render(<WhyFreesportSection />);

    const ctaButton = screen.getByRole('button', { name: 'Стать партнёром' });
    expect(ctaButton).toBeInTheDocument();

    // Проверяем, что кнопка обёрнута в Link с правильным href
    const linkElement = ctaButton.closest('a');
    expect(linkElement).toHaveAttribute('href', '/partners');
  });

  it('applies responsive grid classes', () => {
    const { container } = render(<WhyFreesportSection />);

    // Проверяем наличие grid контейнера с responsive классами
    const gridContainer = container.querySelector(
      '.grid.grid-cols-1.sm\\:grid-cols-2.lg\\:grid-cols-4'
    );
    expect(gridContainer).toBeInTheDocument();
  });

  it('has proper semantic HTML structure', () => {
    const { container } = render(<WhyFreesportSection />);

    // Проверяем, что используется семантический тег section
    const section = container.querySelector('section');
    expect(section).toBeInTheDocument();
  });
});
