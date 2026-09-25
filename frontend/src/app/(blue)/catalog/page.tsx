import type { Metadata } from 'next';
import { cookies, headers } from 'next/headers';

import CatalogPageClient from './CatalogPageClient';
import {
  buildInitialProductFilters,
  productFiltersKey,
  type CatalogInitialProducts,
} from './catalogQuery';
import { buildMetadata } from '@/utils/seo';

const CATEGORY_TREE_FETCH_TIMEOUT_MS = 3000;
const PRODUCTS_FETCH_TIMEOUT_MS = 3000;

const CATALOG_TITLE = 'Каталог спортивных товаров | OPTISPORT';
const CATALOG_DESCRIPTION =
  'Каталог спортивных товаров: фитнес и атлетика, единоборства, спортивные игры, плавание, туризм. Оптовые и рекомендованные розничные цены, доставка по России.';
const CATALOG_KEYWORDS = 'каталог спортивных товаров, спортинвентарь оптом, спортивная экипировка';

// Подборки — самостоятельные страницы каталога со своим canonical /catalog?<ключ>=true;
// непустые попадают в sitemap (41.22, пересмотр D1). Собственные title и description
// снимают дубли с базовым каталогом.
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
  id?: unknown;
  name?: unknown;
  slug?: unknown;
  children?: unknown;
}

interface CategoryInfo {
  name: string;
  /** Нет в ответе — категорию нельзя передать фильтром category_id */
  id: number | null;
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

function collectCategories(nodes: unknown): Map<string, CategoryInfo> | null {
  if (!Array.isArray(nodes)) return null;

  const categories = new Map<string, CategoryInfo>();
  const visit = (items: unknown[]) => {
    for (const item of items) {
      if (!item || typeof item !== 'object' || Array.isArray(item)) continue;
      const node = item as CategoryTreeNode;
      if (typeof node.slug === 'string' && typeof node.name === 'string') {
        const slug = node.slug.trim();
        const name = node.name.trim();
        const id = Number.isSafeInteger(node.id) ? (node.id as number) : null;
        if (slug && name && !categories.has(slug)) categories.set(slug, { name, id });
      }
      if (Array.isArray(node.children)) visit(node.children);
    }
  };

  visit(nodes);
  return categories;
}

async function fetchCategories(): Promise<Map<string, CategoryInfo> | null> {
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
      const path = `/catalog?${new URLSearchParams({ [collection]: 'true' }).toString()}`;
      return {
        ...buildMetadata({ ...CATALOG_COLLECTIONS[collection], path }),
        keywords: null,
      };
    }

    const category = params.category;
    if (typeof category !== 'string' || !category.trim()) return buildCatalogMetadata();

    const slug = category.trim();
    const categories = await fetchCategories();
    const name = categories?.get(slug)?.name;
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

/**
 * Первая страница выдачи для серверного HTML: без неё поисковик видит каталог
 * без единого товара. Запрос анонимный, поэтому при сохранённой сессии не
 * выполняется — вошедшему оптовику нужны цены его роли, их загрузит клиент.
 * Ссылки с брендом не рендерятся: их slug'и разрешает справочник брендов.
 * Любой сбой возвращает null — клиент загрузит выдачу сам, как раньше.
 */
async function fetchInitialProducts(
  params: CatalogSearchParams
): Promise<CatalogInitialProducts | null> {
  try {
    // Клиентская навигация (router.push фильтров, переход по ссылке, префетч)
    // тоже выполняет динамическую страницу заново. Клиент такую выдачу не
    // берёт — он уже смонтирован или грузит её сам, — а запрос удвоил бы
    // нагрузку на бэкенд и задержал бы смену фильтра. Заголовок RSC Next
    // из headers() вырезает, поэтому признак — Sec-Fetch-Dest: его ставит
    // браузер, у документа он `document`, у fetch роутера — `empty`. У ботов
    // заголовка нет — им выдача и нужна.
    const headerStore = await headers();
    const fetchDest = headerStore.get('sec-fetch-dest');
    if (fetchDest && fetchDest !== 'document') return null;

    const cookieStore = await cookies();
    if (cookieStore.get('refreshToken')?.value) return null;

    // Повторяющийся параметр клиент читает через searchParams.get() — первое значение
    const get = (name: string): string | null => {
      const value = params[name];
      return (Array.isArray(value) ? value[0] : value) ?? null;
    };

    if ((get('brand') ?? '').split(',').some(slug => slug.trim())) return null;

    // Клиент сопоставляет slug с деревом без trim — сервер тоже
    const categorySlug = get('category');
    let categoryId: number | null = null;
    if (categorySlug) {
      const categories = await fetchCategories();
      // Дерево не загрузилось — клиент выдачу по категории всё равно запросит сам
      if (!categories) return null;
      const category = categories.get(categorySlug);
      if (category && category.id === null) return null;
      categoryId = category?.id ?? null;
    }

    const filters = buildInitialProductFilters(get, categoryId);
    const query = new URLSearchParams(
      Object.entries(filters)
        .filter(([, value]) => value !== undefined)
        .map(([key, value]) => [key, String(value)])
    );
    const response = await fetch(`${getApiUrl()}/products/?${query.toString()}`, {
      cache: 'no-store',
      signal: AbortSignal.timeout(PRODUCTS_FETCH_TIMEOUT_MS),
    });
    if (!response.ok) return null;

    const data: unknown = await response.json();
    if (!data || typeof data !== 'object') return null;
    const { count, results } = data as { count?: unknown; results?: unknown };
    if (typeof count !== 'number' || !Array.isArray(results)) return null;

    return { key: productFiltersKey(filters), token: crypto.randomUUID(), count, results };
  } catch {
    return null;
  }
}

export default async function CatalogPage({ searchParams }: CatalogPageProps) {
  const initialProducts = await fetchInitialProducts(await searchParams);
  return <CatalogPageClient initialProducts={initialProducts} />;
}
