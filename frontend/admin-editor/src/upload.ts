/**
 * Загрузка картинки на сервер: `POST <data-upload-url>` с полем `image`.
 */

import { IMAGE_TYPES, MAX_IMAGE_BYTES, MESSAGES } from './constants';

export class UploadError extends Error {}

/** Проверка до отправки; `null` — файл можно отправлять. */
export function validateImageFile(file: File): string | null {
  // Пустой тип (бывает при перетаскивании в Windows) — формат определит сервер.
  if (file.type !== '' && !(IMAGE_TYPES as readonly string[]).includes(file.type)) {
    return MESSAGES.wrongType;
  }
  if (file.size > MAX_IMAGE_BYTES) {
    return MESSAGES.tooLarge;
  }
  return null;
}

function readError(data: unknown): string | null {
  if (data && typeof data === 'object' && 'error' in data) {
    const { error } = data as { error: unknown };
    return typeof error === 'string' && error ? error : null;
  }
  return null;
}

function readUrl(data: unknown): string | null {
  if (data && typeof data === 'object' && 'url' in data) {
    const { url } = data as { url: unknown };
    // Сервер отдаёт относительный путь /media/…; другое в текст не вставляем.
    return typeof url === 'string' && /^\/(?!\/)/.test(url) ? url : null;
  }
  return null;
}

/** Возвращает URL сохранённой картинки или бросает `UploadError` с текстом для сотрудника. */
export async function uploadImage(
  uploadUrl: string,
  file: File,
  csrfToken: string
): Promise<string> {
  const body = new FormData();
  body.append('csrfmiddlewaretoken', csrfToken);
  body.append('image', file);

  let response: Response;
  try {
    response = await fetch(uploadUrl, {
      method: 'POST',
      body,
      credentials: 'same-origin',
      // 302 на страницу входа — не успех: иначе fetch молча пошёл бы за ним.
      redirect: 'manual',
      headers: { 'X-CSRFToken': csrfToken },
    });
  } catch {
    throw new UploadError(MESSAGES.network);
  }

  if (response.type === 'opaqueredirect' || (response.status >= 300 && response.status < 400)) {
    throw new UploadError(MESSAGES.session);
  }
  if (response.status === 403) {
    throw new UploadError(MESSAGES.forbidden);
  }

  let data: unknown = null;
  try {
    data = await response.json();
  } catch {
    data = null;
  }

  const url = response.ok ? readUrl(data) : null;
  if (url) {
    return url;
  }
  throw new UploadError(readError(data) ?? `${MESSAGES.failed} (код ответа ${response.status}).`);
}
