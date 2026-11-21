/**
 * DeliveryTeaser Component Tests
 * Story 19.2
 */

import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { DeliveryTeaser } from '../DeliveryTeaser';

describe('DeliveryTeaser', () => {
  it('renders section title correctly', () => {
    render(<DeliveryTeaser />);

    const title = screen.getByText('Доставка по России');
    expect(title).toBeInTheDocument();
    expect(title.tagName).toBe('H2');
  });

  it('renders subtitle correctly', () => {
    render(<DeliveryTeaser />);

    expect(screen.getByText('Удобные варианты получения вашего заказа')).toBeInTheDocument();
  });

  it('renders 2 delivery option cards', () => {
    render(<DeliveryTeaser />);

    expect(screen.getByText('Доставка до ТК')).toBeInTheDocument();
    expect(screen.getByText('Самовывоз со склада')).toBeInTheDocument();
  });

  it('displays БЕСПЛАТНО badge on TK card', () => {
    render(<DeliveryTeaser />);

    const badge = screen.getByText('БЕСПЛАТНО');
    expect(badge).toBeInTheDocument();
    expect(badge).toHaveClass('text-green-700');
  });

  it('displays TK delivery details correctly', () => {
    render(<DeliveryTeaser />);

    expect(screen.getByText('от 35 000 ₽')).toBeInTheDocument();
    expect(screen.getByText('До терминала ТК по России')).toBeInTheDocument();
  });

  it('displays pickup address correctly', () => {
    render(<DeliveryTeaser />);

    expect(screen.getByText('г. Ставрополь')).toBeInTheDocument();
    expect(screen.getByText('ул. Коломийцева, 40/1')).toBeInTheDocument();
  });

  it('renders CTA button with link to /delivery', () => {
    render(<DeliveryTeaser />);

    const ctaButton = screen.getByRole('button', {
      name: 'Подробнее о доставке',
    });
    expect(ctaButton).toBeInTheDocument();

    // Проверяем, что кнопка обёрнута в Link с правильным href
    const linkElement = ctaButton.closest('a');
    expect(linkElement).toHaveAttribute('href', '/delivery');
  });

  it('applies responsive layout classes', () => {
    const { container } = render(<DeliveryTeaser />);

    // Проверяем наличие grid контейнера с responsive классами
    const gridContainer = container.querySelector('.grid.grid-cols-1.md\\:grid-cols-2');
    expect(gridContainer).toBeInTheDocument();
  });

  it('has proper semantic HTML structure', () => {
    const { container } = render(<DeliveryTeaser />);

    // Проверяем, что используется семантический тег section
    const section = container.querySelector('section');
    expect(section).toBeInTheDocument();
  });

  it('applies hover effect classes to cards', () => {
    const { container } = render(<DeliveryTeaser />);

    const cards = container.querySelectorAll('.hover\\:shadow-lg');
    expect(cards.length).toBe(2);
  });
});
