import type { Metadata } from 'next';

import CatalogPageClient from './CatalogPageClient';
import { buildMetadata } from '@/utils/seo';

const CATEGORY_TREE_FETCH_TIMEOUT_MS = 3000;

const CATALOG_TITLE = 'Каталог спортивных товаров | OPTISPORT';
const CATALOG_DESCRIPTION =
  'Каталог спортивных товаров: фитнес и атлетика, единоборства, спортивные игры, плавание, туризм. Оптовые и рекомендованные розничные цены, доставка по России.';
const CATALOG_KEYWORDS = 'каталог спортивных товаров, спортинвентарь оптом, спортивная экипировка';

// Подборки — фильтры-переключатели, а не посадочные страницы: canonical остаётся /catalog,
// в sitemap их нет. Собственные title и description снимают дубли с базовым каталогом.
const CATALOG_COLLECTIONS = {
  is_new: {
    title: 'Новинки — каталог спортивных товаров | OPTISPORT',
    description:
      'Новинки в каталоге OPTISPORT: подборка спортивных товаров с ценами и условиями заказа для оптовых покупателей.',
  },
  is_hit: {
    title: 'Лидеры продаж — каталог спортивных товаров | OPTISPORT',
    description:
      'Лидеры продаж в каталоге OPTISPORT: подборка спортивных товаров с ценами и условиями заказа для оптовых покупателей.',
  },
  is_sale: {
    title: 'Скидки — каталог спортивных товаров | OPTISPORT',
    description:
      'Скидки в каталоге OPTISPORT: подборка спортивных товаров со сниженными ценами и условиями заказа для оптовых покупателей.',
  },
} as const;

type CatalogCollectionKey = keyof typeof CATALOG_COLLECTIONS;

type CatalogSearchParams = Record<string, string | string[] | undefined>;

interface CatalogPageProps {
  searchParams: Promise<CatalogSearchParams>;
}

interface CategoryTreeNode {
  name?: unknown;
  slug?: unknown;
  children?: unknown;
}

function getApiUrl(): string {
  if (process.env.INTERNAL_API_URL) return `${process.env.INTERNAL_API_URL}/api/v1`;
  return (
    process.env.NEXT_PUBLIC_API_URL_INTERNAL ||
    process.env.NEXT_PUBLIC_API_URL ||
    'http://backend:8000/api/v1'
  );
}

function buildCatalogMetadata(): Metadata {
  return buildMetadata({
    title: CATALOG_TITLE,
    description: CATALOG_DESCRIPTION,
    keywords: CATALOG_KEYWORDS,
    path: '/catalog',
    image: '/image.jpg',
  });
}

// Подборка — только адрес с единственным параметром is_new, is_hit или is_sale, равным строке 'true'
// (как сравнивает клиент). Любой другой набор параметров оставляет прежнюю логику метаданных.
function findCatalogCollection(params: CatalogSearchParams): CatalogCollectionKey | null {
  const keys = Object.keys(params).filter(key => params[key] !== undefined);
  if (keys.length !== 1) return null;

  const [key] = keys;
  if (!Object.hasOwn(CATALOG_COLLECTIONS, key) || params[key] !== 'true') return null;
  return key as CatalogCollectionKey;
}

function collectCategories(nodes: unknown): Map<string, string> | null {
  if (!Array.isArray(nodes)) return null;

  const categories = new Map<string, string>();
  const visit = (items: unknown[]) => {
    for (const item of items) {
      if (!item || typeof item !== 'object' || Array.isArray(item)) continue;
      const node = item as CategoryTreeNode;
      if (typeof node.slug === 'string' && typeof node.name === 'string') {
        const slug = node.slug.trim();
        const name = node.name.trim();
        if (slug && name && !categories.has(slug)) categories.set(slug, name);
      }
      if (Array.isArray(node.children)) visit(node.children);
    }
  };

  visit(nodes);
  return categories;
}

async function fetchCategoryNames(): Promise<Map<string, string> | null> {
  const response = await fetch(`${getApiUrl()}/categories-tree/`, {
    next: { revalidate: 3600 },
    signal: AbortSignal.timeout(CATEGORY_TREE_FETCH_TIMEOUT_MS),
  });
  if (!response.ok) return null;
  return collectCategories(await response.json());
}

export async function generateMetadata({ searchParams }: CatalogPageProps): Promise<Metadata> {
  try {
    const params = await searchParams;
    const collection = findCatalogCollection(params);
    if (collection) {
      return {
        ...buildMetadata({ ...CATALOG_COLLECTIONS[collection], path: '/catalog' }),
        keywords: null,
      };
    }

    const category = params.category;
    if (typeof category !== 'string' || !category.trim()) return buildCatalogMetadata();

    const slug = category.trim();
    const categoryNames = await fetchCategoryNames();
    const name = categoryNames?.get(slug);
    if (!name) return buildCatalogMetadata();

    const query = new URLSearchParams({ category: slug });
    const path = `/catalog?${query.toString()}`;
    const title = `${name} — спортивные товары`;
    const description = `Товары категории «${name}» в каталоге OPTISPORT: цены и условия заказа для оптовых покупателей.`;

    return {
      ...buildMetadata({ title, description, path }),
      keywords: null,
    };
  } catch {
    return buildCatalogMetadata();
  }
}

export default function CatalogPage() {
  return <CatalogPageClient />;
}
