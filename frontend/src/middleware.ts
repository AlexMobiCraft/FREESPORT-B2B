/**
 * Next.js Middleware - защита маршрутов и настоящий HTTP 404
 *
 * Edge Runtime - совместимый код (только Web APIs)
 * Проверяет authenticated routes и редиректит неавторизованных пользователей на /login.
 * Дополнительно возвращает настоящий 404 на несуществующие адреса верхнего уровня:
 * App Router фиксирует статус до вызова notFound(), а middleware выполняется
 * до стриминга и статус вернуть может.
 */

import { NextResponse } from 'next/server';
import type { NextRequest } from 'next/server';
import { isSafeRedirectUrl } from '@/utils/urlUtils';

/**
 * Односегментные маршруты, которые обслуживает сам Next.js.
 *
 * Список сверяется с фактической структурой `src/app` тест-стражем
 * `src/__tests__/app-routes-allowlist.test.ts`: добавил страницу верхнего уровня —
 * добавь её сюда, иначе она начнёт отдавать 404.
 *
 * `electric-orange` страницей НЕ является: это rewrite на статику
 * `public/electric-orange/index.html` (`next.config.ts`). Rewrites из
 * `next.config.ts` (afterFiles) выполняются ПОСЛЕ middleware, поэтому без записи
 * здесь рабочий адрес превратится в 404. Не удалять как «лишний».
 *
 * `/product`, `/orders` и `/b2b-dashboard` сюда намеренно не входят — страниц под
 * такими путями нет.
 */
export const KNOWN_TOP_LEVEL_ROUTES: ReadonlySet<string> = new Set([
  'about',
  'b2b-register',
  'blog',
  'cart',
  'catalog',
  'checkout',
  'coming-soon',
  'delivery',
  'design-comparison',
  'electric',
  'electric-orange',
  'electric-orange-test',
  'examples',
  'home',
  'login',
  'news',
  'partners',
  'password-reset',
  'privacy-policy',
  'profile',
  'register',
  'requisites',
  'search',
  'test',
]);

/**
 * Время жизни кэша списка опубликованных CMS-слагов.
 *
 * Нижняя граница задаётся ценой промаха: каждый промах — сетевой запрос на пути
 * HTML-ответа. Верхняя — требованием видимости: вновь опубликованная в админке
 * страница обязана открыться «не позднее TTL», и ждать час редактор не должен.
 * Пять минут дают ~12 запросов в час независимо от трафика.
 */
const SLUG_CACHE_TTL_MS = 5 * 60 * 1000;

/** Предельное время ожидания списка слагов: недоступный backend не должен подвешивать сайт */
const SLUGS_FETCH_TIMEOUT_MS = 2000;

/**
 * Размер страницы выдачи: DRF по умолчанию отдаёт 20 записей, этого мало.
 *
 * Это же значение — ПОДДЕРЖИВАЕМЫЙ ПРЕДЕЛ числа опубликованных CMS-страниц
 * (решение владельца по находке ревью). Оно совпадает с `max_page_size`
 * пагинации на бэкенде (`PagesPagination`, `backend/apps/pages/views.py`), и
 * менять его нужно в обоих местах сразу. За пределом выдача обрезается
 * пагинацией, список перестаёт считаться полным, и middleware навсегда уходит
 * в fail-open: настоящие 404 просто исчезают. Чтобы деградация не была
 * молчаливой, приближение к пределу логируется (см. SLUGS_COUNT_WARN_THRESHOLD).
 */
const SLUGS_PAGE_SIZE = 1000;

/**
 * Порог предупреждения о приближении к пределу (90 % от него).
 *
 * Предупреждение выводится ЗАРАНЕЕ: после пересечения предела 404 пропадут
 * сами собой, и заметить это можно будет только по отсутствию статуса, а не по
 * ошибке. Девяти сотен страниц достаточно, чтобы успеть выбрать решение
 * (облегчённый endpoint слагов либо обход всей пагинации).
 */
const SLUGS_COUNT_WARN_THRESHOLD = Math.floor(SLUGS_PAGE_SIZE * 0.9);

