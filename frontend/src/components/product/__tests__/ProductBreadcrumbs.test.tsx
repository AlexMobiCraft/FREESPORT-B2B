/**
 * Unit тесты для ProductBreadcrumbs (Story 12.1)
 */

import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import ProductBreadcrumbs from '../ProductBreadcrumbs';

describe('ProductBreadcrumbs', () => {
  const mockBreadcrumbs = [
    { id: 1, name: 'Обувь', slug: 'obuv' },
    { id: 2, name: 'Зал', slug: 'zal' },
    { id: 3, name: 'ASICS', slug: 'asics' },
  ];
  const mockProductName = 'ASICS Gel-Blast FF';

  it('рендерит все breadcrumbs', () => {
    render(<ProductBreadcrumbs breadcrumbs={mockBreadcrumbs} productName={mockProductName} />);

    // Проверяем что все элементы отображаются
    expect(screen.getByText('Главная')).toBeInTheDocument();
    expect(screen.getByText('Обувь')).toBeInTheDocument();
    expect(screen.getByText('Зал')).toBeInTheDocument();
    expect(screen.getByText('ASICS')).toBeInTheDocument();
    expect(screen.getByText(mockProductName)).toBeInTheDocument();
  });

  it('рендерит ссылку на главную страницу', () => {
    render(<ProductBreadcrumbs breadcrumbs={mockBreadcrumbs} productName={mockProductName} />);

    const homeLink = screen.getByText('Главная').closest('a');
    expect(homeLink).toHaveAttribute('href', '/');
  });

  it('рендерит ссылки на категории с корректными href', () => {
    render(<ProductBreadcrumbs breadcrumbs={mockBreadcrumbs} productName={mockProductName} />);

    const obuvLink = screen.getByText('Обувь').closest('a');
    expect(obuvLink).toHaveAttribute('href', '/catalog?category=obuv');

    const zalLink = screen.getByText('Зал').closest('a');
    expect(zalLink).toHaveAttribute('href', '/catalog?category=zal');

    const asicsLink = screen.getByText('ASICS').closest('a');
    expect(asicsLink).toHaveAttribute('href', '/catalog?category=asics');
  });

  it('отображает текущий товар с aria-current', () => {
    render(<ProductBreadcrumbs breadcrumbs={mockBreadcrumbs} productName={mockProductName} />);

    const currentItem = screen.getByText(mockProductName).closest('li');
    expect(currentItem).toHaveAttribute('aria-current', 'page');
  });

  it('содержит schema.org разметку', () => {
    const { container } = render(
      <ProductBreadcrumbs breadcrumbs={mockBreadcrumbs} productName={mockProductName} />
    );

    const breadcrumbList = container.querySelector(
      '[itemType="https://schema.org/BreadcrumbList"]'
    );
    expect(breadcrumbList).toBeInTheDocument();

    const listItems = container.querySelectorAll('[itemType="https://schema.org/ListItem"]');
    // Главная + Каталог + 3 категории + товар = 6 элементов
    expect(listItems).toHaveLength(6);
  });

  it('корректно отображает позиции в schema.org', () => {
    const { container } = render(
      <ProductBreadcrumbs breadcrumbs={mockBreadcrumbs} productName={mockProductName} />
    );

    const positions = container.querySelectorAll('meta[itemprop="position"]');
    expect(positions).toHaveLength(6);

    // Проверяем значения позиций
    expect(positions[0]).toHaveAttribute('content', '1'); // Главная
    expect(positions[1]).toHaveAttribute('content', '2'); // Каталог
    expect(positions[2]).toHaveAttribute('content', '3'); // Обувь
    expect(positions[5]).toHaveAttribute('content', '6'); // Товар
  });

  it('рендерит иконки-разделители', () => {
    const { container } = render(
      <ProductBreadcrumbs breadcrumbs={mockBreadcrumbs} productName={mockProductName} />
    );

    const separators = container.querySelectorAll('svg[aria-hidden="true"]');
    // Должно быть 4 разделителя (между Главная > Обувь > Зал > ASICS > Товар)
    expect(separators.length).toBeGreaterThanOrEqual(4);
  });

  it('корректно работает с минимальным набором breadcrumbs', () => {
    const minimalBreadcrumbs = [{ id: 1, name: 'Товары', slug: 'tovary' }];
    render(<ProductBreadcrumbs breadcrumbs={minimalBreadcrumbs} productName="Тестовый товар" />);

    expect(screen.getByText('Главная')).toBeInTheDocument();
    expect(screen.getByText('Товары')).toBeInTheDocument();
    expect(screen.getByText('Тестовый товар')).toBeInTheDocument();
  });

  it('применяет корректные CSS классы для навигации', () => {
    const { container } = render(
      <ProductBreadcrumbs breadcrumbs={mockBreadcrumbs} productName={mockProductName} />
    );

    const nav = container.querySelector('nav');
    expect(nav).toHaveAttribute('aria-label', 'Breadcrumb');
  });

  it('текущий товар имеет жирный шрифт', () => {
    render(<ProductBreadcrumbs breadcrumbs={mockBreadcrumbs} productName={mockProductName} />);

    const currentProduct = screen.getByText(mockProductName);
    expect(currentProduct).toHaveClass('font-medium');
    expect(currentProduct).toHaveClass('text-neutral-900');
  });
});
