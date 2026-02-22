/**
 * Unit tests for NewsCard component
 * Story 20.3 - Task 3
 */

import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { NewsCard } from '../NewsCard';

describe('NewsCard', () => {
  const mockProps = {
    title: 'Тестовая новость',
    slug: 'testovaya-novost',
    excerpt: 'Краткое описание тестовой новости для проверки.',
    image: '/images/test-news.jpg',
    publishedAt: '2025-12-26T10:00:00+03:00',
  };

  it('renders news image', () => {
    render(<NewsCard {...mockProps} />);

    const image = screen.getByRole('img', { name: mockProps.title });
    expect(image).toBeInTheDocument();
    expect(image).toHaveAttribute('alt', mockProps.title);
  });

  it('renders news title', () => {
    render(<NewsCard {...mockProps} />);

    const title = screen.getByRole('heading', { name: mockProps.title });
    expect(title).toBeInTheDocument();
    expect(title).toHaveTextContent(mockProps.title);
  });

  it('renders formatted date', () => {
    render(<NewsCard {...mockProps} />);

    // Проверяем наличие элемента time с правильным dateTime
    const timeElement = screen.getByText(/26 декабря 2025/i);
    expect(timeElement).toBeInTheDocument();
    expect(timeElement.tagName).toBe('TIME');
    expect(timeElement).toHaveAttribute('dateTime', mockProps.publishedAt);
  });

  it('renders excerpt', () => {
    render(<NewsCard {...mockProps} />);

    const excerpt = screen.getByText(mockProps.excerpt);
    expect(excerpt).toBeInTheDocument();
  });

  it('links to /news/{slug}', () => {
    render(<NewsCard {...mockProps} />);

    const link = screen.getByRole('link', { name: `Читать новость: ${mockProps.title}` });
    expect(link).toBeInTheDocument();
    expect(link).toHaveAttribute('href', `/news/${mockProps.slug}`);
  });

  it('uses fallback image when image prop is empty', () => {
    const propsWithoutImage = { ...mockProps, image: '' };
    render(<NewsCard {...propsWithoutImage} />);

    const image = screen.getByRole('img', { name: mockProps.title });
    expect(image).toBeInTheDocument();
    // Fallback изображение должно быть установлено (normalizeImageUrl возвращает No_image.svg для пустых значений)
    expect(image).toHaveAttribute('src', expect.stringContaining('No_image.svg'));
  });

  it('has proper accessibility attributes', () => {
    render(<NewsCard {...mockProps} />);

    // Проверяем aria-label на ссылке
    const link = screen.getByRole('link');
    expect(link).toHaveAttribute('aria-label', `Читать новость: ${mockProps.title}`);

    // Проверяем article внутри ссылки
    const article = link.querySelector('article');
    expect(article).toBeInTheDocument();
  });
});
