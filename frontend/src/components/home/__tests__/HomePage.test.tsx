/**
 * HomePage integration test — section order and BrandsBlock integration
 */

import { describe, it, expect, vi } from 'vitest';
import { render } from '@testing-library/react';
import { HomePage } from '../HomePage';
import type { Brand } from '@/types/api';

// Mock all section components as simple divs with data-testid
vi.mock('../HeroSection', () => ({ default: () => <div data-testid="hero-section" /> }));
vi.mock('../QuickLinksSection', () => ({ QuickLinksSection: () => <div data-testid="quick-links-section" /> }));
vi.mock('../MarketingBannersSection', () => ({ MarketingBannersSection: () => <div data-testid="marketing-banners-section" /> }));
vi.mock('../CategoriesSection', () => ({ CategoriesSection: () => <div data-testid="categories-section" /> }));
vi.mock('../HitsSection', () => ({ HitsSection: () => <div data-testid="hits-section" /> }));
vi.mock('../NewArrivalsSection', () => ({ NewArrivalsSection: () => <div data-testid="new-arrivals-section" /> }));
vi.mock('../PromoSection', () => ({ PromoSection: () => <div data-testid="promo-section" /> }));
vi.mock('../SaleSection', () => ({ SaleSection: () => <div data-testid="sale-section" /> }));
vi.mock('../NewsSection', () => ({ NewsSection: () => <div data-testid="news-section" /> }));
vi.mock('../BlogSection', () => ({ BlogSection: () => <div data-testid="blog-section" /> }));
vi.mock('../SubscribeNewsSection', () => ({ SubscribeNewsSection: () => <div data-testid="subscribe-section" /> }));
vi.mock('../WhyFreesportSection', () => ({ WhyFreesportSection: () => <div data-testid="why-section" /> }));
vi.mock('../DeliveryTeaser', () => ({ DeliveryTeaser: () => <div data-testid="delivery-section" /> }));
vi.mock('../AboutTeaser', () => ({ AboutTeaser: () => <div data-testid="about-section" /> }));
vi.mock('@/components/business/home/BrandsBlock', () => ({
  BrandsBlock: ({ brands }: { brands: Brand[] }) => (
    <div data-testid="brands-block" data-brands-count={brands.length} />
  ),
}));

const mockBrands: Brand[] = [
  { id: 1, name: 'Nike', slug: 'nike', image: '/media/brands/nike.png', description: null, website: null, is_featured: true },
  { id: 2, name: 'Adidas', slug: 'adidas', image: '/media/brands/adidas.png', description: null, website: null, is_featured: true },
];

describe('HomePage', () => {
  it('AC1: MarketingBannersSection рендерится между QuickLinksSection и CategoriesSection', () => {
    const { container } = render(<HomePage featuredBrands={mockBrands} />);

    const sections = container.querySelectorAll('[data-testid]');
    const testIds = Array.from(sections).map(el => el.getAttribute('data-testid'));

    const quickLinksIdx = testIds.indexOf('quick-links-section');
    const marketingIdx = testIds.indexOf('marketing-banners-section');
    const categoriesIdx = testIds.indexOf('categories-section');

    expect(quickLinksIdx).toBeGreaterThan(-1);
    expect(marketingIdx).toBeGreaterThan(-1);
    expect(categoriesIdx).toBeGreaterThan(-1);

    expect(marketingIdx).toBe(quickLinksIdx + 1);
  });

  it('AC2: BrandsBlock рендерится сразу после MarketingBannersSection', () => {
    const { container } = render(<HomePage featuredBrands={mockBrands} />);

    const sections = container.querySelectorAll('[data-testid]');
    const testIds = Array.from(sections).map(el => el.getAttribute('data-testid'));

    const marketingIdx = testIds.indexOf('marketing-banners-section');
    const brandsIdx = testIds.indexOf('brands-block');

    expect(marketingIdx).toBeGreaterThan(-1);
    expect(brandsIdx).toBeGreaterThan(-1);
    expect(brandsIdx).toBe(marketingIdx + 1);
  });

  it('AC5: передаёт featuredBrands в BrandsBlock', () => {
    const { container } = render(<HomePage featuredBrands={mockBrands} />);

    const brandsBlock = container.querySelector('[data-testid="brands-block"]');
    expect(brandsBlock).toBeInTheDocument();
    expect(brandsBlock?.getAttribute('data-brands-count')).toBe('2');
  });

  it('не рендерит BrandsBlock при пустом массиве', () => {
    const { container } = render(<HomePage featuredBrands={[]} />);

    const brandsBlock = container.querySelector('[data-testid="brands-block"]');
    expect(brandsBlock).not.toBeInTheDocument();
  });

  it('рендерит все секции главной страницы в правильном порядке', () => {
    const { container } = render(<HomePage featuredBrands={mockBrands} />);

    const expectedSections = [
      'hero-section',
      'quick-links-section',
      'marketing-banners-section',
      'brands-block',
      'categories-section',
      'about-section',
      'hits-section',
      'new-arrivals-section',
      'promo-section',
      'sale-section',
      'news-section',
      'why-section',
      'subscribe-section',
      'delivery-section',
    ];

    const sections = container.querySelectorAll('[data-testid]');
    const testIds = Array.from(sections).map(el => el.getAttribute('data-testid'));

    // Проверка наличия и порядка
    for (const testId of expectedSections) {
      expect(container.querySelector(`[data-testid="${testId}"]`)).toBeInTheDocument();
    }

    // Проверка порядка (необязательно для всех, но полезно для тех, что перемещали)
    expect(testIds.indexOf('about-section')).toBe(testIds.indexOf('categories-section') + 1);
    expect(testIds.indexOf('why-section')).toBe(testIds.indexOf('news-section') + 1);
    expect(testIds).not.toContain('blog-section');
  });
});
