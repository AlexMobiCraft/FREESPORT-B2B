/**
 * Разметка schema.org уровня сайта: Organization + WebSite (Story 41.6).
 *
 * Оба узла лежат в одном `@graph`, а не в двух отдельных `<script>`: только так
 * `WebSite.publisher` ссылается на `Organization` по `@id`, и робот видит
 * связанные сущности, а не две карточки рядом.
 *
 * Монтируется в корневом layout — он единственный покрывает и `(blue)`, и
 * `(electric)`, и `(coming-soon)`. Осознанное следствие: блок попадает и на
 * `not-found.tsx`; страница 404 уже несёт `noindex`, разметка на ней инертна.
 *
 * Перед вставкой через `dangerouslySetInnerHTML` каждый `<` заменяется на
 * `\\u003c`. Данные разметки — константы модуля, но не литеральные: `SITE_URL`
 * приходит из `NEXT_PUBLIC_APP_URL`, то есть из окружения сборки. Литеральный
 * `</script>` внутри инлайн-скрипта закрывает тег и выносит остаток графа в
 * документ как разметку; для JSON `\\u003c` — та же строка, робот читает её без
 * изменений.
 */

import { ORGANIZATION_JSON_LD, WEBSITE_JSON_LD } from '@/config/organization';

const SITE_GRAPH = {
  '@context': 'https://schema.org',
  '@graph': [ORGANIZATION_JSON_LD, WEBSITE_JSON_LD],
};

/** JSON графа, безопасный для вставки внутрь `<script>` */
const SITE_GRAPH_JSON = JSON.stringify(SITE_GRAPH).replaceAll('<', '\\u003c');

export function SiteJsonLd() {
  return (
    <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: SITE_GRAPH_JSON }} />
  );
}
