import { describe, expect, it } from 'vitest';

import {
  PAGE_SIZE,
  PRICE_MAX,
  PRICE_MIN,
  buildInitialProductFilters,
  parseSearchFilter,
  productFiltersKey,
} from '../catalogQuery';

const reader = (query: string) => {
  const params = new URLSearchParams(query);
  return (name: string) => params.get(name);
};

describe('buildInitialProductFilters', () => {
  it('для пустого адреса собирает фильтры по умолчанию, как клиент', () => {
    expect(buildInitialProductFilters(reader(''), null)).toEqual({
      page: 1,
      page_size: PAGE_SIZE,
      ordering: 'name',
      min_price: PRICE_MIN,
      max_price: PRICE_MAX,
      in_stock: true,
    });
  });

  it('разбирает страницу, сортировку, цену, подборки, наличие и поиск', () => {
    const filters = buildInitialProductFilters(
      reader(
        'page=3&ordering=-created_at&min_price=1000&max_price=9000&is_new=true&is_hit=1&in_stock=false&search=%20мяч%20'
      ),
      42
    );

    expect(filters).toEqual({
      page: 3,
      page_size: PAGE_SIZE,
      ordering: '-created_at',
      min_price: 1000,
      max_price: 9000,
      is_new: true,
      category_id: 42,
      search: 'мяч',
    });
  });

  it('мусор в параметрах заменяет умолчаниями тех же парсеров', () => {
    const filters = buildInitialProductFilters(
      reader('page=abc&ordering=price&min_price=9000&max_price=1000&search=a'),
      null
    );

    expect(filters).toMatchObject({ page: 1, ordering: 'name', min_price: 1, max_price: 50000 });
    expect(filters).not.toHaveProperty('search');
    expect(filters).not.toHaveProperty('category_id');
  });
});

describe('parseSearchFilter', () => {
  it('отдаёт поиск только от двух символов после trim', () => {
    expect(parseSearchFilter(null)).toBe('');
    expect(parseSearchFilter(' a ')).toBe('');
    expect(parseSearchFilter(' ab ')).toBe('ab');
  });
});

describe('productFiltersKey', () => {
  it('не зависит от порядка полей и отбрасывает undefined', () => {
    const a = productFiltersKey({ page: 1, ordering: 'name', is_new: undefined, in_stock: true });
    const b = productFiltersKey({ in_stock: true, ordering: 'name', page: 1 });

    expect(a).toBe(b);
  });

  it('различает разные значения', () => {
    expect(productFiltersKey({ page: 1 })).not.toBe(productFiltersKey({ page: 2 }));
    expect(productFiltersKey({ category_id: 5 })).not.toBe(productFiltersKey({}));
  });
});
