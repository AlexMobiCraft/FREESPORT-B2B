/**
 * ReturnsAndSupportNotice Component Tests
 *
 * Story 41.4 — AC1 (условия возврата и канал поддержки),
 * AC8 (доступность: имя секции и осмысленные имена ссылок).
 */

import React from 'react';
import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { ReturnsAndSupportNotice } from '../ReturnsAndSupportNotice';

// Mock next/link — в jsdom нужен обычный <a>
vi.mock('next/link', () => ({
  default: ({ children, href, ...props }: { children: React.ReactNode; href: string }) => (
    <a href={href} {...props}>
      {children}
    </a>
  ),
}));

describe('ReturnsAndSupportNotice', () => {
  it('рендерит блок с data-testid и aria-label секции (AC8)', () => {
    render(<ReturnsAndSupportNotice />);

    const section = screen.getByTestId('returns-support-notice');
    expect(section.tagName).toBe('SECTION');
    expect(section).toHaveAttribute('aria-label', 'Условия возврата и поддержка');
  });

  it('содержит ссылку на условия возврата с точным доступным именем (AC1)', () => {
    render(<ReturnsAndSupportNotice />);

    const link = screen.getByRole('link', { name: 'Условия возврата и рекламаций' });
    expect(link).toHaveAttribute('href', '/partners#returns');
  });

  it('содержит телефон и почту поддержки (AC1)', () => {
    render(<ReturnsAndSupportNotice />);

    const phone = screen.getByRole('link', { name: '+7 968 273-21-68' });
    expect(phone).toHaveAttribute('href', 'tel:+79682732168');

    const email = screen.getByRole('link', { name: 'info@optisport.ru' });
    expect(email).toHaveAttribute('href', 'mailto:info@optisport.ru');
  });

  it('не содержит ни одной ссылки на несуществующий /returns (AC1)', () => {
    render(<ReturnsAndSupportNotice />);

    const hrefs = screen.getAllByRole('link').map(link => link.getAttribute('href'));
    expect(hrefs).toHaveLength(3);
    expect(hrefs.some(href => href === '/returns')).toBe(false);
  });

  it('прокидывает className на корневую секцию', () => {
    render(<ReturnsAndSupportNotice className="text-body-s" />);

    expect(screen.getByTestId('returns-support-notice')).toHaveClass('text-body-s');
  });
});