/**
 * Пауза после неудачной попытки получить список слагов.
 *
 * Пока backend лежит, каждый запрос к неизвестному адресу платил полный таймаут
 * и создавал новый запрос к API. Пауза убирает и то и другое: 30 секунд после
 * отказа middleware отвечает «не знаю» сразу и в сеть не ходит, оставаясь при
 * этом в fail-open (запрос идёт дальше, 404 не отдаётся). Тридцать секунд —
 * компромисс: заметно короче TTL кэша, поэтому поднявшийся backend возвращает
 * настоящие 404 почти сразу, но достаточно долго, чтобы не долбить лежащий сервис.
 */
const SLUGS_FAILURE_BACKOFF_MS = 30 * 1000;

interface SlugCache {
  slugs: Set<string>;
  fetchedAt: number;
}

/** Кэш в памяти модуля: middleware не имеет доступа к Data Cache Next.js */
let slugCache: SlugCache | null = null;

/** Текущий запрос за списком — схлопывает параллельные промахи кэша в один вызов API */
let inflightSlugsRequest: Promise<Set<string> | null> | null = null;

/** Момент последней неудачи запроса к API — начало паузы (см. SLUGS_FAILURE_BACKOFF_MS) */
let slugsFailedAt: number | null = null;

/**
 * Базовый URL API для запроса из middleware.
 *
 * ВАЖНО: в edge-бандл middleware переменные подставляются на этапе СБОРКИ, и
 * попадают туда только `NEXT_PUBLIC_*`. Поэтому `INTERNAL_API_URL`, с которого
 * начинают цепочку серверные компоненты (`app/sitemap.ts`, `(blue)/[slug]/page.tsx`),
 * здесь неприменим — в собранном middleware он будет undefined.
 *
 * Первым звеном стоит ВЫДЕЛЕННАЯ переменная `NEXT_PUBLIC_MIDDLEWARE_API_URL`, и
 * это не косметика. Подстановка на этапе сборки действует не только на
 * middleware: `process.env.NEXT_PUBLIC_*` инлайнится во весь код, включая
 * серверные компоненты. Общий `NEXT_PUBLIC_API_URL_INTERNAL`, переданный в
 * сборку прода, переключил бы на внутренний `http://backend:8000` и страницы
 * `/oferta`, `/privacy-policy` — а они, в отличие от запроса ниже, не шлют
 * `X-Forwarded-Proto: https`, и при штатном `SECURE_SSL_REDIRECT=True` backend
 * увёл бы их в `https://backend:8000`, где TLS нет. Собственная переменная
 * оставляет остальному фронтенду прежний источник API.
 *
 * `NEXT_PUBLIC_API_URL_INTERNAL` остаётся вторым звеном для dev-контейнера:
 * там middleware компилируется на лету и читает окружение в runtime
 * (`docker/docker-compose.yml`), а build-arg не участвует.
 */
function getApiBaseUrl(): string {
  const base =
    process.env.NEXT_PUBLIC_MIDDLEWARE_API_URL ||
    process.env.NEXT_PUBLIC_API_URL_INTERNAL ||
    process.env.NEXT_PUBLIC_API_URL ||
    'http://backend:8000/api/v1';

  // Завершающий слэш в переменной окружения даёт путь `.../api/v1//pages/`,
  // которого backend не обслуживает: middleware ушёл бы в постоянный fail-open
  // и перестал бы отдавать 404 вообще — молча, только с записями в логе.
  return base.replace(/\/+$/, '');
}

/**
 * Забирает список опубликованных CMS-слагов.
 * Возвращает `null`, если список получить не удалось — вызывающий обязан
 * трактовать это как «не знаю» и пропустить запрос дальше (fail-open).
 */
