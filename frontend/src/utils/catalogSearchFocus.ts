/**
 * Переход из шапки к полю поиска каталога.
 *
 * Раньше шапка вела на `/catalog?focusSearch=true`, и сканер считал этот адрес
 * отдельной страницей-дублем каталога. Теперь ссылка ведёт на фрагмент
 * `/catalog#search`: фрагмент не уходит на сервер и не создаёт нового URL страницы.
 *
 * Одного фрагмента мало. Если посетитель уже на `/catalog`, Next.js считает переход
 * сменой только хэша: компонент каталога не перемонтируется, `useSearchParams`
 * не меняется, а `history.pushState` не порождает `hashchange`. Поэтому ссылка
 * в `onClick` ещё и рассылает событие, по которому смонтированный каталог
 * ставит фокус в поле поиска. При переходе с другой страницы события ловить
 * некому — фокус ставит проверка хэша при монтировании каталога.
 */

/** id элемента поиска на странице каталога — цель прокрутки к фрагменту. */
export const CATALOG_SEARCH_HASH = 'search';

/** Адрес ссылок «Поиск» в шапке. */
export const CATALOG_SEARCH_HREF = `/catalog#${CATALOG_SEARCH_HASH}`;

/** Событие window, по которому каталог фокусирует поле поиска. */
export const CATALOG_SEARCH_FOCUS_EVENT = 'optisport:catalog-search-focus';

/** Просит смонтированный каталог поставить фокус в поле поиска; на сервере ничего не делает. */
export function requestCatalogSearchFocus(): void {
  if (typeof window === 'undefined') return;
  window.dispatchEvent(new Event(CATALOG_SEARCH_FOCUS_EVENT));
}
