/**
 * Разметка schema.org `Product` на странице товара.
 *
 * Закрепляет две вещи:
 *  1. данные товара из 1С не могут закрыть `<script>`: литеральный `</script>`
 *     в названии или описании при SSR выносил остаток JSON в документ как HTML;
 *  2. `offers.url` строится от `SITE_URL`, как весь остальной SEO-код, а не от
 *     захардкоженного домена.
 */

import { describe, it, expect, vi } from 'vitest';
import { render } from '@testing-library/react';
import { renderToStaticMarkup } from 'react-dom/server';

import ProductPageClient from '../ProductPageClient';
import type { ProductDetailWithVariants } from '../ProductSummary';
import { SITE_URL } from '@/utils/seo';

vi.mock('@/components/ui/Toast', () => ({
  useToast: () => ({ success: vi.fn(), error: vi.fn() }),
}));

const PAYLOAD = '</script><img src=x onerror=alert(1)>';

const product: ProductDetailWithVariants = {
  id: 1,
  slug: 'evil-product',
  name: `Мяч ${PAYLOAD}`,
  sku: 'EVIL',
  article: 'EVIL-1',
  brand: 'Brand',
  description: `Описание ${PAYLOAD}`,
  price: { retail: 1000, currency: 'RUB' },
  stock_quantity: 1,
  images: [],
  category: { id: 1, name: 'Мячи', slug: 'balls', breadcrumbs: [] },
  is_in_stock: true,
  can_be_ordered: true,
  variants: [],
};

describe('ProductPageClient JSON-LD', () => {
  it('не даёт данным товара закрыть script-тег при SSR', () => {
    const html = renderToStaticMarkup(<ProductPageClient product={product} userRole="retail" />);

    const start = html.indexOf('<script type="application/ld+json">');
    expect(start).toBeGreaterThanOrEqual(0);
    const bodyStart = start + '<script type="application/ld+json">'.length;
    const end = html.indexOf('</script>', bodyStart);

    // Первый `</script>` после открытия — родной закрывающий тег, а не данные товара
    const json = html.slice(bodyStart, end);
    expect(json).not.toContain('<');
    expect(json).toContain('\\u003c/script>');
    expect(html).not.toContain('<img src=x');

    const parsed = JSON.parse(json);
    expect(parsed.name).toBe(product.name);
    expect(parsed.description).toBe(product.description);
  });

  it('строит offers.url от SITE_URL', () => {
    const { container } = render(<ProductPageClient product={product} userRole="retail" />);
    const script = container.querySelector('script[type="application/ld+json"]')!;

    const parsed = JSON.parse(script.textContent ?? '');
    expect(parsed.offers.url).toBe(`${SITE_URL}/product/evil-product`);
  });
});
