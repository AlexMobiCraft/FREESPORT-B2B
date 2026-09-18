import type { MetadataRoute } from 'next';

import { absoluteUrl } from '@/utils/seo';

/**
 * sitemap.xml: статические разделы + карточки товаров, статьи блога, новости
 * и CMS-страницы.
 *
 * Данные тянутся напрямую из API внутри Docker-сети, минуя nginx. Любая ошибка
 * запроса не должна ронять весь sitemap — динамический блок просто выпадает,
 * статические маршруты остаются.
 */

export const revalidate = 3600;

const PAGE_SIZE = 1000;
const CATEGORY_TREE_FETCH_TIMEOUT_MS = 3000;
/** Предохранитель от бесконечного обхода пагинации */
const MAX_PAGES = 60;

function getApiUrl(): string {
  if (process.env.INTERNAL_API_URL) return `${process.env.INTERNAL_API_URL}/api/v1`;
  return (
    process.env.NEXT_PUBLIC_API_URL_INTERNAL ||
    process.env.NEXT_PUBLIC_API_URL ||
    'http://backend:8000/api/v1'
  );
}

interface ListItem {
  slug?: unknown;
  updated_at?: unknown;
  published_at?: unknown;
  created_at?: unknown;
}

interface CategoryTreeNode {
  slug?: unknown;
  children?: unknown;
}

function pickLastModified(item: ListItem): Date | undefined {
  const raw = item.updated_at ?? item.published_at ?? item.created_at;
  if (typeof raw !== 'string') return undefined;
  const date = new Date(raw);
  return Number.isNaN(date.getTime()) ? undefined : date;
}

/**
 * Обходит пагинацию DRF и возвращает элементы со строковым `slug`.
 * При ошибке отдаёт то, что успело собраться.
 */
async function fetchAll(endpoint: string): Promise<ListItem[]> {
  const items: ListItem[] = [];

  try {
    for (let page = 1; page <= MAX_PAGES; page += 1) {
      const res = await fetch(`${getApiUrl()}/${endpoint}/?page=${page}&page_size=${PAGE_SIZE}`, {
        next: { revalidate },
      });
      if (!res.ok) break;

      const data = (await res.json()) as { results?: unknown; next?: unknown };
      if (!Array.isArray(data.results)) break;

      items.push(...(data.results as ListItem[]).filter(i => typeof i.slug === 'string'));

      if (!data.next) break;
    }
  } catch {
    // Сеть или API недоступны — отдаём частичный результат
  }

  return items;
}

async function fetchCategorySlugs(): Promise<string[]> {
  try {
    const response = await fetch(`${getApiUrl()}/categories-tree/`, {
      next: { revalidate },
      signal: AbortSignal.timeout(CATEGORY_TREE_FETCH_TIMEOUT_MS),
    });
    if (!response.ok) return [];

    const tree = (await response.json()) as unknown;
    if (!Array.isArray(tree)) return [];

    const slugs = new Set<string>();
    const visit = (nodes: unknown[]) => {
      for (const item of nodes) {
        if (!item || typeof item !== 'object' || Array.isArray(item)) continue;
        const node = item as CategoryTreeNode;
        if (typeof node.slug === 'string' && node.slug.trim()) slugs.add(node.slug.trim());
        if (Array.isArray(node.children)) visit(node.children);
      }
    };
    visit(tree);
    return Array.from(slugs);
  } catch {
    return [];
  }
}

function toCategoryEntries(slugs: string[]): MetadataRoute.Sitemap {
  return slugs.map(slug => ({
    url: absoluteUrl(`/catalog?${new URLSearchParams({ category: slug }).toString()}`),
    changeFrequency: 'weekly',
    priority: 0.7,
  }));
}

function toEntries(
  items: ListItem[],
  prefix: string,
  options: { changeFrequency: MetadataRoute.Sitemap[number]['changeFrequency']; priority: number }
): MetadataRoute.Sitemap {
  return items.map(item => ({
    url: absoluteUrl(`${prefix}/${item.slug as string}`),
    lastModified: pickLastModified(item),
    changeFrequency: options.changeFrequency,
    priority: options.priority,
  }));
}

export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  const now = new Date();

  const staticRoutes: MetadataRoute.Sitemap = (
    [
      { url: absoluteUrl('/home'), changeFrequency: 'daily', priority: 1 },
      { url: absoluteUrl('/catalog'), changeFrequency: 'daily', priority: 0.9 },
      { url: absoluteUrl('/about'), changeFrequency: 'monthly', priority: 0.6 },
      { url: absoluteUrl('/partners'), changeFrequency: 'monthly', priority: 0.7 },
      { url: absoluteUrl('/delivery'), changeFrequency: 'monthly', priority: 0.6 },
      { url: absoluteUrl('/requisites'), changeFrequency: 'yearly', priority: 0.3 },
      { url: absoluteUrl('/blog'), changeFrequency: 'weekly', priority: 0.6 },
      { url: absoluteUrl('/news'), changeFrequency: 'weekly', priority: 0.6 },
    ] satisfies MetadataRoute.Sitemap
  ).map(route => ({ ...route, lastModified: now }));

  const [products, blogPosts, news, pages, categorySlugs] = await Promise.all([
    fetchAll('products'),
    fetchAll('blog'),
    fetchAll('news'),
    fetchAll('pages'),
    fetchCategorySlugs(),
  ]);

  return [
    ...staticRoutes,
    ...toCategoryEntries(categorySlugs),
    ...toEntries(products, '/product', { changeFrequency: 'weekly', priority: 0.8 }),
    ...toEntries(blogPosts, '/blog', { changeFrequency: 'monthly', priority: 0.5 }),
    ...toEntries(news, '/news', { changeFrequency: 'monthly', priority: 0.5 }),
    ...toEntries(pages, '', { changeFrequency: 'yearly', priority: 0.3 }),
  ];
}
