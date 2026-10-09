/**
 * Unit-тесты для страницы отписки от рассылки (/unsubscribe)
 *
 * Проверяет:
 * - Разметку в стиле (blue)-страниц: breadcrumb, h1, карточка
 * - Отсутствие собственного <main> (его рендерит LayoutWrapper)
 * - SEO metadata (noindex, no-referrer)
 */

import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import UnsubscribePage, { metadata } from '../page';

vi.mock('next/link', () => ({
  default: ({ children, href }: { children: React.ReactNode; href: string }) => (
    <a href={href}>{children}</a>
  ),
}));

vi.mock('../UnsubscribeClient', () => ({
  default: () => <div data-testid="unsubscribe-client" />,
}));

describe('UnsubscribePage (/unsubscribe)', () => {
  it('рендерит breadcrumb «Главная / Отписка от рассылки»', () => {
    render(<UnsubscribePage />);
    expect(screen.getByText('Главная')).toBeInTheDocument();
    expect(
      screen.getByText('Отписка от рассылки', { selector: '[aria-current="page"]' })
    ).toBeInTheDocument();
    expect(screen.getByText('Главная').closest('a')).toHaveAttribute('href', '/');
  });

  it('рендерит h1, связанный с секцией через aria-labelledby', () => {
    const { container } = render(<UnsubscribePage />);
    const h1 = screen.getByRole('heading', { level: 1 });
    expect(h1).toHaveTextContent('Отписка от маркетинговой рассылки');
    expect(h1).toHaveAttribute('id', 'unsubscribe-title');
    expect(container.querySelector('section')).toHaveAttribute(
      'aria-labelledby',
      'unsubscribe-title'
    );
  });

  it('не рендерит собственный <main> — landmark выдаёт LayoutWrapper', () => {
    const { container } = render(<UnsubscribePage />);
    expect(container.querySelectorAll('main').length).toBe(0);
  });

  it('использует контейнер и карточку дизайн-системы', () => {
    const { container } = render(<UnsubscribePage />);
    expect(container.querySelector('.max-w-\\[1280px\\]')).toBeInTheDocument();
    expect(container.querySelector('section')?.className).toContain('bg-white');
    expect(container.querySelector('section')?.className).toContain(
      'shadow-[var(--shadow-default)]'
    );
  });

  it('SEO: noindex и no-referrer', () => {
    expect(metadata.title).toBe('Отписка от рассылки | OPTISPORT');
    expect(metadata.robots).toEqual({ index: false, follow: false });
    expect(metadata.referrer).toBe('no-referrer');
  });
});