async function fetchPublishedSlugs(): Promise<Set<string> | null> {
  const url = `${getApiBaseUrl()}/pages/?page_size=${SLUGS_PAGE_SIZE}`;

  try {
    const res = await fetch(url, {
      signal: AbortSignal.timeout(SLUGS_FETCH_TIMEOUT_MS),
      // На проде у backend включён SECURE_SSL_REDIRECT, а доверенный признак
      // протокола он берёт из SECURE_PROXY_SSL_HEADER (X-Forwarded-Proto).
      // Без этого заголовка внутренний http://backend:8000 отвечает редиректом
      // на https://backend:8000, где TLS нет: запрос падал бы по таймауту, и
      // стори тихо выродилась бы в вечный fail-open — 404 не вернулся бы никогда.
      headers: { 'X-Forwarded-Proto': 'https' },
      // Молча идти за редиректом нельзя: это скрыло бы саму проблему за
      // двухсекундным таймаутом вместо внятной записи в логе.
      redirect: 'manual',
    });

    if (
      res.redirected ||
      res.type === 'opaqueredirect' ||
      (res.status >= 300 && res.status < 400)
    ) {
      console.warn(
        `[middleware] Запрос списка CMS-слагов уехал в редирект (HTTP ${res.status}): ` +
          'проверь SECURE_SSL_REDIRECT и SECURE_PROXY_SSL_HEADER на backend'
      );
      return null;
    }

    if (!res.ok) {
      console.warn(`[middleware] Список CMS-слагов недоступен: HTTP ${res.status}`);
      return null;
    }

    const data = (await res.json()) as { results?: unknown; count?: unknown; next?: unknown };

    if (!Array.isArray(data.results)) {
      console.warn('[middleware] Ответ со списком CMS-слагов не разобрался');
      return null;
    }

    // Выдача, обрезанная пагинацией, полным списком не является: непопавшие в
    // неё страницы получили бы 404. Полнота обязана подтверждаться ОБОИМИ
    // признаками DRF — ссылкой на следующую страницу и общим числом записей.
    // Отсутствие любого из них означает неизвестную форму ответа, а не полный
    // список: молча принять её за allowlist — значит вернуть ложные 404.
    if (!('next' in data)) {
      console.warn('[middleware] В ответе нет признака завершённой пагинации (next)');
      return null;
    }

    // DRF кладёт в `next` строку-URL следующей страницы либо null. Проверка на
    // «истинность» тут слишком мягкая: `false`, `0` и пустая строка сошли бы за
    // признак полного списка, хотя это ответ неизвестной формы. Принимаем
    // только явный null — остальное уводит в fail-open.
    if (data.next !== null) {
      const reason =
        typeof data.next === 'string'
          ? `обрезан пагинацией — опубликованных страниц больше поддерживаемого предела ${SLUGS_PAGE_SIZE}, ` +
            'настоящие 404 отдаваться перестанут: нужен облегчённый endpoint слагов или обход всей пагинации'
          : `признак next неизвестной формы (${JSON.stringify(data.next)})`;
      console.warn(`[middleware] Список CMS-слагов считаем неполным: ${reason}`);
      return null;
    }

    if (typeof data.count !== 'number') {
      console.warn('[middleware] В ответе со списком CMS-слагов нет числового count');
      return null;
    }

    if (data.count >= SLUGS_COUNT_WARN_THRESHOLD) {
      // Предел ещё не перейдён, решение принимается как обычно — но дальше
      // молчаливая деградация, поэтому предупреждаем заранее.
      console.warn(
        `[middleware] Опубликованных CMS-страниц ${data.count} при поддерживаемом пределе ${SLUGS_PAGE_SIZE}: ` +
          'после его превышения список слагов станет неполным и настоящие 404 пропадут'
      );
    }

    if (data.count !== data.results.length) {
      console.warn(
        `[middleware] Список CMS-слагов неполон: count=${data.count}, получено ${data.results.length}`
      );
      return null;
    }

    const slugs = new Set<string>();
    for (const item of data.results as Array<{ slug?: unknown }>) {
      // Молча пропускать нераспознанный элемент нельзя: неполный список тут же
      // стал бы авторитетным allowlist-ом и превратил реальную страницу в 404.
      if (!item || typeof item !== 'object' || typeof item.slug !== 'string' || !item.slug) {
        console.warn('[middleware] В списке CMS-слагов есть запись без строкового slug');
        return null;
      }
      slugs.add(item.slug);
    }

    return slugs;
  } catch (error) {
    console.warn('[middleware] Не удалось получить список CMS-слагов:', error);
    return null;
  }
}

