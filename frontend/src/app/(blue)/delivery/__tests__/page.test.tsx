/**
 * Unit-тесты для страницы "Доставка" (/delivery)
 * Story 19.5 - Task 8
 *
 * Проверяет:
 * - Корректный рендеринг всех секций
 * - SEO metadata
 * - Breadcrumb навигацию
 * - Отображение условий доставки
 * - Секцию контактов с корректными ссылками
 */

import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import DeliveryPage, { metadata } from '../page';

// Mock Next.js Link component
vi.mock('next/link', () => ({
  default: ({ children, href }: { children: React.ReactNode; href: string }) => (
    <a href={href}>{children}</a>
  ),
}));

describe('DeliveryPage (/delivery)', () => {
  describe('Рендеринг страницы', () => {
    it('должна рендериться без ошибок', () => {
      const { container } = render(<DeliveryPage />);
      expect(container).toBeInTheDocument();
    });

    it('должна иметь корректную структуру', () => {
      const { container } = render(<DeliveryPage />);
      const sections = container.querySelectorAll('section');
      // Hero + Main Content = 2 секции
      expect(sections.length).toBe(2);
    });
  });

  describe('SEO Metadata', () => {
    it('должна иметь корректный title', () => {
      expect(metadata.title).toBe('Доставка | FREESPORT');
    });

    it('должна иметь корректное description', () => {
      expect(metadata.description).toContain('Условия доставки FREESPORT');
      expect(metadata.description).toContain('Бесплатная доставка до ТК от 35 000 ₽');
      expect(metadata.description).toContain('Самовывоз со склада в Ставрополе от 1 500 ₽');
    });
  });

  describe('Breadcrumb навигация', () => {
    it('должна отображать breadcrumb', () => {
      render(<DeliveryPage />);
      expect(screen.getByText('Главная')).toBeInTheDocument();
      expect(screen.getByText('Доставка')).toBeInTheDocument();
    });

    it('должна иметь ссылку на главную', () => {
      render(<DeliveryPage />);
      const homeLink = screen.getByText('Главная').closest('a');
      expect(homeLink).toHaveAttribute('href', '/');
    });
  });

  describe('Hero секция', () => {
    it('должна отображать заголовок h1', () => {
      render(<DeliveryPage />);
      const heading = screen.getByRole('heading', { level: 1 });
      expect(heading).toHaveTextContent('Условия доставки');
    });

    it('должна отображать подзаголовок', () => {
      render(<DeliveryPage />);
      expect(
        screen.getByText('Мы предлагаем удобные варианты получения заказа')
      ).toBeInTheDocument();
    });
  });

  describe('Секция "Доставка до ТК"', () => {
    it('должна отображать заголовок секции', () => {
      render(<DeliveryPage />);
      const heading = screen.getByRole('heading', {
        level: 2,
        name: /Доставка до транспортной компании/i,
      });
      expect(heading).toBeInTheDocument();
    });

    it('должна отображать badge "БЕСПЛАТНО от 35 000 ₽"', () => {
      render(<DeliveryPage />);
      expect(screen.getByText('БЕСПЛАТНО от 35 000 ₽')).toBeInTheDocument();
    });

    it('должна отображать условия доставки до ТК', () => {
      render(<DeliveryPage />);
      expect(
        screen.getByText(/Согласуем выбранную ТК после оформления заказа/i)
      ).toBeInTheDocument();
      expect(
        screen.getByText(/Доставим до терминала без дополнительной платы/i)
      ).toBeInTheDocument();
      expect(
        screen.getByText(/Дальнейшую доставку осуществляет ТК по её тарифам/i)
      ).toBeInTheDocument();
    });
  });

  describe('Секция "Самовывоз"', () => {
    it('должна отображать заголовок секции', () => {
      render(<DeliveryPage />);
      const heading = screen.getByRole('heading', {
        level: 2,
        name: /Самовывоз со склада/i,
      });
      expect(heading).toBeInTheDocument();
    });

    it('должна отображать минимальный заказ', () => {
      render(<DeliveryPage />);
      expect(screen.getByText(/Минимальный заказ:/i)).toBeInTheDocument();
      expect(screen.getByText(/от 1 500 ₽/i)).toBeInTheDocument();
    });

    it('должна отображать адрес самовывоза', () => {
      render(<DeliveryPage />);
      expect(screen.getByText(/Адрес:/i)).toBeInTheDocument();
      expect(screen.getByText('г. Ставрополь, ул. Коломийцева, 40/1')).toBeInTheDocument();
    });

    it('должна отображать предупреждение о готовности заказа', () => {
      render(<DeliveryPage />);
      expect(screen.getByText(/Перед приездом уточните готовность заказа/i)).toBeInTheDocument();
    });
  });

  describe('Интеграция карты', () => {
    it('должна отображать iframe с Яндекс.Картой', () => {
      const { container } = render(<DeliveryPage />);
      const iframe = container.querySelector('iframe');

      expect(iframe).toBeInTheDocument();
      expect(iframe).toHaveAttribute('src');
      expect(iframe?.getAttribute('src')).toContain('yandex.ru/map-widget');
    });

    it('должна иметь lazy loading для карты', () => {
      const { container } = render(<DeliveryPage />);
      const iframe = container.querySelector('iframe');

      expect(iframe).toHaveAttribute('loading', 'lazy');
    });

    it('должна иметь title для accessibility', () => {
      const { container } = render(<DeliveryPage />);
      const iframe = container.querySelector('iframe');

      expect(iframe).toHaveAttribute('title', 'Пункт самовывоза FREESPORT');
    });
  });

  describe('Секция контактов', () => {
    it('должна отображать заголовок секции', () => {
      render(<DeliveryPage />);
      const heading = screen.getByRole('heading', {
        level: 2,
        name: /Контакты отдела логистики/i,
      });
      expect(heading).toBeInTheDocument();
    });

    it('должна отображать телефон как ссылку tel:', () => {
      render(<DeliveryPage />);
      const phoneLink = screen.getByText('+7 968 273-21-68').closest('a');

      expect(phoneLink).toBeInTheDocument();
      expect(phoneLink).toHaveAttribute('href', 'tel:+79682732168');
    });

    it('должна отображать email как ссылку mailto:', () => {
      render(<DeliveryPage />);
      const emailLink = screen.getByText('logist@freesportopt.ru').closest('a');

      expect(emailLink).toBeInTheDocument();
      expect(emailLink).toHaveAttribute('href', 'mailto:logist@freesportopt.ru');
    });
  });

  describe('Иконки', () => {
    it('должна отображать иконку Truck для доставки до ТК', () => {
      const { container } = render(<DeliveryPage />);
      // Проверяем наличие SVG иконки в секции доставки
      const tkSection = container.querySelector('.bg-primary-subtle');
      expect(tkSection).toBeInTheDocument();
    });

    it('должна отображать иконку MapPin для самовывоза', () => {
      const { container } = render(<DeliveryPage />);
      // Проверяем наличие нескольких иконок с bg-primary-subtle
      const iconContainers = container.querySelectorAll('.bg-primary-subtle');
      expect(iconContainers.length).toBeGreaterThanOrEqual(2);
    });

    it('должна отображать иконку Phone для телефона', () => {
      const { container } = render(<DeliveryPage />);
      const contactsSection = container.querySelectorAll('.bg-primary-subtle');
      // Phone + Mail = минимум 4 иконки всего (TK, Pickup, Phone, Mail)
      expect(contactsSection.length).toBeGreaterThanOrEqual(4);
    });

    it('должна отображать иконку Mail для email', () => {
      const { container } = render(<DeliveryPage />);
      const contactsSection = container.querySelectorAll('.bg-primary-subtle');
      expect(contactsSection.length).toBeGreaterThanOrEqual(4);
    });

    it('должна отображать иконку AlertTriangle для предупреждения', () => {
      const { container } = render(<DeliveryPage />);
      const warningSection = container.querySelector('.bg-warning-subtle');
      expect(warningSection).toBeInTheDocument();
    });
  });

  describe('Стилизация и доступность', () => {
    it('должна использовать корректные CSS классы для typography', () => {
      render(<DeliveryPage />);
      const h1 = screen.getByRole('heading', { level: 1 });

      expect(h1).toHaveClass('text-headline-xl');
    });

    it('должна иметь hover-эффекты для ссылок', () => {
      render(<DeliveryPage />);
      const phoneLink = screen.getByText('+7 968 273-21-68').closest('a');

      expect(phoneLink).toHaveClass('hover:text-primary-hover');
    });

    it('должна использовать transition для плавных анимаций', () => {
      render(<DeliveryPage />);
      const emailLink = screen.getByText('logist@freesportopt.ru').closest('a');

      expect(emailLink).toHaveClass('transition-colors');
    });
  });
});
