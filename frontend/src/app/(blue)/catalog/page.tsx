import type { Metadata } from 'next';

import CatalogPageClient from './CatalogPageClient';
import { buildMetadata } from '@/utils/seo';

const CATEGORY_TREE_FETCH_TIMEOUT_MS = 3000;

const CATALOG_TITLE = 'Каталог спортивных товаров | OPTISPORT';
const CATALOG_DESCRIPTION =
  'Каталог спортивных товаров: фитнес и атлетика, единоборства, спортивные игры, плавание, туризм. Оптовые и розничные цены, доставка по России.';
const CATALOG_KEYWORDS = 'каталог спортивных товаров, спортинвентарь оптом, спортивная экипировка';

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
    const category = params.category;
    if (typeof category !== 'string' || !category.trim()) return buildCatalogMetadata();

    const slug = category.trim();
    const categoryNames = await fetchCategoryNames();
    const name = categoryNames?.get(slug);
    if (!name) return buildCatalogMetadata();

    const query = new URLSearchParams({ category: slug });
    const path = `/catalog?${query.toString()}`;
    const title = `${name} — спортивные товары`;
    const description = `Спортивные товары категории «${name}» в каталоге OPTISPORT: информация о товарах, ценах и условиях заказа для розничных и оптовых покупателей.`;

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