/** Обновляет кэш, схлопывая параллельные вызовы в один запрос к API */
function refreshSlugCache(): Promise<Set<string> | null> {
  if (inflightSlugsRequest) return inflightSlugsRequest;

  if (slugsFailedAt !== null && Date.now() - slugsFailedAt < SLUGS_FAILURE_BACKOFF_MS) {
    // Пауза после отказа: отвечаем «не знаю» немедленно. Это по-прежнему
    // fail-open — вызывающий пропустит запрос дальше, — но без похода в сеть
    // и без таймаута в каждом HTML-ответе, пока backend недоступен.
    return Promise.resolve(null);
  }

  inflightSlugsRequest = fetchPublishedSlugs()
    .then(slugs => {
      if (slugs) {
        slugCache = { slugs, fetchedAt: Date.now() };
        slugsFailedAt = null;
      } else {
        slugsFailedAt = Date.now();
      }
      return slugs;
    })
    .finally(() => {
      inflightSlugsRequest = null;
    });

  return inflightSlugsRequest;
}

/** Читает кэш слагов вместе с признаком протухания */
function readSlugCache(): { slugs: Set<string>; isStale: boolean } | null {
  if (!slugCache) return null;

  return {
    slugs: slugCache.slugs,
    // Сравнение нестрогое: AC6 обещает видимость новой страницы «не позднее
    // TTL», поэтому ровно на границе список уже считается протухшим и
    // отрицательное решение (404) без обновления не принимается.
    isStale: Date.now() - slugCache.fetchedAt >= SLUG_CACHE_TTL_MS,
  };
}

/**
 * Отвечает, опубликована ли CMS-страница с таким слагом:
 * `true` — да, `false` — точно нет, `null` — выяснить не удалось (fail-open).
 *
 * Положительное и отрицательное решения намеренно несимметричны:
 *
 * - положительное принимается и по протухшему кэшу, а обновление идёт фоном
 *   (stale-while-revalidate) — страница уже была опубликована, лишний 200
 *   безвреден, а снятие с публикации подстрахует ветка `if (!page)` с `noindex`
 *   в `(blue)/[slug]/page.tsx`;
 * - отрицательное (то есть 404) по протухшему кэшу принимать НЕЛЬЗЯ: отсутствие
 *   слага в устаревшем списке не доказывает, что страницы нет. Иначе вновь
 *   опубликованная страница получала бы 404 в первом запросе после TTL, а при
 *   недоступном backend — постоянно, в обход fail-open. Поэтому здесь список
 *   приходится дождаться, и «не знаю» (null) снова означает пропуск запроса.
 */
async function isPublishedSlug(segment: string): Promise<boolean | null> {
  const cached = readSlugCache();

  if (cached?.slugs.has(segment)) {
    if (cached.isStale) {
      // Фоновое обновление обязано глотать свои ошибки, иначе unhandled rejection
      void refreshSlugCache().catch(() => null);
    }
    return true;
  }

  if (cached && !cached.isStale) return false;

  const fresh = await refreshSlugCache().catch(() => null);
  return fresh === null ? null : fresh.has(segment);
}

/** Декодирует сегмент пути; битую percent-последовательность оставляет как есть */
function decodeSegment(segment: string): string {
  try {
    return decodeURIComponent(segment);
  } catch {
    return segment;
  }
}

/**
 * Возвращает единственный сегмент пути в декодированном виде или null.
 *
 * Один сегмент — в точности зона перехвата catch-all `(blue)/[slug]`.
 * Корень и многосегментные пути Next обрабатывает сам и на несуществующие
 * из них уже отдаёт 404.
 *
 * Декодирование обязательно: в `pathname` кириллический slug приходит в
 * percent-encoding (`/%D0%BE%D1%84%D0%B5%D1%80%D1%82%D0%B0`), а в списке из API
 * лежит обычная строка. Без декодирования опубликованная страница с нелатинским
 * адресом получала бы ложный 404.
 *
 * Закодированный слэш (`%2F`) разделителем сегментов для Next НЕ является:
 * `/foo%2Fbar` остаётся односегментным путём и попадает в тот же catch-all,
 * поэтому пропускать его «как многосегментный» нельзя — живой запрос отдавал бы
 * soft-404 со статусом 200. Такой сегмент проверяется на общих основаниях и в
 * allowlist не попадёт никогда: `Page.slug` — это `SlugField`, слэша в нём быть
 * не может.
 */
