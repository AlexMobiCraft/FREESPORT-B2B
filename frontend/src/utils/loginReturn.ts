/**
 * Точка возврата после входа (Story 41.18, решение D3).
 *
 * Гость, попавший на `/login` с защищённого маршрута или по приглашению на
 * `/checkout`, приходит на адрес без query-параметров, а цель лежит в
 * короткоживущей cookie с `Path=/login`. Страница входа читает её на сервере
 * (из JS после клиентской навигации Chromium её не показывает), при открытии
 * переносит значение в свою память и сразу удаляет cookie (сценарий S8).
 *
 * Модуль исполняется и в edge-runtime `middleware.ts`, и в браузере, поэтому
 * на уровне модуля к `document`/`window` не обращаемся: браузерные функции
 * проверяют наличие `document` внутри себя.
 *
 * Cookie не `HttpOnly`: её читает клиентская страница входа. Значение —
 * несекретный путь, и при каждом использовании он проходит `isSafeRedirectUrl`.
 */

import { isSafeRedirectUrl } from './urlUtils';

export const LOGIN_RETURN_COOKIE = 'loginReturnTo';
export const LOGIN_RETURN_COOKIE_PATH = '/login';
export const LOGIN_RETURN_COOKIE_MAX_AGE = 600;

/**
 * Атрибуты cookie — одна точка правды для middleware и клиента.
 * `Secure` решается по `NODE_ENV`, а не по протоколу запроса: за nginx Next
 * видит `http`, и на проде `Secure` иначе не проставился бы.
 */
export function loginReturnCookieOptions() {
  return {
    path: LOGIN_RETURN_COOKIE_PATH,
    maxAge: LOGIN_RETURN_COOKIE_MAX_AGE,
    sameSite: 'lax' as const,
    secure: process.env.NODE_ENV === 'production',
    httpOnly: false,
  };
}

/**
 * Адрес перехода после входа: первый безопасный из кандидата URL
 * (`next || redirect` целиком — опасный непустой `next` не уступает место
 * `redirect`, семантика 41.12) и cookie точки возврата, иначе `/`.
 */
export function resolvePostLoginTarget(
  urlCandidate: string | null | undefined,
  cookieCandidate: string | null | undefined
): string {
  for (const candidate of [urlCandidate, cookieCandidate]) {
    if (isSafeRedirectUrl(candidate)) return candidate as string;
  }
  return '/';
}

/** Пишет цель в cookie точки возврата; небезопасный путь не записывается. */
export function writeLoginReturnCookie(path: string): void {
  if (typeof document === 'undefined') return;
  if (!isSafeRedirectUrl(path)) return;

  const { secure } = loginReturnCookieOptions();
  document.cookie =
    `${LOGIN_RETURN_COOKIE}=${encodeURIComponent(path)}; Path=${LOGIN_RETURN_COOKIE_PATH}; ` +
    `Max-Age=${LOGIN_RETURN_COOKIE_MAX_AGE}; SameSite=Lax${secure ? '; Secure' : ''}`;
}

/** Значение cookie точки возврата или `null` (нет cookie, пусто или битое значение). */
export function readLoginReturnCookie(): string | null {
  if (typeof document === 'undefined') return null;

  const prefix = `${LOGIN_RETURN_COOKIE}=`;
  const raw = document.cookie
    .split(';')
    .map(part => part.trim())
    .find(part => part.startsWith(prefix));
  if (!raw) return null;

  try {
    return decodeURIComponent(raw.slice(prefix.length)) || null;
  } catch {
    return null;
  }
}

/**
 * Удаляет cookie точки возврата. Пишутся и `Max-Age=0`, и `Expires` в прошлом:
 * happy-dom не удаляет cookie по одному `Max-Age=0`, браузеры — по любому.
 */
export function clearLoginReturnCookie(): void {
  if (typeof document === 'undefined') return;

  document.cookie =
    `${LOGIN_RETURN_COOKIE}=; Path=${LOGIN_RETURN_COOKIE_PATH}; Max-Age=0; ` +
    'Expires=Thu, 01 Jan 1970 00:00:00 GMT';
}
