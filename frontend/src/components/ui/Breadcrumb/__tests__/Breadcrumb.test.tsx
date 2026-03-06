/**
 * Breadcrumb Component Tests
 * Покрытие длинной цепочки, ellipsis, tooltip
 */

import React from 'react';
import { render, screen } from '@testing-library/react';
import { Breadcrumb, BreadcrumbItem } from '../Breadcrumb';

describe('Breadcrumb', () => {
  const simpleItems: BreadcrumbItem[] = [
    { label: 'Home', href: '/' },
    { label: 'Products', href: '/products' },
    { label: 'Shoes' },
  ];

  // Базовый рендеринг
  it('renders breadcrumb items', () => {
    render(<Breadcrumb items={simpleItems} />);

    expect(screen.getByText('Home')).toBeInTheDocument();
    expect(screen.getByText('Products')).toBeInTheDocument();
    expect(screen.getByText('Shoes')).toBeInTheDocument();
  });

  // Navigation
  it('has proper navigation role', () => {
    render(<Breadcrumb items={simpleItems} />);

    const nav = screen.getByRole('navigation', { name: /breadcrumb/i });
    expect(nav).toBeInTheDocument();
  });

  // Links
  describe('Links', () => {
    it('renders links for items with href (except last)', () => {
      render(<Breadcrumb items={simpleItems} />);

      const homeLink = screen.getByRole('link', { name: 'Home' });
      expect(homeLink).toHaveAttribute('href', '/');

      const productsLink = screen.getByRole('link', { name: 'Products' });
      expect(productsLink).toHaveAttribute('href', '/products');
    });

    it('renders last item as span (not link)', () => {
      render(<Breadcrumb items={simpleItems} />);

      const lastItem = screen.getByText('Shoes');
      expect(lastItem.tagName).toBe('SPAN');
      expect(lastItem).toHaveClass('text-text-primary', 'font-medium');
    });

    it('renders item without href as span', () => {
      const items: BreadcrumbItem[] = [{ label: 'Home', href: '/' }, { label: 'No Link' }];

      render(<Breadcrumb items={items} />);

      const noLinkItem = screen.getByText('No Link');
      expect(noLinkItem.tagName).toBe('SPAN');
    });
  });

  // Separators
  describe('Separators', () => {
    it('renders ChevronRight separators between items', () => {
      const { container } = render(<Breadcrumb items={simpleItems} />);

      const separators = container.querySelectorAll('svg[aria-hidden="true"]');
      // 2 separators for 3 items
      expect(separators).toHaveLength(2);
    });

    it('does not render separator after last item', () => {
      const { container } = render(<Breadcrumb items={simpleItems} />);

      const listItems = container.querySelectorAll('li');
      const lastItem = listItems[listItems.length - 1];
      const separator = lastItem.querySelector('svg');

      expect(separator).not.toBeInTheDocument();
    });
  });

  // Edge Case: Длинная цепочка (больше 5 элементов)
  describe('Long Chain Collapse', () => {
    const longItems: BreadcrumbItem[] = [
      { label: 'Home', href: '/' },
      { label: 'Category 1', href: '/cat1' },
      { label: 'Category 2', href: '/cat2' },
      { label: 'Category 3', href: '/cat3' },
      { label: 'Subcategory', href: '/subcat' },
      { label: 'Product' },
    ];

    it('collapses items when more than 5', () => {
      render(<Breadcrumb items={longItems} />);

      // Should show: Home > ... > Subcategory > Product
      expect(screen.getByText('Home')).toBeInTheDocument();
      expect(screen.getByText('...')).toBeInTheDocument();
      expect(screen.getByText('Subcategory')).toBeInTheDocument();
      expect(screen.getByText('Product')).toBeInTheDocument();

      // Hidden items
      expect(screen.queryByText('Category 1')).not.toBeInTheDocument();
      expect(screen.queryByText('Category 2')).not.toBeInTheDocument();
      expect(screen.queryByText('Category 3')).not.toBeInTheDocument();
    });

    it('ellipsis has tooltip with full path', () => {
      render(<Breadcrumb items={longItems} />);

      const ellipsis = screen.getByText('...');
      expect(ellipsis).toHaveAttribute('title', 'Category 1 > Category 2 > Category 3');
    });

    it('ellipsis has cursor-help style', () => {
      render(<Breadcrumb items={longItems} />);

      const ellipsis = screen.getByText('...');
      expect(ellipsis).toHaveClass('cursor-help');
    });

    it('does not collapse when 5 or fewer items', () => {
      const fiveItems = longItems.slice(0, 5);
      render(<Breadcrumb items={fiveItems} />);

      expect(screen.queryByText('...')).not.toBeInTheDocument();
      expect(screen.getByText('Category 1')).toBeInTheDocument();
    });
  });

  // Edge Case: Длинный текст элемента
  describe('Long Text Truncation', () => {
    it('truncates long text with max-w-[150px]', () => {
      const items: BreadcrumbItem[] = [
        { label: 'Home', href: '/' },
        { label: 'Very Long Category Name That Should Be Truncated', href: '/long' },
        { label: 'Last', href: '/last' },
      ];

      render(<Breadcrumb items={items} />);

      const longLink = screen.getByRole('link', { name: /very long/i });
      expect(longLink).toHaveClass('max-w-[150px]');
      expect(longLink).toHaveClass('truncate');
    });

    it('has title attribute for tooltip on long text', () => {
      const longLabel = 'Very Long Category Name';
      const items: BreadcrumbItem[] = [
        { label: 'Home', href: '/' },
        { label: longLabel, href: '/long' },
        { label: 'Last', href: '/last' },
      ];

      render(<Breadcrumb items={items} />);

      const longLink = screen.getByRole('link', { name: longLabel });
      expect(longLink).toHaveAttribute('title', longLabel);
    });
  });

  // Styling
  describe('Styling', () => {
    it('has proper link styles', () => {
      render(<Breadcrumb items={simpleItems} />);

      const link = screen.getByRole('link', { name: 'Home' });
      expect(link).toHaveClass('text-neutral-700');
      expect(link).toHaveClass('hover:text-primary');
    });

    it('last item has primary text color', () => {
      render(<Breadcrumb items={simpleItems} />);

      const lastItem = screen.getByText('Shoes');
      expect(lastItem).toHaveClass('text-text-primary');
      expect(lastItem).toHaveClass('font-medium');
    });
  });

  // Accessibility
  describe('Accessibility', () => {
    it('uses semantic nav element', () => {
      render(<Breadcrumb items={simpleItems} />);

      expect(screen.getByRole('navigation')).toBeInTheDocument();
    });

    it('has aria-label on nav', () => {
      render(<Breadcrumb items={simpleItems} />);

      const nav = screen.getByRole('navigation');
      expect(nav).toHaveAttribute('aria-label', 'Breadcrumb');
    });

    it('uses ordered list for items', () => {
      const { container } = render(<Breadcrumb items={simpleItems} />);

      const ol = container.querySelector('ol');
      expect(ol).toBeInTheDocument();
    });

    it('separators have aria-hidden', () => {
      const { container } = render(<Breadcrumb items={simpleItems} />);

      const separators = container.querySelectorAll('svg');
      separators.forEach(separator => {
        expect(separator).toHaveAttribute('aria-hidden', 'true');
      });
    });
  });

  // Custom className
  it('accepts custom className', () => {
    const { container } = render(<Breadcrumb items={simpleItems} className="custom-class" />);

    const nav = container.querySelector('nav');
    expect(nav).toHaveClass('custom-class');
  });

  // Empty items
  it('handles empty items array', () => {
    const { container } = render(<Breadcrumb items={[]} />);

    const nav = container.querySelector('nav');
    expect(nav).toBeInTheDocument();
  });
});