function getSingleSegment(pathname: string): string | null {
  const segments = pathname.split('/').filter(Boolean);
  if (segments.length !== 1) return null;

  return decodeSegment(segments[0]);
}

/**
 * Проверяет, является ли маршрут защищенным
 */
function isProtectedRoute(pathname: string): boolean {
  const protectedPaths = ['/profile', '/orders', '/b2b-dashboard'];
  return protectedPaths.some(path => pathname.startsWith(path));
}

/**
 * Проверяет, является ли маршрут публичным (auth routes)
 */
function isAuthRoute(pathname: string): boolean {
  const authPaths = ['/login', '/register', '/password-reset', '/b2b-register'];
  return authPaths.some(path => pathname.startsWith(path));
}

/**
 * Middleware function
 */
export async function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;

  // Проверяем наличие refresh token в cookies
  // ВАЖНО: В Edge Runtime нет доступа к localStorage, используем cookies
  const refreshToken = request.cookies.get('refreshToken')?.value;
  const isAuthenticated = !!refreshToken;

  // Если это protected route и пользователь не авторизован - редирект на /login
  if (isProtectedRoute(pathname) && !isAuthenticated) {
    const url = request.nextUrl.clone();
    url.pathname = '/login';

    // Сохраняем исходный путь для редиректа после входа
    // НЕ добавляем next параметр, если уже на /login (предотвращение бесконечного редиректа)
    if (pathname !== '/login') {
      url.searchParams.set('next', pathname);
    }

    return NextResponse.redirect(url);
  }

  // Если пользователь авторизован и пытается открыть auth route - редирект на главную
  if (isAuthRoute(pathname) && isAuthenticated) {
    const url = request.nextUrl.clone();
    const nextParam = url.searchParams.get('next') || url.searchParams.get('redirect');

    // Если есть next/redirect параметр и он валидный
    if (isSafeRedirectUrl(nextParam)) {
      return NextResponse.redirect(new URL(nextParam!, request.url));
    }

    url.pathname = '/';
    return NextResponse.redirect(url);
  }

  // Настоящий 404 вместо soft-404 из catch-all `(blue)/[slug]`.
  // Проверка идёт последней: редиректы выше не должны ждать сетевой запрос.
  const segment = getSingleSegment(pathname);
  if (segment && !KNOWN_TOP_LEVEL_ROUTES.has(segment)) {
    const isPublished = await isPublishedSlug(segment);

    if (isPublished === null) {
      // Fail-open: список получить не удалось — вслепую 404 не отдаём,
      // иначе недоступный backend превратит весь сайт в 404.
      console.warn(`[middleware] Проверка адреса ${pathname} пропущена: список слагов недоступен`);
      return NextResponse.next();
    }

    if (!isPublished) {
      // Rewrite на внутренний маршрут `/_not-found` со статусом 404: Next
      // переносит статус ответа middleware на ответ (resolve-routes) и рендерит
      // `app/not-found.tsx` (base-server). Если статус когда-нибудь перестанет
      // переноситься — запасной вариант в стори 41.0: rewrite на заведомо
      // несуществующий ДВУХсегментный путь (односегментный перехватит catch-all).
      return NextResponse.rewrite(new URL('/_not-found', request.url), { status: 404 });
    }
  }

  return NextResponse.next();
}

/**
 * Matcher config - определяет маршруты, к которым применяется middleware
 *
 * ВАЖНО: Matcher запускается для ВСЕХ указанных путей
 * Внутри middleware мы делаем дополнительную проверку
 */
export const config = {
  matcher: [
    /*
     * Match all request paths except for:
     * - _next/static (static files)
     * - _next/image (image optimization)
     * - favicon.ico (favicon)
     * - public folder
     * - API routes (handled separately)
     *
     * `api$` рядом с `api/` — не дубль: без него ровно путь `/api` (без
     * завершающего слэша) попадал в middleware и перехватывался логикой 404
     * раньше, чем срабатывал rewrite `/api/:path*` из next.config.ts.
     */
    '/((?!_next/static|_next/image|favicon.ico|.*\\..*|api/|api$).*)',
  ],
};
