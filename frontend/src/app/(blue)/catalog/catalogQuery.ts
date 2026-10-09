/**
 * Разбор адресной строки каталога — общий для серверной страницы и клиента.
 *
 * Сервер по этим же правилам загружает первую страницу выдачи, а клиент
 * сравнивает с её ключом свой первый запрос. Два независимых разбора
 * разъехались бы между собой, и серверная выдача молча перестала бы
 * использоваться.
 */

import type { ProductFilters } from '@/services/productsService';
import type { PaginatedResponse, Product } from '@/types/api';

export type PriceRange = {
  min: number;
  max: number;
};

export const PRICE_MIN = 1;
export const PRICE_MAX = 50000;
export const DEFAULT_PRICE_RANGE: PriceRange = { min: PRICE_MIN, max: PRICE_MAX };
export const PAGE_SIZE = 12;
export const DEFAULT_ORDERING = 'name';

/**
 * Разбирает query-параметр `page`. Всё, что не является строкой из одних цифр
 * (`abc`, `3abc`, `1e3`, `2.9`, `-1`, пустая строка), и всё вне безопасного
 * диапазона трактуется как первая страница — каталог не должен падать на кривой ссылке.
 */
export const parsePageNumber = (value: string | null): number => {
  if (!value || !/^\d+$/.test(value)) {
    return 1;
  }
  const page = Number(value);
  return Number.isSafeInteger(page) && page >= 1 ? page : 1;
};

/** Белый список значений <select> сортировки: всё остальное — сортировка по умолчанию */
const ORDERING_OPTIONS: readonly string[] = [
  '-created_at',
  'min_retail_price',
  '-min_retail_price',
  'name',
  '-name',
];

/** Мусор в `?ordering=` не должен уезжать в запрос — страница молча берёт умолчание */
export const parseOrdering = (value: string | null): string =>
  value && ORDERING_OPTIONS.includes(value) ? value : DEFAULT_ORDERING;

/**
 * Один конец диапазона цены. Всё, что не является целым числом в
 * [PRICE_MIN, PRICE_MAX], заменяется умолчанием СВОЕГО конца. Clamp запрещён:
 * бэкенд отрицательное значение и так игнорирует, а зажатие `max_price=-5`
 * к PRICE_MIN дало бы пользователю пустую выдачу вместо всего каталога.
 */
const parsePriceBound = (value: string | null, fallback: number): number => {
  if (!value || !/^\d+$/.test(value)) {
    return fallback;
  }
  const parsed = Number(value);
  return Number.isSafeInteger(parsed) && parsed >= PRICE_MIN && parsed <= PRICE_MAX
    ? parsed
    : fallback;
};

/**
 * Разбор пары концов диапазона одним правилом, а не двумя независимыми:
 * инвертированный диапазон (`?min_price=9000&max_price=1000`) сбрасывает ОБА
 * конца к умолчаниям — ни swap, ни подтягивание одного конца к другому, иначе
 * пользователь не поймёт, почему выдача не соответствует ссылке.
 * Правило идемпотентно, поэтому канонизация URL не зациклится.
 */
export const parsePriceRange = (minParam: string | null, maxParam: string | null): PriceRange => {
  const min = parsePriceBound(minParam, PRICE_MIN);
  const max = parsePriceBound(maxParam, PRICE_MAX);
  return min > max ? DEFAULT_PRICE_RANGE : { min, max };
};

/** `in_stock` живёт в URL только выключенным: умолчание фильтра — «в наличии» */
export const parseInStock = (value: string | null): boolean => value !== 'false';

/** Поиск уходит в запрос только от двух символов — та же граница, что у поля поиска */
export const parseSearchFilter = (value: string | null): string => {
  const trimmed = (value ?? '').trim();
  return trimmed.length >= 2 ? trimmed : '';
};

/** Первая страница выдачи, загруженная на сервере, и ключ фильтров, по которым она получена */
export type CatalogInitialProducts = Pick<PaginatedResponse<Product>, 'count' | 'results'> & {
  key: string;
  /**
   * Уникален для каждого серверного запроса. «Назад» восстанавливает страницу
   * из кэша роутера с той же выдачей — по токену клиент узнаёт уже
   * использованную и не показывает её повторно без запроса.
   */
  token: string;
};

/** Доступ к параметру адреса одинаковый для URLSearchParams и серверных searchParams */
type ParamReader = (name: string) => string | null;

/**
 * Фильтры первого запроса товаров для состояния, прочитанного из адреса.
 * Повторяет сборку `productFilters` в клиенте: расхождение лишь отключает
 * повторное использование серверной выдачи, но не ломает страницу.
 * Бренд не поддержан: его slug'и разрешает справочник, и такие ссылки
 * сервер не рендерит вовсе.
 */
export const buildInitialProductFilters = (
  get: ParamReader,
  categoryId: number | null
): ProductFilters => {
  const price = parsePriceRange(get('min_price'), get('max_price'));
  const filters: ProductFilters = {
    page: parsePageNumber(get('page')),
    page_size: PAGE_SIZE,
    ordering: parseOrdering(get('ordering')),
    min_price: price.min,
    max_price: price.max,
  };

  (['is_new', 'is_hit', 'is_sale'] as const).forEach(badge => {
    if (get(badge) === 'true') filters[badge] = true;
  });

  if (categoryId) filters.category_id = categoryId;
  if (parseInStock(get('in_stock'))) filters.in_stock = true;

  const search = parseSearchFilter(get('search'));
  if (search) filters.search = search;

  return filters;
};

/**
 * Стабильный ключ фильтров: поля по алфавиту, `undefined` отброшены — как их
 * отбрасывает и axios при сборке query. Порядок, в котором поля добавлялись в
 * объект, на ключ не влияет.
 */
export const productFiltersKey = (filters: ProductFilters): string =>
  JSON.stringify(
    Object.entries(filters)
      .filter(([, value]) => value !== undefined)
      .sort(([a], [b]) => (a < b ? -1 : a > b ? 1 : 0))
  );
