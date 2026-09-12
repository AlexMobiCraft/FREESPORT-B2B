/**
 * CategoryCard Component Tests (Story 12.7 - QA Fix TEST-002)
 *
 * Tests covering:
 * - Rendering of all props (name, image, href, alt)
 * - Aspect-square for image
 * - Hover effects (shadow-hover, -translate-y-0.5, scale-105)
 * - Focus ring for accessibility
 * - Design System v2.0 compliance
 */

import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { CategoryCard, type CategoryCardProps } from '../CategoryCard';

describe('CategoryCard', () => {
  const mockProps: CategoryCardProps = {
    name: 'Футбол',
    image: '/images/categories/football.jpg',
    href: '/catalog/football',
  };

  describe('Rendering - Basic Structure', () => {
    it('renders as a Link component with correct href', () => {
      render(<CategoryCard {...mockProps} />);

      const link = screen.getByRole('link');
      expect(link).toHaveAttribute('href', '/catalog/football');
    });

    it('renders with white background', () => {
      render(<CategoryCard {...mockProps} />);

      const link = screen.getByRole('link');
      expect(link).toHaveClass('bg-white');
    });

    it('renders with rounded corners (rounded-2xl)', () => {
      render(<CategoryCard {...mockProps} />);

      const link = screen.getByRole('link');
      expect(link).toHaveClass('rounded-2xl', 'overflow-hidden');
    });

    it('renders with default shadow', () => {
      render(<CategoryCard {...mockProps} />);

      const link = screen.getByRole('link');
      expect(link).toHaveClass('shadow-default');
    });
  });

  describe('Rendering - Image', () => {
    it('renders image with alt text matching name by default', () => {
      render(<CategoryCard {...mockProps} />);

      const image = screen.getByAltText('Футбол');
      expect(image).toBeInTheDocument();
    });

    it('renders image with custom alt text when provided', () => {
      render(<CategoryCard {...mockProps} alt="Спортивная одежда для футбола" />);

      const image = screen.getByAltText('Спортивная одежда для футбола');
      expect(image).toBeInTheDocument();
    });

    it('image container has aspect-square ratio', () => {
      render(<CategoryCard {...mockProps} />);

      const link = screen.getByRole('link');
      const imageContainer = link.querySelector('.aspect-square');
      expect(imageContainer).toBeInTheDocument();
    });

    it('renders Image component with fill property', () => {
      render(<CategoryCard {...mockProps} />);

      const image = screen.getByAltText('Футбол');
      expect(image).toHaveClass('object-cover');
    });

    it('applies hover scale effect to image', () => {
      render(<CategoryCard {...mockProps} />);

      const image = screen.getByAltText('Футбол');
      expect(image).toHaveClass(
        'group-hover:scale-105',
        'transition-transform',
        'duration-[180ms]',
        'ease-in-out'
      );
    });

    it('image has relative positioning in aspect-square container', () => {
      render(<CategoryCard {...mockProps} />);

      const link = screen.getByRole('link');
      const imageContainer = link.querySelector('.aspect-square');
      expect(imageContainer).toHaveClass('relative', 'overflow-hidden');
    });
  });

  describe('Rendering - Category Name', () => {
    it('renders category name as h3 element', () => {
      render(<CategoryCard {...mockProps} />);

      const heading = screen.getByRole('heading', { level: 3 });
      expect(heading).toHaveTextContent('Футбол');
    });

    it('applies correct typography to name (text-xl font-semibold)', () => {
      render(<CategoryCard {...mockProps} />);

      const heading = screen.getByRole('heading', { level: 3 });
      expect(heading).toHaveClass('text-xl', 'font-semibold', 'text-primary');
    });

    it('centers category name text', () => {
      render(<CategoryCard {...mockProps} />);

      const heading = screen.getByRole('heading', { level: 3 });
      expect(heading).toHaveClass('text-center');
    });

    it('name is inside p-4 padding container', () => {
      render(<CategoryCard {...mockProps} />);

      const link = screen.getByRole('link');
      const contentDiv = link.querySelector('.p-4');
      expect(contentDiv).toBeInTheDocument();

      const heading = screen.getByRole('heading', { level: 3 });
      expect(contentDiv).toContainElement(heading);
    });

    it('renders different category names correctly', () => {
      const categories = ['Фитнес', 'Единоборства', 'Плавание', 'Детский транспорт'];

      categories.forEach(name => {
        const { unmount } = render(<CategoryCard {...mockProps} name={name} />);
        expect(screen.getByRole('heading', { level: 3 })).toHaveTextContent(name);
        unmount();
      });
    });
  });

  describe('Hover Effects', () => {
    it('applies hover shadow effect', () => {
      render(<CategoryCard {...mockProps} />);

      const link = screen.getByRole('link');
      expect(link).toHaveClass('hover:shadow-hover');
    });

    it('applies hover lift effect (-translate-y-0.5)', () => {
      render(<CategoryCard {...mockProps} />);

      const link = screen.getByRole('link');
      expect(link).toHaveClass('hover:-translate-y-0.5');
    });

    it('applies transition to all hover effects', () => {
      render(<CategoryCard {...mockProps} />);

      const link = screen.getByRole('link');
      expect(link).toHaveClass('transition-all', 'duration-[180ms]', 'ease-in-out');
    });

    it('card is part of group for coordinated hover effects', () => {
      render(<CategoryCard {...mockProps} />);

      const link = screen.getByRole('link');
      expect(link).toHaveClass('group');
    });
  });

  describe('Accessibility', () => {
    it('link has proper focus styles', () => {
      render(<CategoryCard {...mockProps} />);

      const link = screen.getByRole('link');
      expect(link).toHaveClass(
        'focus:outline-none',
        'focus:ring-2',
        'focus:ring-primary',
        'focus:ring-offset-2'
      );
    });

    it('image has descriptive alt text', () => {
      render(<CategoryCard {...mockProps} />);

      const image = screen.getByAltText('Футбол');
      expect(image).toBeInTheDocument();
    });

    it('uses semantic heading for category name', () => {
      render(<CategoryCard {...mockProps} />);

      const heading = screen.getByRole('heading', { level: 3 });
      expect(heading).toBeInTheDocument();
    });

    it('card is keyboard accessible via Link', () => {
      render(<CategoryCard {...mockProps} />);

      const link = screen.getByRole('link');
      expect(link).toBeInTheDocument();
    });

    it('renders with custom alt text for better accessibility', () => {
      const customAlt = 'Категория спортивных товаров для футбола';
      render(<CategoryCard {...mockProps} alt={customAlt} />);

      const image = screen.getByAltText(customAlt);
      expect(image).toBeInTheDocument();
    });
  });

  describe('Design System v2.0 Compliance', () => {
    it('uses correct shadow tokens (shadow-default, hover:shadow-hover)', () => {
      render(<CategoryCard {...mockProps} />);

      const link = screen.getByRole('link');
      expect(link).toHaveClass('shadow-default', 'hover:shadow-hover');
    });

    it('uses correct border radius (rounded-2xl = 16px)', () => {
      render(<CategoryCard {...mockProps} />);

      const link = screen.getByRole('link');
      expect(link).toHaveClass('rounded-2xl');
    });

    it('uses correct typography for title (text-xl font-semibold)', () => {
      render(<CategoryCard {...mockProps} />);

      const heading = screen.getByRole('heading', { level: 3 });
      expect(heading).toHaveClass('text-xl', 'font-semibold');
    });

    it('uses correct color token (text-primary)', () => {
      render(<CategoryCard {...mockProps} />);

      const heading = screen.getByRole('heading', { level: 3 });
      expect(heading).toHaveClass('text-primary');
    });

    it('uses correct motion duration (180ms)', () => {
      render(<CategoryCard {...mockProps} />);

      const link = screen.getByRole('link');
      expect(link).toHaveClass('duration-[180ms]', 'ease-in-out');
    });

    it('uses correct spacing (p-4 for content)', () => {
      render(<CategoryCard {...mockProps} />);

      const link = screen.getByRole('link');
      const contentDiv = link.querySelector('.p-4');
      expect(contentDiv).toBeInTheDocument();
    });

    it('uses correct hover lift transform (-translate-y-0.5 = -2px)', () => {
      render(<CategoryCard {...mockProps} />);

      const link = screen.getByRole('link');
      expect(link).toHaveClass('hover:-translate-y-0.5');
    });
  });

  describe('Link Behavior', () => {
    it('renders with correct href for different categories', () => {
      const categories = [
        { name: 'Фитнес', href: '/catalog/fitness' },
        { name: 'Единоборства', href: '/catalog/martial-arts' },
        { name: 'Плавание', href: '/catalog/swimming' },
      ];

      categories.forEach(({ name, href }) => {
        const { unmount } = render(<CategoryCard {...mockProps} name={name} href={href} />);
        const link = screen.getByRole('link');
        expect(link).toHaveAttribute('href', href);
        unmount();
      });
    });

    it('renders absolute href correctly', () => {
      render(<CategoryCard {...mockProps} href="https://example.com/catalog" />);

      const link = screen.getByRole('link');
      expect(link).toHaveAttribute('href', 'https://example.com/catalog');
    });

    it('renders href with query parameters', () => {
      render(<CategoryCard {...mockProps} href="/catalog/football?brand=nike" />);

      const link = screen.getByRole('link');
      expect(link).toHaveAttribute('href', '/catalog/football?brand=nike');
    });
  });

  describe('Edge Cases', () => {
    it('renders with minimal name', () => {
      render(<CategoryCard {...mockProps} name="А" />);

      expect(screen.getByRole('heading', { level: 3 })).toHaveTextContent('А');
    });

    it('renders with very long name', () => {
      const longName = 'Очень длинное название категории товаров для тестирования';
      render(<CategoryCard {...mockProps} name={longName} />);

      expect(screen.getByRole('heading', { level: 3 })).toHaveTextContent(longName);
    });

    it('renders with empty alt text (defaults to name)', () => {
      render(<CategoryCard {...mockProps} />);

      const image = screen.getByAltText('Футбол');
      expect(image).toBeInTheDocument();
    });

    it('handles Cyrillic characters in href', () => {
      render(<CategoryCard {...mockProps} href="/каталог/футбол" />);

      const link = screen.getByRole('link');
      expect(link).toHaveAttribute('href', '/каталог/футбол');
    });

    it('renders with special characters in name', () => {
      render(<CategoryCard {...mockProps} name="Фитнес & Йога" />);

      expect(screen.getByRole('heading', { level: 3 })).toHaveTextContent('Фитнес & Йога');
    });

    it('renders with data URI image', () => {
      const dataUri = 'data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMTAwIiBoZWlnaHQ9IjEwMCI+PC9zdmc+';
      render(<CategoryCard {...mockProps} image={dataUri} />);

      const link = screen.getByRole('link');
      expect(link).toBeInTheDocument();
    });
  });

  describe('Component Metadata', () => {
    it('has displayName set for debugging', () => {
      expect(CategoryCard.displayName).toBe('CategoryCard');
    });
  });

  describe('Integration - Multiple Cards', () => {
    it('renders multiple cards with different props', () => {
      const cards: CategoryCardProps[] = [
        { name: 'Футбол', image: '/images/categories/football.jpg', href: '/catalog/football' },
        { name: 'Фитнес', image: '/images/categories/fitness.jpg', href: '/catalog/fitness' },
        { name: 'Плавание', image: '/images/categories/swimming.jpg', href: '/catalog/swimming' },
      ];

      const { container } = render(
        <div>
          {cards.map((card, index) => (
            <CategoryCard key={index} {...card} />
          ))}
        </div>
      );

      const links = container.querySelectorAll('a');
      expect(links).toHaveLength(3);

      cards.forEach(card => {
        expect(screen.getByRole('heading', { name: card.name })).toBeInTheDocument();
      });
    });
  });
});
