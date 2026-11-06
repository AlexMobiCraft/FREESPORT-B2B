/**
 * Общие константы визуального редактора админки.
 *
 * Ограничения картинок повторяют серверные (`apps/common/rich_editor.py`):
 * проверка здесь только экономит сотруднику время на заведомо отклонённую загрузку,
 * решает всё равно сервер.
 */

export const IMAGE_TYPES = ['image/jpeg', 'image/png', 'image/webp', 'image/gif'] as const;

export const MAX_IMAGE_BYTES = 10 * 1024 * 1024;

export const IMAGE_ALIGNMENTS = ['left', 'center', 'right'] as const;

export type ImageAlignment = (typeof IMAGE_ALIGNMENTS)[number];

/**
 * Ширина картинки хранится в `width` у `img` в пикселях; высота не хранится —
 * на сайте и в редакторе `height: auto`, пропорции сохраняются.
 * 1920 px — длинная сторона, до которой сервер уменьшает загруженные картинки.
 */
export const IMAGE_MIN_WIDTH = 48;
export const IMAGE_MAX_WIDTH = 1920;

/** Доли колонки текста для кнопок «25% / 50% / 75%». */
export const IMAGE_SIZE_PRESETS = [0.25, 0.5, 0.75] as const;

/**
 * Ширина колонки текста на сайте, px: в новостях и статьях блога это `max-w-4xl`
 * (896 px) без боковых отступов `lg:px-8`. Для страниц задаётся виджетом
 * (`data-column-width`): у них колонка шире, см. `RichContentAdminMixin`.
 */
export const DEFAULT_COLUMN_WIDTH = 832;

/** Атрибут узла загрузки: такой элемент не попадает ни в textarea, ни в режим HTML. */
export const UPLOAD_MARKER = 'data-rich-upload';

export const HTML_MODE_HINT =
  'Правка исходного кода. При возврате в визуальный режим то, чего нет в тулбаре ' +
  '(div, span, стили, id, заголовки h1, h5, h6), будет удалено или упрощено';

export const MESSAGES = {
  wrongType: 'Поддерживаются картинки JPEG, PNG, WEBP и GIF.',
  tooLarge: 'Картинка больше 10 МБ — уменьшите её и загрузите снова.',
  network: 'Нет связи с сервером, картинка не загружена. Попробуйте ещё раз.',
  session: 'Сессия истекла: войдите в админку заново и повторите загрузку.',
  // 403 даёт и устаревший CSRF-токен (повторный вход в другой вкладке).
  forbidden:
    'Нет права загружать картинки в этот раздел или страница устарела — обновите её и повторите.',
  failed: 'Не удалось загрузить картинку',
  waitForUpload: 'Дождитесь окончания загрузки картинки, затем сохраните.',
  badLink: 'Ссылка должна начинаться с https://, http://, mailto: или / (страница этого сайта).',
} as const;

/**
 * Ссылки, которые пропускает редактор: `http`, `https`, `mailto` и пути этого сайта.
 *
 * Белый список санитайзера на сервере шире, но редактор сам создаёт только эти
 * ссылки: `//host` — чужой сайт без протокола, `#якорь` схема не держит (у заголовков нет `id`).
 */
export function isAllowedHref(url: string | null | undefined): boolean {
  if (!url) {
    return false;
  }
  const value = url.trim();
  return isSitePath(value) || /^(?:https?:\/\/|mailto:)/i.test(value);
}

/** Путь этого сайта: `/…`, но не `//host` (чужой сайт без протокола). */
export function isSitePath(url: string | null | undefined): boolean {
  return /^\/(?!\/)/.test((url ?? '').trim());
}

/**
 * Ширина из атрибута `width`: целые пиксели (`400`, `400px`). Проценты и мусор — `null`,
 * слишком большое значение обрезается до `IMAGE_MAX_WIDTH`.
 */
export function parseImageWidth(value: string | null | undefined): number | null {
  const match = /^\s*(\d{1,5})\s*(?:px)?\s*$/i.exec(value ?? '');
  if (!match) {
    return null;
  }
  const width = Number(match[1]);
  return width >= 1 ? Math.min(width, IMAGE_MAX_WIDTH) : null;
}

/**
 * Допустимая ширина при изменении размера: не меньше `IMAGE_MIN_WIDTH` и не больше
 * оригинала (`naturalWidth`; пока он неизвестен — `IMAGE_MAX_WIDTH`): растянутая
 * сверх оригинала картинка на сайте выглядит размытой.
 */
export function clampImageWidth(width: number, naturalWidth = 0): number {
  const limit = naturalWidth > 0 ? Math.min(naturalWidth, IMAGE_MAX_WIDTH) : IMAGE_MAX_WIDTH;
  return Math.round(Math.min(Math.max(width, IMAGE_MIN_WIDTH), limit));
}

/** Ширина колонки из `data-column-width`; без значения — колонка новостей. */
export function parseColumnWidth(value: string | undefined): number {
  const width = Number(value);
  return Number.isInteger(width) && width >= 320 && width <= 3000 ? width : DEFAULT_COLUMN_WIDTH;
}

/** Источник картинки: `http(s)://` или путь сайта; `file:`, `cid:`, `data:`, `blob:` — нет. */
export function isAllowedImageSrc(src: string | null | undefined): boolean {
  const value = (src ?? '').trim();
  return isSitePath(value) || /^https?:\/\//i.test(value);
}
