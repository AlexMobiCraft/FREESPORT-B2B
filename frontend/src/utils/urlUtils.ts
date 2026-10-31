/**
 * Единая проверка допустимости redirect-цели после входа.
 * Предотвращает Open Redirect и циклы клиентских/middleware-редиректов.
 *
 * Модуль исполняется и в edge-runtime `middleware.ts`, поэтому обращаться к
 * `location`/`window` нельзя — базой для WHATWG-разбора служит фиксированный
 * внутренний origin.
 *
 * Цель отклоняется по трём причинам:
 * 1. обратный слэш в декодированном runtime-значении: WHATWG-нормализация
 *    превращает `/\evil.com` в `//evil.com` — внешний адрес;
 * 2. адрес не является внутренним: другой origin или неоднозначный WHATWG URL
 *    (`//evil.com`, `https://evil.com`, `javascript:…`, пустое/относительное);
 * 3. внутренний auth-route (`/login`, `/register`, `/b2b-register`,
 *    `/password-reset`) непригоден как конечная точка после аутентификации:
 *    `/login` даёт self-redirect и вечный spinner, остальные немедленно
 *    перенаправляются middleware.
 *
 * @param url Проверяемый адрес (значение query-параметра `next`/`redirect`)
 * @returns true, если адрес безопасен для внутреннего перехода
 */

/** Фактические auth-route приложения (см. `middleware.ts`). */
const AUTH_ROUTE_BASES = ['/login', '/register', '/b2b-register', '/password-reset'] as const;

/** Внутренняя база для WHATWG-разбора — без DOM-зависимостей (edge-runtime). */
const SAFE_REDIRECT_ORIGIN = 'https://optisport.invalid';

export function isSafeRedirectUrl(url: string | null | undefined): boolean {
  if (!url) return false;
  if (!url.startsWith('/')) return false;

  // Отклоняем обратный слэш до разбора: `/\\evil.com` нормализуется в `//evil.com`.
  if (url.includes('\\')) return false;

  let parsed: URL;
  try {
    parsed = new URL(url, SAFE_REDIRECT_ORIGIN);
  } catch {
    return false;
  }

  if (parsed.origin !== SAFE_REDIRECT_ORIGIN) return false;

  // Auth-route и его дочерние пути (с границей сегмента) — недопустимая цель.
  // `/login-foo` намеренно не отклоняется: это deferred-дефект вне scope стори.
  return !AUTH_ROUTE_BASES.some(
    base => parsed.pathname === base || parsed.pathname.startsWith(`${base}/`)
  );
}
