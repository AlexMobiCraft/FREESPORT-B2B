/**
 * Unit-тесты для страницы «Политика обработки персональных данных» (/privacy-policy).
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import PrivacyPolicyPage, { generateMetadata } from '../page';

const { mockNotFound } = vi.hoisted(() => ({
  mockNotFound: vi.fn(() => {
    throw new Error('NEXT_NOT_FOUND');
  }),
}));

vi.mock('next/navigation', () => ({
  notFound: mockNotFound,
}));

vi.mock('next/link', () => ({
  default: ({ children, href }: { children: React.ReactNode; href: string }) => (
    <a href={href}>{children}</a>
  ),
}));

const mockPage = {
  id: 1,
  title: 'Политика обработки персональных данных',
  slug: 'privacy-policy',
  content: '<p>Текст политики с <strong>HTML</strong>.</p>',
  seo_title: 'Политика ПДн | FREESPORT',
  seo_description: 'Правила обработки персональных данных FREESPORT',
  is_published: true,
  created_at: '2026-05-09T10:00:00Z',
  updated_at: '2026-05-09T10:00:00Z',
};

function mockFetch(response: Response) {
  vi.spyOn(globalThis, 'fetch').mockResolvedValue(response);
}

describe('PrivacyPolicyPage (/privacy-policy)', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('запрашивает страницу политики через Pages API с ISR revalidate 3600', async () => {
    mockFetch(Response.json(mockPage));

    render(await PrivacyPolicyPage());

    expect(fetch).toHaveBeenCalledWith(
      'http://localhost:8001/api/v1/pages/privacy-policy/',
      { next: { revalidate: 3600 } }
    );
  });

  it('рендерит заголовок страницы из API', async () => {
    mockFetch(Response.json(mockPage));

    render(await PrivacyPolicyPage());

    expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent(
      'Политика обработки персональных данных'
    );
  });

  it('рендерит HTML-контент из API', async () => {
    mockFetch(Response.json(mockPage));

    const { container } = render(await PrivacyPolicyPage());
    const content = container.querySelector('.prose');

    expect(content?.innerHTML).toContain('<strong>HTML</strong>');
  });

  it('извлекает только содержимое <body> при полном HTML-документе', async () => {
    const fullHtmlPage = {
      ...mockPage,
      content: '<html><head><style>.red{color:red}</style></head><body><p>Текст политики</p></body></html>',
    };
    mockFetch(Response.json(fullHtmlPage));

    const { container } = render(await PrivacyPolicyPage());
    const content = container.querySelector('.prose');

    expect(content?.innerHTML).toContain('<p>Текст политики</p>');
    expect(content?.innerHTML).not.toContain('<html>');
    expect(content?.innerHTML).not.toContain('<head>');
    expect(content?.innerHTML).not.toContain('<style>');
  });

  it('рендерит breadcrumb', async () => {
    mockFetch(Response.json(mockPage));

    render(await PrivacyPolicyPage());

    expect(screen.getByText('Главная')).toBeInTheDocument();
    expect(screen.getAllByText('Политика обработки персональных данных').length).toBeGreaterThan(0);
    expect(screen.getByText('Главная').closest('a')).toHaveAttribute('href', '/');
  });

  it('вызывает notFound при 404 от API', async () => {
    mockFetch(new Response(null, { status: 404 }));

    await expect(PrivacyPolicyPage()).rejects.toThrow('NEXT_NOT_FOUND');
    expect(mockNotFound).toHaveBeenCalled();
  });

  it('пробрасывает 500 от API в error boundary вместо 404', async () => {
    mockFetch(new Response('Server error', { status: 500 }));

    await expect(PrivacyPolicyPage()).rejects.toThrow(
      'Не удалось загрузить страницу политики ПДн'
    );
    expect(mockNotFound).not.toHaveBeenCalled();
  });

  it('вызывает notFound при сетевой ошибке', async () => {
    vi.spyOn(globalThis, 'fetch').mockRejectedValue(new Error('Network timeout'));

    await expect(PrivacyPolicyPage()).rejects.toThrow('NEXT_NOT_FOUND');
    expect(mockNotFound).toHaveBeenCalled();
  });

  it('вызывает notFound при malformed JSON от API', async () => {
    mockFetch(new Response('not-json', { status: 200 }));

    await expect(PrivacyPolicyPage()).rejects.toThrow('NEXT_NOT_FOUND');
    expect(mockNotFound).toHaveBeenCalled();
  });

  it('вызывает notFound при пустом content', async () => {
    mockFetch(Response.json({ ...mockPage, content: null }));

    await expect(PrivacyPolicyPage()).rejects.toThrow('NEXT_NOT_FOUND');
    expect(mockNotFound).toHaveBeenCalled();
  });

  it('вызывает notFound при отсутствующем title', async () => {
    mockFetch(Response.json({ ...mockPage, title: undefined }));

    await expect(PrivacyPolicyPage()).rejects.toThrow('NEXT_NOT_FOUND');
    expect(mockNotFound).toHaveBeenCalled();
  });

  it('генерирует metadata из SEO-полей страницы', async () => {
    mockFetch(Response.json(mockPage));

    const metadata = await generateMetadata();

    expect(metadata.title).toBe('Политика ПДн | FREESPORT');
    expect(metadata.description).toBe('Правила обработки персональных данных FREESPORT');
  });
});
