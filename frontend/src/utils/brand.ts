/**
 * Бренды-заглушки импорта 1С.
 *
 * Товары без марки импорт привязывает к техническому бренду «Без ТМ»
 * (`IMPORT_FALLBACK_BRAND_SLUG` на бэкенде), раньше — к «No Brand»;
 * на проде есть и «Без бренда». Это не торговая марка: в title и
 * schema.org её выводить нельзя. На фронтенде список держим только здесь —
 * разошедшиеся копии таких списков уже приводили к дефектам (см. deferred-work).
 */
export const PLACEHOLDER_BRAND_SLUGS: ReadonlySet<string> = new Set([
  'bez-tm',
  'bez-brenda',
  'no-brand',
]);

/**
 * Имена тех же заглушек (нижний регистр, пробелы схлопнуты): slug заглушки
 * задаётся настройкой и может отличаться, а имя импорт ищет по «без тм».
 */
const PLACEHOLDER_BRAND_NAMES: ReadonlySet<string> = new Set(['без тм', 'без бренда', 'no brand']);

/**
 * true, если бренда фактически нет: заглушка импорта, пустое имя или «-».
 */
export function isPlaceholderBrand(name: string | null | undefined, slug?: string | null): boolean {
  const normalizedName = (name ?? '').trim().replace(/\s+/g, ' ').toLowerCase();
  if (normalizedName === '' || normalizedName === '-') {
    return true;
  }
  if (PLACEHOLDER_BRAND_NAMES.has(normalizedName)) {
    return true;
  }
  const normalizedSlug = (slug ?? '').trim().toLowerCase();
  return PLACEHOLDER_BRAND_SLUGS.has(normalizedSlug);
}
