/**
 * Unit-тесты для страницы "О компании" (/about)
 * Story 19.3 - AC 8
 *
 * Проверяет:
 * - Корректный рендеринг всех секций
 * - SEO metadata
 * - Breadcrumb навигацию
 * - Отображение ценностей и статистики
 * - CTA секцию
 */

import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import AboutPage, { metadata } from '../page';

// Mock Next.js Link component
vi.mock('next/link', () => ({
  default: ({ children, href }: { children: React.ReactNode; href: string }) => (
    <a href={href}>{children}</a>
  ),
}));

describe('AboutPage (/about)', () => {
  describe('Рендеринг страницы', () => {
    it('должна рендериться без ошибок', () => {
      const { container } = render(<AboutPage />);
      expect(container).toBeInTheDocument();
    });

    it('должна иметь корректную структуру', () => {
      const { container } = render(<AboutPage />);
      const sections = container.querySelectorAll('section');
      // Hero, "Кто мы", Ценности, Статистика, CTA = 5 секций
      expect(sections.length).toBe(5);
    });
  });

  describe('Breadcrumb навигация', () => {
    it('должна отображать breadcrumb', () => {
      render(<AboutPage />);
      expect(screen.getByText('Главная')).toBeInTheDocument();
      expect(screen.getByText('О компании')).toBeInTheDocument();
    });

    it('должна иметь ссылку на главную', () => {
      render(<AboutPage />);
      const homeLink = screen.getByText('Главная').closest('a');
      expect(homeLink).toHaveAttribute('href', '/');
    });
  });

  describe('Hero секция', () => {
    it('должна отображать заголовок h1', () => {
      render(<AboutPage />);
      const heading = screen.getByRole('heading', { level: 1 });
      expect(heading).toHaveTextContent('О компании FREESPORT');
    });

    it('должна отображать подзаголовок', () => {
      render(<AboutPage />);
      expect(
        screen.getByText(
          /Федеральный оптовый поставщик и производитель спортивных товаров с 2015 года/i
        )
      ).toBeInTheDocument();
    });
  });

  describe('Секция "Кто мы"', () => {
    it('должна отображать заголовок секции', () => {
      render(<AboutPage />);
      const heading = screen.getByRole('heading', { level: 2, name: /Кто мы/i });
      expect(heading).toBeInTheDocument();
    });

    it('должна отображать описание компании', () => {
      render(<AboutPage />);
      const descriptions = screen.getAllByText(
        /федеральный оптовый поставщик и производитель спортивных товаров/i
      );
      expect(descriptions.length).toBeGreaterThanOrEqual(1);
    });

    it('должна отображать принципы работы', () => {
      render(<AboutPage />);
      expect(
        screen.getByText(/качество, надёжность и долгосрочное партнёрство/i)
      ).toBeInTheDocument();
    });
  });

  describe('Секция "Наши ценности"', () => {
    it('должна отображать заголовок секции', () => {
      render(<AboutPage />);
      const heading = screen.getByRole('heading', { level: 2, name: /Наши ценности/i });
      expect(heading).toBeInTheDocument();
    });

    it('должна отображать 4 карточки ценностей', () => {
      render(<AboutPage />);
      expect(screen.getByText('Оперативность')).toBeInTheDocument();
      expect(screen.getByText('Качество')).toBeInTheDocument();
      expect(screen.getByText('Инновации')).toBeInTheDocument();
      expect(screen.getByText('Надёжность')).toBeInTheDocument();
    });

    it('должна отображать описания ценностей', () => {
      render(<AboutPage />);
      expect(screen.getByText(/Быстрая обработка заказов/i)).toBeInTheDocument();
      expect(screen.getByText(/Контроль на всех этапах/i)).toBeInTheDocument();
      expect(screen.getByText(/Современные технологии/i)).toBeInTheDocument();
      expect(screen.getByText(/Гарантия качества на все товары/i)).toBeInTheDocument();
    });

    it('должна иметь responsive grid для ценностей', () => {
      const { container } = render(<AboutPage />);
      // Ищем grid с карточками ценностей
      const grids = container.querySelectorAll('[class*="grid"]');
      const valuesGrid = Array.from(grids).find(grid => grid.className.includes('lg:grid-cols-4'));
      expect(valuesGrid).toBeTruthy();
    });
  });

  describe('Секция статистики', () => {
    it('должна отображать заголовок секции', () => {
      render(<AboutPage />);
      const heading = screen.getByRole('heading', { level: 2, name: /В цифрах/i });
      expect(heading).toBeInTheDocument();
    });

    it('должна отображать 4 счётчика статистики', () => {
      render(<AboutPage />);
      expect(screen.getByText('товаров')).toBeInTheDocument();
      expect(screen.getByText('брендов')).toBeInTheDocument();
      expect(screen.getByText('лет')).toBeInTheDocument();
      expect(screen.getByText('гарантия')).toBeInTheDocument();
    });

    it('должна иметь responsive grid для счётчиков', () => {
      const { container } = render(<AboutPage />);
      const grids = container.querySelectorAll('[class*="grid"]');
      const statsGrid = Array.from(grids).find(grid => grid.className.includes('lg:grid-cols-4'));
      expect(statsGrid).toBeTruthy();
    });
  });

  describe('CTA секция', () => {
    it('должна отображать заголовок CTA', () => {
      render(<AboutPage />);
      expect(
        screen.getByRole('heading', { level: 2, name: /Присоединяйтесь к числу наших партнёров/i })
      ).toBeInTheDocument();
    });

    it('должна отображать кнопку "Стать партнёром"', () => {
      render(<AboutPage />);
      const button = screen.getByText('Стать партнёром');
      expect(button).toBeInTheDocument();
    });

    it('должна иметь ссылку на /register', () => {
      render(<AboutPage />);
      const link = screen.getByText('Стать партнёром').closest('a');
      expect(link).toBeTruthy();
      expect(link).toHaveAttribute('href', '/register');
    });

    it('должна иметь фон primary цвета', () => {
      const { container } = render(<AboutPage />);
      const ctaSection = container.querySelector('.bg-primary');
      expect(ctaSection).toBeInTheDocument();
    });
  });

  describe('SEO Metadata', () => {
    it('должна содержать правильный title', () => {
      expect(metadata.title).toBe('О компании | FREESPORT');
    });

    it('должна содержать правильный description', () => {
      expect(metadata.description).toContain('FREESPORT');
      expect(metadata.description).toContain('федеральный оптовый поставщик');
      expect(metadata.description).toContain('1000 товаров');
      expect(metadata.description).toContain('50+ брендов');
      expect(metadata.description).toContain('10+ лет');
    });

    it('должна содержать OpenGraph метатеги', () => {
      expect(metadata.openGraph).toBeDefined();
      expect(metadata.openGraph?.title).toBe('О компании | FREESPORT');
      expect(metadata.openGraph?.description).toContain('Федеральный оптовый поставщик');
    });
  });

  describe('Адаптивность', () => {
    it('должна иметь responsive контейнеры', () => {
      const { container } = render(<AboutPage />);
      const containers = container.querySelectorAll('.max-w-7xl');
      expect(containers.length).toBeGreaterThan(0);
    });

    it('должна иметь адаптивные padding классы', () => {
      const { container } = render(<AboutPage />);
      const responsiveContainers = container.querySelectorAll('[class*="sm:px-"]');
      expect(responsiveContainers.length).toBeGreaterThan(0);
    });

    it('должна иметь адаптивные размеры текста', () => {
      const { container } = render(<AboutPage />);
      const headings = container.querySelectorAll('[class*="sm:text-"]');
      expect(headings.length).toBeGreaterThan(0);
    });
  });

  describe('Доступность', () => {
    it('должна иметь семантическую разметку с секциями', () => {
      const { container } = render(<AboutPage />);
      const sections = container.querySelectorAll('section');
      expect(sections.length).toBe(5);
    });

    it('должна иметь правильную иерархию заголовков', () => {
      render(<AboutPage />);
      const h1 = screen.getAllByRole('heading', { level: 1 });
      const h2 = screen.getAllByRole('heading', { level: 2 });

      expect(h1.length).toBe(1); // Только один h1
      expect(h2.length).toBeGreaterThan(0); // Несколько h2
    });

    it('должна иметь корректные aria-labels для навигации', () => {
      const { container } = render(<AboutPage />);
      const nav = container.querySelector('nav[aria-label="Breadcrumb"]');
      expect(nav).toBeInTheDocument();
    });
  });

  describe('Структура контента', () => {
    it('должна содержать все обязательные секции в правильном порядке', () => {
      const { container } = render(<AboutPage />);
      const sections = container.querySelectorAll('section');

      // Проверяем наличие текстовых маркеров для каждой секции
      expect(sections[0].textContent).toContain('О компании FREESPORT');
      expect(sections[1].textContent).toContain('Кто мы');
      expect(sections[2].textContent).toContain('Наши ценности');
      expect(sections[3].textContent).toContain('В цифрах');
      expect(sections[4].textContent).toContain('Присоединяйтесь');
    });

    it('должна использовать максимальную ширину для контента', () => {
      const { container } = render(<AboutPage />);
      const maxWidthContainers = container.querySelectorAll('.max-w-7xl, .max-w-3xl');
      expect(maxWidthContainers.length).toBeGreaterThan(0);
    });
  });
});
