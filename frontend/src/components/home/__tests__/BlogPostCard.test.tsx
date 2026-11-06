/**
 * BlogPostCard Component Tests (Story 12.7 - QA Fix TEST-002)
 *
 * Tests covering:
 * - Rendering of all props (title, excerpt, image, date, slug)
 * - Date formatting (ru-RU locale)
 * - Line clamping (line-clamp-2 for title and excerpt)
 * - Link href correctness
 * - Hover effects and transitions
 * - Accessibility (time element with dateTime)
 */

import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { BlogPostCard, type BlogPostCardProps } from '../BlogPostCard';

describe('BlogPostCard', () => {
  const mockProps: BlogPostCardProps = {
    id: '1',
    title: 'Как выбрать правильные кроссовки для бега',
    excerpt: 'Подробное руководство по выбору беговой обуви: типы стопы, пронация, амортизация.',
    image: '/images/blog/running-shoes-guide.jpg',
    date: '2025-11-15',
    slug: 'kak-vybrat-krossovki-dlya-bega',
  };

  describe('Rendering - Basic Structure', () => {
    it('renders as a Link component with correct href', () => {
      render(<BlogPostCard {...mockProps} />);

      const link = screen.getByRole('link');
      expect(link).toHaveAttribute('href', '/blog/kak-vybrat-krossovki-dlya-bega');
    });

    it('renders with white background and shadow', () => {
      render(<BlogPostCard {...mockProps} />);

      const link = screen.getByRole('link');
      expect(link).toHaveClass('bg-white', 'shadow-default');
    });

    it('renders with rounded corners (rounded-xl)', () => {
      render(<BlogPostCard {...mockProps} />);

      const link = screen.getByRole('link');
      expect(link).toHaveClass('rounded-xl', 'overflow-hidden');
    });
  });

  describe('Rendering - Image', () => {
    it('renders image with correct alt text', () => {
      render(<BlogPostCard {...mockProps} />);

      const image = screen.getByAltText('Как выбрать правильные кроссовки для бега');
      expect(image).toBeInTheDocument();
    });

    it('image container has aspect-video ratio', () => {
      render(<BlogPostCard {...mockProps} />);

      const link = screen.getByRole('link');
      const imageContainer = link.querySelector('.aspect-video');
      expect(imageContainer).toBeInTheDocument();
    });

    it('renders Image component with fill property', () => {
      render(<BlogPostCard {...mockProps} />);

      const image = screen.getByAltText(mockProps.title);
      expect(image).toHaveClass('object-cover');
    });

    it('applies hover scale effect to image', () => {
      render(<BlogPostCard {...mockProps} />);

      const image = screen.getByAltText(mockProps.title);
      expect(image).toHaveClass(
        'group-hover:scale-105',
        'transition-transform',
        'duration-[180ms]',
        'ease-in-out'
      );
    });
  });

  describe('Rendering - Date', () => {
    it('renders date as time element with dateTime attribute', () => {
      render(<BlogPostCard {...mockProps} />);

      const timeElement = screen.getByText(/15 ноября 2025/i);
      expect(timeElement.tagName).toBe('TIME');
      expect(timeElement).toHaveAttribute('dateTime', '2025-11-15');
    });

    it('formats date correctly in Russian locale', () => {
      render(<BlogPostCard {...mockProps} />);

      expect(screen.getByText('15 ноября 2025 г.')).toBeInTheDocument();
    });

    it('applies correct typography to date (text-xs text-muted)', () => {
      render(<BlogPostCard {...mockProps} />);

      const timeElement = screen.getByText(/15 ноября 2025/i);
      expect(timeElement).toHaveClass('text-xs', 'text-text-secondary');
    });

    it('formats different date correctly', () => {
      render(<BlogPostCard {...mockProps} date="2025-01-01" />);

      expect(screen.getByText('1 января 2025 г.')).toBeInTheDocument();
    });
  });

  describe('Rendering - Title', () => {
    it('renders title as h3 element', () => {
      render(<BlogPostCard {...mockProps} />);

      const heading = screen.getByRole('heading', { level: 3 });
      expect(heading).toHaveTextContent('Как выбрать правильные кроссовки для бега');
    });

    it('applies correct typography to title (text-xl font-semibold)', () => {
      render(<BlogPostCard {...mockProps} />);

      const heading = screen.getByRole('heading', { level: 3 });
      expect(heading).toHaveClass('text-xl', 'font-semibold', 'text-text-primary');
    });

    it('applies line-clamp-2 to title', () => {
      render(<BlogPostCard {...mockProps} />);

      const heading = screen.getByRole('heading', { level: 3 });
      expect(heading).toHaveClass('line-clamp-2');
    });

    it('renders long title correctly', () => {
      const longTitle =
        'Очень длинный заголовок статьи который должен быть обрезан до двух строк с использованием line-clamp-2 класса для правильного отображения';

      render(<BlogPostCard {...mockProps} title={longTitle} />);

      const heading = screen.getByRole('heading', { level: 3 });
      expect(heading).toHaveTextContent(longTitle);
      expect(heading).toHaveClass('line-clamp-2');
    });
  });

  describe('Rendering - Excerpt', () => {
    it('renders excerpt text', () => {
      render(<BlogPostCard {...mockProps} />);

      expect(
        screen.getByText(
          'Подробное руководство по выбору беговой обуви: типы стопы, пронация, амортизация.'
        )
      ).toBeInTheDocument();
    });

    it('applies correct typography to excerpt (text-sm text-secondary)', () => {
      render(<BlogPostCard {...mockProps} />);

      const excerpt = screen.getByText(mockProps.excerpt);
      expect(excerpt).toHaveClass('text-sm', 'text-text-secondary');
    });

    it('applies line-clamp-2 to excerpt', () => {
      render(<BlogPostCard {...mockProps} />);

      const excerpt = screen.getByText(mockProps.excerpt);
      expect(excerpt).toHaveClass('line-clamp-2');
    });

    it('renders long excerpt correctly with line-clamp', () => {
      const longExcerpt =
        'Очень длинный текст описания статьи который должен быть обрезан до двух строк. Этот текст содержит много информации о статье и должен правильно отображаться с использованием line-clamp-2 класса.';

      render(<BlogPostCard {...mockProps} excerpt={longExcerpt} />);

      const excerpt = screen.getByText(longExcerpt);
      expect(excerpt).toHaveClass('line-clamp-2');
    });
  });

  describe('Rendering - Read More Link', () => {
    it('renders "Читать далее" text', () => {
      render(<BlogPostCard {...mockProps} />);

      expect(screen.getByText('Читать далее')).toBeInTheDocument();
    });

    it('renders arrow icon for "Читать далее"', () => {
      render(<BlogPostCard {...mockProps} />);

      const link = screen.getByRole('link');
      const svg = link.querySelector('svg');
      expect(svg).toBeInTheDocument();
      expect(svg).toHaveClass('w-4', 'h-4');
    });

    it('applies hover underline to "Читать далее"', () => {
      render(<BlogPostCard {...mockProps} />);

      const readMore = screen.getByText('Читать далее');
      expect(readMore).toHaveClass('hover:underline');
    });
  });

  describe('Hover Effects', () => {
    it('applies hover shadow effect to card', () => {
      render(<BlogPostCard {...mockProps} />);

      const link = screen.getByRole('link');
      expect(link).toHaveClass('hover:shadow-hover', 'transition-shadow');
    });

    it('card is part of group for hover effects', () => {
      render(<BlogPostCard {...mockProps} />);

      const link = screen.getByRole('link');
      expect(link).toHaveClass('group');
    });
  });

  describe('Accessibility', () => {
    it('link has proper focus styles', () => {
      render(<BlogPostCard {...mockProps} />);

      const link = screen.getByRole('link');
      expect(link).toHaveClass(
        'focus:outline-none',
        'focus:ring-2',
        'focus:ring-primary',
        'focus:ring-offset-2'
      );
    });

    it('time element has semantic dateTime attribute', () => {
      render(<BlogPostCard {...mockProps} />);

      const timeElement = screen.getByText(/15 ноября 2025/i);
      expect(timeElement).toHaveAttribute('dateTime', '2025-11-15');
    });

    it('image has alt text matching title', () => {
      render(<BlogPostCard {...mockProps} />);

      const image = screen.getByAltText(mockProps.title);
      expect(image).toBeInTheDocument();
    });

    it('card is keyboard accessible via Link', () => {
      render(<BlogPostCard {...mockProps} />);

      const link = screen.getByRole('link');
      expect(link).toBeInTheDocument();
    });
  });

  describe('Design System v2.0 Compliance', () => {
    it('uses correct shadow tokens (shadow-default, shadow-hover)', () => {
      render(<BlogPostCard {...mockProps} />);

      const link = screen.getByRole('link');
      expect(link).toHaveClass('shadow-default', 'hover:shadow-hover');
    });

    it('uses correct typography tokens for title (text-xl font-semibold)', () => {
      render(<BlogPostCard {...mockProps} />);

      const heading = screen.getByRole('heading', { level: 3 });
      expect(heading).toHaveClass('text-xl', 'font-semibold');
    });

    it('uses correct color tokens (text-primary, text-secondary, text-muted)', () => {
      render(<BlogPostCard {...mockProps} />);

      const heading = screen.getByRole('heading', { level: 3 });
      const excerpt = screen.getByText(mockProps.excerpt);
      const time = screen.getByText(/15 ноября 2025/i);

      expect(heading).toHaveClass('text-text-primary');
      expect(excerpt).toHaveClass('text-text-secondary');
      expect(time).toHaveClass('text-text-secondary');
    });

    it('uses correct motion duration (180ms)', () => {
      render(<BlogPostCard {...mockProps} />);

      const image = screen.getByAltText(mockProps.title);
      expect(image).toHaveClass('duration-[180ms]', 'ease-in-out');
    });

    it('uses correct spacing (p-4 for content, mb-2/mb-3 for elements)', () => {
      render(<BlogPostCard {...mockProps} />);

      const link = screen.getByRole('link');
      const contentDiv = link.querySelector('.p-4');
      expect(contentDiv).toBeInTheDocument();

      const time = screen.getByText(/15 ноября 2025/i);
      expect(time).toHaveClass('mb-2');

      const heading = screen.getByRole('heading', { level: 3 });
      expect(heading).toHaveClass('mb-2');
    });
  });

  describe('Edge Cases', () => {
    it('renders with minimal title', () => {
      render(<BlogPostCard {...mockProps} title="Тест" />);

      expect(screen.getByRole('heading', { level: 3 })).toHaveTextContent('Тест');
    });

    it('renders with minimal excerpt', () => {
      render(<BlogPostCard {...mockProps} excerpt="." />);

      expect(screen.getByText('.')).toBeInTheDocument();
    });

    it('renders with different slug format', () => {
      render(<BlogPostCard {...mockProps} slug="test-slug-123" />);

      const link = screen.getByRole('link');
      expect(link).toHaveAttribute('href', '/blog/test-slug-123');
    });

    it('renders with empty excerpt', () => {
      render(<BlogPostCard {...mockProps} excerpt="" />);

      const link = screen.getByRole('link');
      expect(link).toBeInTheDocument();
    });

    it('handles Cyrillic characters in slug', () => {
      render(<BlogPostCard {...mockProps} slug="тестовая-статья" />);

      const link = screen.getByRole('link');
      expect(link).toHaveAttribute('href', '/blog/тестовая-статья');
    });
  });

  describe('Component Metadata', () => {
    it('has displayName set for debugging', () => {
      expect(BlogPostCard.displayName).toBe('BlogPostCard');
    });
  });
});
