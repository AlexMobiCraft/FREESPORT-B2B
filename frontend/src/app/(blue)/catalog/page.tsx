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
const FEATURED_BRANDS_FETCH_TIMEOUT_MS = 3000;
const PRODUCTS_FETCH_TIMEOUT_MS = 3000;

// Тот же текст, что клиент показывает в H1 без категории (CatalogPageClient)
const CATALOG_HEADING = 'Каталог';

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

interface FeaturedBrandItem {
  name?: unknown;
  slug?: unknown;
}

interface CategoryInfo {
  name: string;
  /** Нет в ответе — категорию нельзя передать фильтром category_id */
  id: number | null;
}

/** Дерево категорий по slug; null — не загрузилось. Одна загрузка на рендер страницы */
type CategoriesLoader = () => Promise<Map<string, CategoryInfo> | null>;

// Повторяющийся параметр клиент читает через searchParams.get() — первое значение
function readParam(params: CatalogSearchParams, name: string): string | null {
  const value = params[name];
  return (Array.isArray(value) ? value[0] : value) ?? null;
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

// Страница бренда — адрес с единственным параметром brand: строка, непустая после trim,
// без запятой (запятая — мультибренд, его канон /catalog). Любой другой набор параметров
// оставляет прежнюю логику метаданных. Совпадает ли slug с избранным брендом, решает список.
function findCatalogBrandSlug(params: CatalogSearchParams): string | null {
  const keys = Object.keys(params).filter(key => params[key] !== undefined);
  if (keys.length !== 1 || keys[0] !== 'brand') return null;

  const brand = params.brand;
  if (typeof brand !== 'string') return null;

  const slug = brand.trim();
  return slug && !slug.includes(',') ? slug : null;
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

// slug → name избранных брендов: тот же список строит BrandsBlock, ссылки на страницы
// брендов ведут только оттуда. slug берётся как есть — регистр и пробелы не нормализуются.
function collectFeaturedBrands(items: unknown): Map<string, string> | null {
  if (!Array.isArray(items)) return null;

  const brands = new Map<string, string>();
  for (const item of items) {
    if (!item || typeof item !== 'object' || Array.isArray(item)) continue;
    const { slug, name } = item as FeaturedBrandItem;
    if (typeof slug !== 'string' || typeof name !== 'string') continue;

    const brandName = name.trim();
    if (slug && brandName && !brands.has(slug)) brands.set(slug, brandName);
  }
  return brands;
}

// Плоский список без slug в адресе запроса: один ключ кэша Next на все страницы брендов
// (кэшируются только ответы 200), а slug вроде `..` не может изменить путь запроса.
async function fetchFeaturedBrands(): Promise<Map<string, string> | null> {
  const response = await fetch(`${getApiUrl()}/brands/featured/`, {
    next: { revalidate: 3600 },
    signal: AbortSignal.timeout(FEATURED_BRANDS_FETCH_TIMEOUT_MS),
  });
  if (!response.ok) return null;
  return collectFeaturedBrands(await response.json());
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

    const brandSlug = findCatalogBrandSlug(params);
    if (brandSlug) {
      const brandName = (await fetchFeaturedBrands())?.get(brandSlug);
      if (brandName) {
        const path = `/catalog?${new URLSearchParams({ brand: brandSlug }).toString()}`;
        const title = `Спортивные товары ${brandName} оптом | OPTISPORT`;
        const description = `Товары бренда ${brandName} в каталоге OPTISPORT: цены и условия заказа для оптовых покупателей, доставка по России.`;
        return {
          ...buildMetadata({ title, description, path }),
          keywords: null,
        };
      }
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
  params: CatalogSearchParams,
  loadCategories: CategoriesLoader
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

    const get = (name: string) => readParam(params, name);

    if ((get('brand') ?? '').split(',').some(slug => slug.trim())) return null;

    // Клиент сопоставляет slug с деревом без trim — сервер тоже
    const categorySlug = get('category');
    let categoryId: number | null = null;
    if (categorySlug) {
      const categories = await loadCategories();
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

/**
 * Начальный текст H1 для серверного HTML: без него сканер и поисковик видят пустой
 * заголовок, пока клиент грузит дерево категорий. Выбор тот же, что делает клиент после
 * загрузки: название категории из адреса или «Каталог». null — определить не удалось,
 * клиент покажет скелетон, как раньше.
 * В отличие от выдачи, не зависит от cookie и типа навигации: дерево берётся из кеша
 * данных Next, а не из некешируемого запроса.
 */
async function resolveInitialHeading(
  params: CatalogSearchParams,
  loadCategories: CategoriesLoader
): Promise<string | null> {
  // Клиент сопоставляет slug с деревом без trim — сервер тоже; пустой параметр — как его отсутствие
  const slug = readParam(params, 'category');
  if (!slug) return CATALOG_HEADING;

  try {
    const categories = await loadCategories();
    if (!categories) return null;
    return categories.get(slug)?.name ?? CATALOG_HEADING;
  } catch {
    return null;
  }
}

export default async function CatalogPage({ searchParams }: CatalogPageProps) {
  const params = await searchParams;

  // Дерево нужно и выдаче (category_id), и заголовку: одна загрузка на рендер, чтобы при
  // холодном кеше и недоступном бэкенде таймауты не складывались, а запросы не удваивались
  let categoriesRequest: ReturnType<typeof fetchCategories> | undefined;
  const loadCategories: CategoriesLoader = () => (categoriesRequest ??= fetchCategories());

  const [initialProducts, initialHeading] = await Promise.all([
    fetchInitialProducts(params, loadCategories),
    resolveInitialHeading(params, loadCategories),
  ]);
  return <CatalogPageClient initialProducts={initialProducts} initialHeading={initialHeading} />;
}
