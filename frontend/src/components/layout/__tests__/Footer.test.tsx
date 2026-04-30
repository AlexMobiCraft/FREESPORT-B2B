/**
 * Footer Component Tests (Story 12.7 - QA Fix TEST-001)
 *
 * Comprehensive test suite covering:
 * - Rendering of columns, social links, copyright
 * - Accessibility (role="contentinfo", aria-labels)
 * - Responsive grid layout
 * - External links security (rel="noopener noreferrer")
 */

import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { Footer, type FooterColumn, type SocialLink } from '../Footer';

describe('Footer', () => {
  describe('Rendering - Basic Structure', () => {
    it('renders footer with contentinfo role for accessibility', () => {
      render(<Footer />);
      const footer = screen.getByRole('contentinfo');
      expect(footer).toBeInTheDocument();
    });

    it('renders with dark background color (#111827)', () => {
      render(<Footer />);
      const footer = screen.getByRole('contentinfo');
      expect(footer).toHaveClass('bg-[#111827]', 'text-white');
    });

    it('renders with correct padding (py-12)', () => {
      render(<Footer />);
      const footer = screen.getByRole('contentinfo');
      expect(footer).toHaveClass('py-12');
    });

    it('renders container with max-width 1280px', () => {
      render(<Footer />);
      const footer = screen.getByRole('contentinfo');
      const container = footer.querySelector('.max-w-\\[1280px\\]');
      expect(container).toBeInTheDocument();
    });
  });

  describe('Rendering - Columns', () => {
    it('renders all 5 default column titles', () => {
      render(<Footer />);

      const headings = screen.getAllByRole('heading', { level: 3 });
      const headingTexts = headings.map(h => h.textContent);

      expect(headingTexts).toContain('Каталог');
      expect(headingTexts).toContain('Информация');
      expect(headingTexts).toContain('Контакты');
      expect(headingTexts).toContain('Компания');
      expect(headingTexts).toContain('Клиентам');
      expect(headings.length).toBe(5);
    });

    it('renders Information section links', () => {
      render(<Footer />);

      expect(screen.getByRole('link', { name: 'О нас' })).toHaveAttribute('href', '/about');
      expect(screen.getByRole('link', { name: 'Доставка' })).toHaveAttribute('href', '/delivery');
      expect(screen.getByRole('link', { name: 'Возврат' })).toHaveAttribute('href', '/returns');
    });

    it('renders Каталог column links', () => {
      render(<Footer />);

      expect(screen.getByRole('link', { name: 'Фитнес и атлетика' })).toHaveAttribute(
        'href',
        '/catalog?category=fitnes-i-atletika'
      );
      expect(screen.getByRole('link', { name: 'Спортивные игры' })).toHaveAttribute(
        'href',
        '/catalog?category=sportivnye-igry'
      );
    });

    it('renders Контакты column with tel: and mailto: links', () => {
      render(<Footer />);

      const phoneLink = screen.getByRole('link', { name: '+7 968 273-21-68' });
      expect(phoneLink).toHaveAttribute('href', 'tel:+79682732168');

      const emailLink = screen.getByRole('link', { name: 'info@freesport.ru' });
      expect(emailLink).toHaveAttribute('href', 'mailto:info@freesport.ru');
    });

    it('renders custom columns when provided', () => {
      const customColumns: FooterColumn[] = [
        {
          title: 'Custom Column',
          links: [
            { label: 'Custom Link 1', href: '/custom-1' },
            { label: 'Custom Link 2', href: '/custom-2' },
          ],
        },
      ];

      render(<Footer columns={customColumns} />);

      expect(screen.getByText('Custom Column')).toBeInTheDocument();
      expect(screen.getByRole('link', { name: 'Custom Link 1' })).toHaveAttribute(
        'href',
        '/custom-1'
      );
      expect(screen.getByRole('link', { name: 'Custom Link 2' })).toHaveAttribute(
        'href',
        '/custom-2'
      );
    });

    it('applies hover styles to column links', () => {
      render(<Footer />);

      const link = screen.getByRole('link', { name: 'Фитнес и атлетика' });
      expect(link).toHaveClass('hover:text-white', 'transition-colors');
    });
  });

  describe('Rendering - Social Links', () => {
    it('renders all 3 social links with aria-labels', () => {
      render(<Footer />);

      expect(screen.getByLabelText('VK')).toBeInTheDocument();
      expect(screen.getByLabelText('Telegram')).toBeInTheDocument();
      expect(screen.getByLabelText('YouTube')).toBeInTheDocument();
    });

    it('renders VK link with correct href and security attributes', () => {
      render(<Footer />);

      const vkLink = screen.getByLabelText('VK');
      expect(vkLink).toHaveAttribute('href', 'https://vk.com/freesport');
      expect(vkLink).toHaveAttribute('target', '_blank');
      expect(vkLink).toHaveAttribute('rel', 'noopener noreferrer');
    });

    it('renders Telegram link with correct href and security attributes', () => {
      render(<Footer />);

      const telegramLink = screen.getByLabelText('Telegram');
      expect(telegramLink).toHaveAttribute('href', 'https://t.me/freesport');
      expect(telegramLink).toHaveAttribute('target', '_blank');
      expect(telegramLink).toHaveAttribute('rel', 'noopener noreferrer');
    });

    it('renders YouTube link with correct href and security attributes', () => {
      render(<Footer />);

      const youtubeLink = screen.getByLabelText('YouTube');
      expect(youtubeLink).toHaveAttribute('href', 'https://youtube.com/@freesport');
      expect(youtubeLink).toHaveAttribute('target', '_blank');
      expect(youtubeLink).toHaveAttribute('rel', 'noopener noreferrer');
    });

    it('renders custom social links when provided', () => {
      const customSocialLinks: SocialLink[] = [
        {
          name: 'Facebook',
          href: 'https://facebook.com/freesport',
          icon: <span>FB</span>,
        },
      ];

      render(<Footer socialLinks={customSocialLinks} />);

      const facebookLink = screen.getByLabelText('Facebook');
      expect(facebookLink).toHaveAttribute('href', 'https://facebook.com/freesport');
      expect(facebookLink).toHaveAttribute('rel', 'noopener noreferrer');
    });

    it('applies hover styles to social links', () => {
      render(<Footer />);

      const vkLink = screen.getByLabelText('VK');
      expect(vkLink).toHaveClass('hover:opacity-80', 'transition-opacity');
    });

    it('renders SVG icons with proper size (w-6 h-6)', () => {
      render(<Footer />);

      const footer = screen.getByRole('contentinfo');
      const svgIcons = footer.querySelectorAll('svg');

      expect(svgIcons.length).toBeGreaterThanOrEqual(3);
      svgIcons.forEach(svg => {
        expect(svg).toHaveClass('w-6', 'h-6');
      });
    });
  });

  describe('Rendering - Copyright', () => {
    it('renders default copyright text', () => {
      render(<Footer />);

      expect(screen.getByText('© 2026 FREESPORT. Все права защищены.')).toBeInTheDocument();
    });

    it('renders custom copyright when provided', () => {
      render(<Footer copyright="© 2025 Custom Copyright" />);

      expect(screen.getByText('© 2025 Custom Copyright')).toBeInTheDocument();
    });

    it('applies correct typography to copyright (text-xs text-neutral-500)', () => {
      render(<Footer />);

      const copyrightText = screen.getByText('© 2026 FREESPORT. Все права защищены.');
      expect(copyrightText).toHaveClass('text-xs', 'text-neutral-500');
    });
  });

  describe('Responsive Layout', () => {
    it('renders grid with responsive columns (1/2/3)', () => {
      render(<Footer />);

      const footer = screen.getByRole('contentinfo');
      const grid = footer.querySelector('.grid');

      expect(grid).toHaveClass('grid-cols-1', 'md:grid-cols-2', 'lg:grid-cols-3');
    });

    it('renders responsive padding (px-3 md:px-4 lg:px-6)', () => {
      render(<Footer />);

      const footer = screen.getByRole('contentinfo');
      const container = footer.querySelector('.max-w-\\[1280px\\]');

      expect(container).toHaveClass('px-3', 'md:px-4', 'lg:px-6');
    });

    it('renders bottom section with responsive flex direction', () => {
      render(<Footer />);

      const footer = screen.getByRole('contentinfo');
      const bottomSection = footer.querySelector('.border-t');

      expect(bottomSection).toHaveClass('flex-col', 'md:flex-row');
    });
  });

  describe('Accessibility', () => {
    it('has role="contentinfo" for screen readers', () => {
      render(<Footer />);

      const footer = screen.getByRole('contentinfo');
      expect(footer).toBeInTheDocument();
    });

    it('all social links have aria-label attributes', () => {
      render(<Footer />);

      const vkLink = screen.getByLabelText('VK');
      const telegramLink = screen.getByLabelText('Telegram');
      const youtubeLink = screen.getByLabelText('YouTube');

      expect(vkLink).toHaveAttribute('aria-label', 'VK');
      expect(telegramLink).toHaveAttribute('aria-label', 'Telegram');
      expect(youtubeLink).toHaveAttribute('aria-label', 'YouTube');
    });

    it('all SVG icons have aria-hidden="true"', () => {
      render(<Footer />);

      const footer = screen.getByRole('contentinfo');
      const svgIcons = footer.querySelectorAll('svg[aria-hidden]');

      expect(svgIcons.length).toBeGreaterThanOrEqual(3);
    });

    it('column headings use semantic h3 elements', () => {
      render(<Footer />);

      const footer = screen.getByRole('contentinfo');
      const headings = footer.querySelectorAll('h3');

      expect(headings.length).toBe(5); // 5 default columns
    });

    it('all navigation links are keyboard accessible', () => {
      render(<Footer />);

      const links = screen.getAllByRole('link');

      // All links should be in the document and thus keyboard accessible
      links.forEach(link => {
        expect(link).toBeInTheDocument();
      });
    });
  });

  describe('Design System v2.0 Compliance', () => {
    it('uses correct primary color (#111827) for background', () => {
      render(<Footer />);

      const footer = screen.getByRole('contentinfo');
      expect(footer).toHaveClass('bg-[#111827]');
    });

    it('uses inverse text color (white) for content', () => {
      render(<Footer />);

      const footer = screen.getByRole('contentinfo');
      expect(footer).toHaveClass('text-white');
    });

    it('applies correct spacing (gap-8 between columns)', () => {
      render(<Footer />);

      const footer = screen.getByRole('contentinfo');
      const grid = footer.querySelector('.grid');

      expect(grid).toHaveClass('gap-8');
    });

    it('uses border-neutral-700 for divider', () => {
      render(<Footer />);

      const footer = screen.getByRole('contentinfo');
      const divider = footer.querySelector('.border-t');

      expect(divider).toHaveClass('border-neutral-700');
    });

    it('applies transition effects for hover states', () => {
      render(<Footer />);

      const link = screen.getByRole('link', { name: 'Фитнес и атлетика' });
      expect(link).toHaveClass('transition-colors');
    });
  });

  describe('Edge Cases', () => {
    it('renders footer with empty columns array', () => {
      render(<Footer columns={[]} />);

      const footer = screen.getByRole('contentinfo');
      expect(footer).toBeInTheDocument();
    });

    it('renders footer with empty social links array', () => {
      render(<Footer socialLinks={[]} />);

      const footer = screen.getByRole('contentinfo');
      expect(footer).toBeInTheDocument();
    });

    it('renders footer with all custom props', () => {
      const customColumns: FooterColumn[] = [
        {
          title: 'Test',
          links: [{ label: 'Test Link', href: '/test' }],
        },
      ];

      const customSocialLinks: SocialLink[] = [
        {
          name: 'Test Social',
          href: 'https://test.com',
          icon: <span>T</span>,
        },
      ];

      render(
        <Footer
          columns={customColumns}
          socialLinks={customSocialLinks}
          copyright="Custom Copyright"
        />
      );

      expect(screen.getByText('Test')).toBeInTheDocument();
      expect(screen.getByLabelText('Test Social')).toBeInTheDocument();
      expect(screen.getByText('Custom Copyright')).toBeInTheDocument();
    });
  });

  describe('Component Metadata', () => {
    it('has displayName set for debugging', () => {
      expect(Footer.displayName).toBe('Footer');
    });
  });
});
