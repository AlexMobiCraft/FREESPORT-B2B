/**
 * AboutTeaser Component Tests
 * Story 19.2
 */

import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { AboutTeaser } from '../AboutTeaser';

describe('AboutTeaser', () => {
  it('renders company title correctly', () => {
    render(<AboutTeaser />);

    const title = screen.getByText('FREESPORT');
    expect(title).toBeInTheDocument();
    expect(title.tagName).toBe('H2');
  });

  it('renders company subtitle', () => {
    render(<AboutTeaser />);

    expect(
      screen.getByText('Федеральный оптовый поставщик и производитель спортивных товаров')
    ).toBeInTheDocument();
  });

  it('renders company description', () => {
    render(<AboutTeaser />);

    const description = screen.getByText(/Мы создаём качественные спортивные товары/i);
    expect(description).toBeInTheDocument();
  });

  it('renders values section title', () => {
    render(<AboutTeaser />);

    const valuesTitle = screen.getByText('Наши ценности');
    expect(valuesTitle).toBeInTheDocument();
    expect(valuesTitle.tagName).toBe('H3');
  });

  it('renders 4 value items', () => {
    render(<AboutTeaser />);

    expect(screen.getByText('Оперативность')).toBeInTheDocument();
    expect(screen.getByText('Качество')).toBeInTheDocument();
    expect(screen.getByText('Инновации')).toBeInTheDocument();
    expect(screen.getByText('Надёжность')).toBeInTheDocument();
  });

  it('renders CTA button with link to /about', () => {
    render(<AboutTeaser />);

    const ctaButton = screen.getByRole('button', {
      name: 'Узнать больше о нас',
    });
    expect(ctaButton).toBeInTheDocument();

    // Проверяем, что кнопка обёрнута в Link с правильным href
    const linkElement = ctaButton.closest('a');
    expect(linkElement).toHaveAttribute('href', '/about');
  });

  it('applies responsive layout classes', () => {
    const { container } = render(<AboutTeaser />);

    // Проверяем наличие grid контейнера с responsive классами
    const gridContainer = container.querySelector('.grid.grid-cols-1.md\\:grid-cols-2');
    expect(gridContainer).toBeInTheDocument();
  });

  it('has proper semantic HTML structure', () => {
    const { container } = render(<AboutTeaser />);

    // Проверяем, что используется семантический тег section
    const section = container.querySelector('section');
    expect(section).toBeInTheDocument();
  });

  it('renders Trophy icon for company', () => {
    const { container } = render(<AboutTeaser />);

    // Проверяем наличие иконки Trophy
    const iconContainer = container.querySelector('.bg-yellow-100');
    expect(iconContainer).toBeInTheDocument();
  });

  it('applies hover effects to value items', () => {
    const { container } = render(<AboutTeaser />);

    // Проверяем наличие hover классов
    const valueItems = container.querySelectorAll('.hover\\:bg-primary-subtle');
    expect(valueItems.length).toBe(4);
  });

  it('displays values in grid layout', () => {
    const { container } = render(<AboutTeaser />);

    // Проверяем grid для ценностей
    const valuesGrid = container.querySelector('.grid.grid-cols-1.sm\\:grid-cols-2');
    expect(valuesGrid).toBeInTheDocument();
  });
});
