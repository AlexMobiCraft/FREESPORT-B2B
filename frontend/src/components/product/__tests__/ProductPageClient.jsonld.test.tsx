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
    // Теги из описания в JSON-LD не попадают: только простой текст
    expect(parsed.description).toBe('Описание');
  });

  it('строит offers.url от SITE_URL', () => {
    const { container } = render(<ProductPageClient product={product} userRole="retail" />);
    const script = container.querySelector('script[type="application/ld+json"]')!;

    const parsed = JSON.parse(script.textContent ?? '');
    expect(parsed.offers.url).toBe(`${SITE_URL}/product/evil-product`);
  });

  function renderJsonLd(overrides: Partial<ProductDetailWithVariants>) {
    const { container } = render(
      <ProductPageClient product={{ ...product, ...overrides }} userRole="retail" />
    );
    const script = container.querySelector('script[type="application/ld+json"]')!;
    return JSON.parse(script.textContent ?? '');
  }

  it.each([
    ['Без ТМ', 'bez-tm'],
    ['No Brand', 'no-brand'],
    ['Без бренда', 'bez-brenda'],
    ['', ''],
    ['-', ''],
  ])('не выводит brand для заглушки «%s»', (brand, brand_slug) => {
    const parsed = renderJsonLd({ brand, brand_slug });
    expect(parsed).not.toHaveProperty('brand');
  });

  it('выводит brand для настоящего бренда', () => {
    const parsed = renderJsonLd({ brand: 'BoyBo', brand_slug: 'boybo' });
    expect(parsed.brand).toEqual({ '@type': 'Brand', name: 'BoyBo' });
  });

  it('отдаёт описание простым текстом со схлопнутыми пробелами', () => {
    const parsed = renderJsonLd({ description: 'Материал: NBR<br>Размер:\n183 см &amp; чехол' });
    expect(parsed.description).toBe('Материал: NBR Размер: 183 см & чехол');
  });

  it('экранирует </script>, раскодированный из сущностей описания', () => {
    const html = renderToStaticMarkup(
      <ProductPageClient
        product={{ ...product, name: 'Мяч', description: 'А &lt;/script&gt;&lt;b&gt;Б' }}
        userRole="retail"
      />
    );
    const open = '<script type="application/ld+json">';
    const bodyStart = html.indexOf(open) + open.length;
    const json = html.slice(bodyStart, html.indexOf('</script>', bodyStart));

    expect(json).not.toContain('<');
    expect(JSON.parse(json).description).toBe('А </script><b>Б');
  });

  it('не выводит description, если текста нет', () => {
    const parsed = renderJsonLd({ description: '<br><br>' });
    expect(parsed).not.toHaveProperty('description');
  });

  describe('цена в offers при акции', () => {
    // Розница 1200, акция 800: покупатель видит 800, и поисковикам нужна та же сумма
    const promoProduct: ProductDetailWithVariants = {
      ...product,
      price: { retail: 1200, currency: 'RUB' },
      current_price: '800.00',
      regular_price: '1200.00',
      promo_price: '800.00',
    };

    function jsonLdOfHtml(html: string) {
      const open = '<script type="application/ld+json">';
      const bodyStart = html.indexOf(open) + open.length;
      return JSON.parse(html.slice(bodyStart, html.indexOf('</script>', bodyStart)));
    }

    it('SSR до выбора варианта отдаёт акционную цену', () => {
      const html = renderToStaticMarkup(
        <ProductPageClient product={promoProduct} userRole="retail" />
      );

      expect(jsonLdOfHtml(html).offers.price).toBe(800);
    });

    it('товар без опций после монтирования сохраняет акционную цену', () => {
      // Без размера и цвета родитель не получает начальный onVariantChange: вариант не выбран
      const parsed = renderJsonLd(promoProduct);

      expect(parsed.offers.price).toBe(800);
    });

    it('без акции в offers розничная цена', () => {
      const parsed = renderJsonLd({ ...product, current_price: '1000.00', promo_price: null });

      expect(parsed.offers.price).toBe(1000);
    });
  });

  describe('цена в offers у оптовика без акции (D14-2)', () => {
    // Товар без вариантов: на экране оптовая 700, разметка раньше называла розничные 1200
    const wholesaleProduct: ProductDetailWithVariants = {
      ...product,
      price: { retail: 1200, wholesale: { level1: 700 }, currency: 'RUB' },
      current_price: '700.00',
      regular_price: '700.00',
      promo_price: null,
      variants: [],
    };

    it('SSR отдаёт ролевую цену', () => {
      const html = renderToStaticMarkup(
        <ProductPageClient product={wholesaleProduct} userRole="wholesale_level1" />
      );
      const open = '<script type="application/ld+json">';
      const bodyStart = html.indexOf(open) + open.length;
      const parsed = JSON.parse(html.slice(bodyStart, html.indexOf('</script>', bodyStart)));

      expect(html).toMatch(/700\s*₽/);
      expect(parsed.offers.price).toBe(700);
    });

    it('после монтирования ролевая цена сохраняется', () => {
      const { container } = render(
        <ProductPageClient product={wholesaleProduct} userRole="wholesale_level1" />
      );
      const script = container.querySelector('script[type="application/ld+json"]')!;

      expect(JSON.parse(script.textContent ?? '').offers.price).toBe(700);
    });
  });
});
