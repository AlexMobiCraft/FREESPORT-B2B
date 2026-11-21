/**
 * SSR-страница товара: сессия покупателя доходит до запроса товара.
 *
 * У акционного товара API отдаёт цены по роли: розница 1200, опт 700, акция 800. Клиент платит
 * меньшую из цен, поэтому оптовику `current_price` = 700 и акция не применена, гостю — 800 с
 * зачёркнутой 1200. Если страница не передаст Cookie в запрос товара, оптовик получит гостевой
 * ответ и увидит акцию 800 вместо своей цены 700.
 *
 * Тест вызывает настоящий `ProductPage` и настоящий `productsService`; ответ MSW зависит
 * от заголовка Cookie, поэтому потеря заголовка на любом из шагов цепочки ломает проверки.
 * Окружение node, как у серверного рендера: в happy-dom XHR срезает запрещённый заголовок Cookie.
 *
 * @vitest-environment node
 */

import { Children, isValidElement, type ReactElement, type ReactNode } from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { describe, it, expect, vi } from 'vitest';
import { http, HttpResponse } from 'msw';
import { cookies } from 'next/headers';
import { server } from '@/__mocks__/api/server';
import type { ProductDetail } from '@/types/api';
import type { UserRole } from '@/utils/pricing';

vi.mock('next/headers', () => ({
  cookies: vi.fn(),
}));

vi.mock('next/navigation', () => ({
  notFound: vi.fn(() => {
    throw new Error('NEXT_NOT_FOUND');
  }),
}));

vi.mock('@/stores/authStore', () => ({
  useAuthStore: Object.assign(vi.fn(), {
    getState: () => ({
      accessToken: null,
      refreshToken: null,
    }),
  }),
}));

vi.mock('@/utils/server-auth', () => ({
  getUserRole: vi.fn(),
}));

vi.mock('@/components/product/ProductBreadcrumbs', () => ({ default: () => null }));
vi.mock('@/components/product/ProductPageClient', () => ({ default: () => null }));

import ProductPage from '../page';
import ProductInfo from '@/components/product/ProductInfo';
import ProductPageClient from '@/components/product/ProductPageClient';
import { getUserRole } from '@/utils/server-auth';

const API_BASE_URL = 'http://localhost:8001/api/v1';
const WHOLESALE_SESSION = 'wholesale-session';

const rawPromoProduct = (currentPrice: string, regularPrice: string) => ({
  id: 301,
  slug: 'promo-product',
  name: 'Товар с акцией',
  brand: { id: 1, name: 'Бренд', slug: 'brand' },
  category: { id: 1, name: 'Категория', slug: 'category' },
  description: 'Описание',
  retail_price: 1200,
  current_price: currentPrice,
  regular_price: regularPrice,
  promo_price: '800.00',
  stock_quantity: 5,
  is_in_stock: true,
  can_be_ordered: true,
  variants: [],
});

/** API отдаёт оптовику его цену 700 (она ниже акции), а запросу без сессии — акцию 800 при рознице 1200. */
function serveProductByCookie() {
  server.use(
    http.get(`${API_BASE_URL}/products/:slug/`, ({ request }) => {
      const cookie = request.headers.get('cookie') ?? '';
      const isWholesale = cookie.includes(`sessionid=${WHOLESALE_SESSION}`);
      return HttpResponse.json(
        isWholesale ? rawPromoProduct('700.00', '700.00') : rawPromoProduct('800.00', '1200.00')
      );
    })
  );
}

function openSession(sessionId: string | null) {
  vi.mocked(cookies).mockResolvedValue({
    get: (name: string) => (name === 'sessionid' && sessionId ? { value: sessionId } : undefined),
  } as unknown as Awaited<ReturnType<typeof cookies>>);
}

type ClientProps = { product: ProductDetail; userRole: UserRole };

/** Ищет в дереве элементов страницы элемент заданного компонента. */
function findElement(node: ReactNode, type: unknown): ReactElement<ClientProps> | null {
  if (!isValidElement(node)) return null;
  if (node.type === type) return node as ReactElement<ClientProps>;
  const { children } = node.props as { children?: ReactNode };
  for (const child of Children.toArray(children)) {
    const found = findElement(child, type);
    if (found) return found;
  }
  return null;
}

/** Товар и роль, которые серверная страница передала клиентской части. */
async function propsPassedToClient(): Promise<ClientProps> {
  const element = await ProductPage({ params: Promise.resolve({ slug: 'promo-product' }) });
  const client = findElement(element, ProductPageClient);
  expect(client).not.toBeNull();
  const { product, userRole } = (client as ReactElement<ClientProps>).props;
  return { product, userRole };
}

describe('Product Detail Page - сессия в запросе акционного товара', () => {
  it('оптовик платит свою цену ниже акции, и страница выглядит как без акции', async () => {
    serveProductByCookie();
    openSession(WHOLESALE_SESSION);
    vi.mocked(getUserRole).mockResolvedValue('wholesale_level1');

    const { product, userRole } = await propsPassedToClient();

    expect(userRole).toBe('wholesale_level1');
    expect(product.current_price).toBe('700.00');
    expect(product.promo_price).toBe('800.00');

    const html = renderToStaticMarkup(<ProductInfo product={product} userRole={userRole} />);
    expect(html).toMatch(/700\s₽/);
    expect(html).not.toMatch(/800\s₽/);
    expect(html).not.toContain('Акция');
    expect(html).not.toContain('Акционная цена');
    expect(html).not.toContain('data-testid="promo-price"');
    expect(html).not.toContain('data-testid="regular-price"');
  });

  it('гость без сессии платит акцию и видит зачёркнутую розницу', async () => {
    serveProductByCookie();
    openSession(null);
    vi.mocked(getUserRole).mockResolvedValue('guest');

    const { product, userRole } = await propsPassedToClient();

    expect(userRole).toBe('guest');
    expect(product.current_price).toBe('800.00');
    expect(product.regular_price).toBe('1200.00');

    const html = renderToStaticMarkup(<ProductInfo product={product} userRole={userRole} />);
    expect(html).toContain('Акция');
    expect(html).toMatch(/data-testid="promo-price"[^>]*>.*?800\s₽/);
    expect(html).toMatch(/data-testid="regular-price"[^>]*>.*?1\s200\s₽/);
  });
});
