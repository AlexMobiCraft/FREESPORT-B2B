/**
 * Тест-страж: состав заголовков безопасности HTML фронтенда (стори 41.5).
 *
 * Граница ответственности после 41.5: на `location /` nginx выставляет ТОЛЬКО
 * Strict-Transport-Security, и этот одиночный `add_header` вытесняет там весь
 * унаследованный серверный набор. Значит всё остальное на HTML обязан поставить
 * `next.config.ts` — включая `X-XSS-Protection`, который Django перестал
 * отдавать в 4.0, а nginx на этой локации больше не добавляет. Убери его
 * отсюда — и заголовок молча исчезнет со всего HTML сайта.
 *
 * Второе, что здесь закрепляется: CSP и Permissions-Policy существуют в двух
 * несвязанных источниках (Next и сниппеты nginx), общего файла у них нет и быть
 * не может. Единственная защита от расхождения — сверка ниже.
 *
 * Ограничение того же рода, что и у backend/tests/unit/test_nginx_security_headers.py:
 * доказывается «объявлено», а не «доехало до браузера».
 */

import { describe, it, expect } from 'vitest';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

import nextConfig from '../../next.config';

const FRONTEND_DIR = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..', '..');
const REPO_ROOT = path.resolve(FRONTEND_DIR, '..');
const SNIPPET_NO_HSTS = path.join(
  REPO_ROOT,
  'docker',
  'nginx',
  'snippets',
  'security-headers-no-hsts.conf'
);

/** Заголовки правила `/(.*)` из headers() — как плоская карта имя → значение */
async function htmlHeaders(): Promise<Record<string, string>> {
  expect(typeof nextConfig.headers).toBe('function');
  const rules = await nextConfig.headers!();
  const rule = rules.find(entry => entry.source === '/(.*)');
  expect(rule, 'нет правила для source /(.*) — заголовки перестали покрывать весь HTML').toBeDefined();

  return Object.fromEntries(rule!.headers.map(header => [header.key, header.value]));
}

/** Значение add_header из сниппета nginx (без разбора комментариев) */
function snippetHeader(file: string, name: string): string | undefined {
  const directives = fs
    .readFileSync(file, 'utf-8')
    .split('\n')
    .filter(line => !line.trim().startsWith('#'));
  const match = directives
    .map(line => new RegExp(`^\\s*add_header\\s+${name}\\s+"([^"]*)"`).exec(line))
    .find(Boolean);
  return match?.[1];
}

describe('next.config.ts: заголовки безопасности HTML', () => {
  it('X-Frame-Options — SAMEORIGIN (запас на встраивание CMS-страниц)', async () => {
    // Парный заголовок — frame-ancestors ниже. Меняются только вместе:
    // в поддерживающих браузерах CSP перекрывает X-Frame-Options, и пара
    // «SAMEORIGIN + 'none'» молча свела бы запас на нет.
    expect((await htmlHeaders())['X-Frame-Options']).toBe('SAMEORIGIN');
  });

  it('X-Content-Type-Options и Referrer-Policy на месте', async () => {
    const headers = await htmlHeaders();

    expect(headers['X-Content-Type-Options']).toBe('nosniff');
    expect(headers['Referrer-Policy']).toBe('strict-origin-when-cross-origin');
  });

  it('X-XSS-Protection выставляется здесь — других источников на HTML нет', async () => {
    expect((await htmlHeaders())['X-XSS-Protection']).toBe('1; mode=block');
  });

  it('CSP содержит frame-ancestors, согласованный с X-Frame-Options', async () => {
    const headers = await htmlHeaders();
    const csp = headers['Content-Security-Policy'];

    expect(csp, 'CSP на HTML отсутствует').toBeDefined();
    expect(csp).toContain("frame-ancestors 'self'");
    expect(headers['X-Frame-Options']).toBe('SAMEORIGIN');
  });

  it('Permissions-Policy задан и без interest-cohort', async () => {
    const value = (await htmlHeaders())['Permissions-Policy'];

    expect(value, 'Permissions-Policy на HTML отсутствует').toBeDefined();
    // Директива снята из Chrome 115+ и даёт Unrecognized feature в консоли,
    // что противоречит требованию «консоль без ошибок» (AC6 стори 41.5).
    expect(value).not.toContain('interest-cohort');
  });

  it('Cache-Control здесь НЕ задаётся', async () => {
    // Next в production перезаписывает Cache-Control, заданный в конфиге.
    // Срок жизни HTML управляется сегментной опцией revalidate (src/app/layout.tsx),
    // иначе статические страницы отдаются с s-maxage=31536000 — год заглушки
    // «Скоро открытие» в общем кэше после запуска сайта.
    expect((await htmlHeaders())['Cache-Control']).toBeUndefined();
  });
});

describe('Сверка с nginx: одна политика — два источника', () => {
  it('сниппет nginx доступен из этого окружения', () => {
    // Намеренно НЕ skipIf. Эта сверка — единственная защита от расхождения двух
    // источников одной политики, и пропуск её обессмысливает. В контейнере
    // frontend каталог docker/ смонтирован в /docker (docker-compose.yml,
    // сервис frontend); на хосте и в CI он лежит рядом с frontend/.
    expect(
      fs.existsSync(SNIPPET_NO_HSTS),
      `Не найден ${SNIPPET_NO_HSTS}. В контейнере frontend нужен volume ` +
        '`../docker:/docker:ro` (docker-compose.yml). Пропускать эту проверку нельзя: ' +
        'без неё CSP в next.config.ts и в сниппетах nginx расходятся молча.'
    ).toBe(true);
  });

  it('CSP совпадает со сниппетом nginx посимвольно', async () => {
    const fromNginx = snippetHeader(SNIPPET_NO_HSTS, 'Content-Security-Policy');
    const fromNext = (await htmlHeaders())['Content-Security-Policy'];

    // Сниппет без HSTS выбран как эталон намеренно: он покрывает ту же
    // поверхность «сайт» (frame-ancestors 'self'), что и HTML фронтенда.
    expect(fromNext).toBe(fromNginx);
  });

  it('Permissions-Policy совпадает со сниппетом nginx', async () => {
    const fromNginx = snippetHeader(SNIPPET_NO_HSTS, 'Permissions-Policy');
    const fromNext = (await htmlHeaders())['Permissions-Policy'];

    expect(fromNext).toBe(fromNginx);
  });

  it('Strict-Transport-Security здесь НЕ задаётся — его источник только nginx', async () => {
    expect((await htmlHeaders())['Strict-Transport-Security']).toBeUndefined();
  });
});
