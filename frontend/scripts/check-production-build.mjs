#!/usr/bin/env node
/**
 * Проверка production-сборки Next (стори 41.21, code review).
 *
 * Запускается после `npm run build`, поднимает `next start` с заглушкой backend
 * и падает с ненулевым кодом на любом нарушении или на невозможности
 * проверить (fail-closed):
 *
 * - AC1: в JS-чанках, которые загружают публичные страницы, нет `example` без
 *   учёта регистра, а в `.next/static/chunks/**` нет middleware `zustand
 *   devtools`. Проверяемые чанки — объединение двух источников:
 *   1) фактические ссылки из HTML страниц рецепта Task 1.6 и адресов 404 —
 *      так же, как их видит сканер;
 *   2) манифест сборки: для каждой страницы App Router, кроме `/profile/**`,
 *      её чанки, чанки записей всех сегментов-предков и полифилы.
 *   Одного манифеста мало: HTML ссылается и на чанки вне этого набора (layout
 *   соседней группы маршрутов, общие чанки сторов). Исключение `/profile/**` —
 *   решение владельца Q1 (jsPDF на `/profile/orders/[id]`).
 * - AC7: настоящие 404 отвечают 404 и несут ровно один `robots=noindex`,
 *   soft-404 динамических страниц — 200 и ровно один `noindex, follow`.
 *
 * Адрес заглушки backend берётся из той же цепочки переменных, что и в
 * `src/middleware.ts` (`getApiBaseUrl`): middleware получает адрес при сборке,
 * поэтому переменные окружения запуска обязаны совпадать со сборкой. Локально,
 * где порт 8001 занят backend из Docker:
 *   NEXT_PUBLIC_API_URL=http://localhost:18001/api/v1 npm run build
 *   NEXT_PUBLIC_API_URL=http://localhost:18001/api/v1 npm run check:build
 */

import { spawn } from 'node:child_process';
import { existsSync, readdirSync, readFileSync } from 'node:fs';
import http from 'node:http';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const FRONTEND_DIR = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const NEXT_DIR = path.join(FRONTEND_DIR, '.next');

/** Публичные адреса рецепта Task 1.6. */
export const PUBLIC_URLS = [
  '/coming-soon',
  '/home',
  '/catalog',
  '/catalog?is_hit=true',
  '/register',
  '/b2b-register',
  '/password-reset',
  '/login',
  '/cart',
  '/checkout',
  '/partners',
  '/privacy-policy',
  '/about',
  '/delivery',
  '/requisites',
  '/electric',
];
export const NOT_FOUND_URLS = ['/nonexistent-xyz', '/catalog/zzz', '/zzz/yyy'];
export const SOFT_404_URLS = ['/product/zzz-none', '/blog/zzz-none', '/news/zzz-none'];

/** Закрытый раздел (`Disallow: /profile`), исключение Q1. */
const PRIVATE_PREFIX = '/(blue)/profile/';

export const FORBIDDEN_IN_PUBLIC_CHUNKS = /example/i;
export const FORBIDDEN_ANYWHERE = 'zustand devtools middleware';

const USER_AGENT = 'AuditikBot/1.0';
const NEXT_PORT = Number(process.env.CHECK_BUILD_PORT || 3100);
const READY_TIMEOUT_MS = 60_000;
const REQUEST_TIMEOUT_MS = 30_000;

/** Страницы манифеста, чанки которых загружают публичные адреса. */
export function selectPublicPages(pageKeys) {
  return pageKeys.filter(key => key.endsWith('/page') && !key.startsWith(PRIVATE_PREFIX));
}

/** Каталоги-предки ключа манифеста: `/(blue)/home/page` → `''`, `/(blue)`, `/(blue)/home`. */
function ancestorDirs(pageKey) {
  const parts = pageKey.split('/').slice(1, -1);
  return parts.map((_, i) => '/' + parts.slice(0, i + 1).join('/')).concat('');
}

/**
 * JS-чанки страницы по манифесту: её собственные, всех записей в
 * каталогах-предках (layout, loading, error, not-found) и полифилы.
 */
export function chunksForPage(pageKey, appPages, polyfillFiles) {
  const dirs = new Set(ancestorDirs(pageKey));
  const chunks = new Set(polyfillFiles);

  for (const [key, files] of Object.entries(appPages)) {
    if (key === pageKey || dirs.has(key.slice(0, key.lastIndexOf('/')))) {
      files.forEach(file => chunks.add(file));
    }
  }

  return [...chunks].filter(file => file.endsWith('.js')).sort();
}

/**
 * Чанки, на которые ссылается HTML: `<script src>` и RSC-данные страницы
 * (там кавычки экранированы, а сегменты вида `[slug]` закодированы).
 */
export function chunkRefsFromHtml(html) {
  const refs = new Set();
  for (const [, ref] of html.matchAll(/(static\/chunks\/[^"'\\\s]+?\.js)(?!\w)/g)) {
    refs.add(decodeURIComponent(ref));
  }
  return [...refs].sort();
}

/** Контекст первого совпадения — чтобы по логу CI сразу найти источник. */
export function matchContext(text, pattern) {
  const match = pattern.exec(text);
  if (!match) return null;
  const start = Math.max(0, match.index - 60);
  return text.slice(start, match.index + match[0].length + 60).replace(/\s+/g, ' ');
}

/** Значения `content` всех `<meta name="robots">` документа. */
export function robotsMetaContents(html) {
  const contents = [];
  for (const [tag] of html.matchAll(/<meta\b[^>]*>/gi)) {
    if (!/\bname\s*=\s*["']robots["']/i.test(tag)) continue;
    const content = /\bcontent\s*=\s*["']([^"']*)["']/i.exec(tag);
    contents.push(content ? content[1] : '');
  }
  return contents;
}

/** Цепочка `getApiBaseUrl` из `src/middleware.ts` без последнего умолчания. */
export function middlewareApiBase(env) {
  const base =
    env.NEXT_PUBLIC_MIDDLEWARE_API_URL ||
    env.NEXT_PUBLIC_API_URL_INTERNAL ||
    env.NEXT_PUBLIC_API_URL ||
    '';
  return base.replace(/\/+$/, '');
}

function readJson(file) {
  if (!existsSync(file)) {
    throw new Error(`нет ${path.relative(FRONTEND_DIR, file)} — сначала выполните npm run build`);
  }
  return JSON.parse(readFileSync(file, 'utf8'));
}

function listFiles(dir) {
  return readdirSync(dir, { withFileTypes: true }).flatMap(entry => {
    const full = path.join(dir, entry.name);
    return entry.isDirectory() ? listFiles(full) : [full];
  });
}

/** Чанк → источники, из-за которых он проверяется (для сообщения об ошибке). */
function collectManifestChunks(errors) {
  const appPages = readJson(path.join(NEXT_DIR, 'app-build-manifest.json')).pages ?? {};
  const polyfillFiles = readJson(path.join(NEXT_DIR, 'build-manifest.json')).polyfillFiles ?? [];
  const pages = selectPublicPages(Object.keys(appPages));
  const owners = new Map();

  if (pages.length === 0) errors.push('в app-build-manifest нет ни одной публичной страницы');

  for (const page of pages) {
    const chunks = chunksForPage(page, appPages, polyfillFiles);
    if (chunks.length === 0) errors.push(`${page}: в манифесте нет ни одного JS-чанка`);
    chunks.forEach(chunk => owners.set(chunk, owners.get(chunk) ?? `манифест ${page}`));
  }

  return owners;
}

function scanChunks(owners, errors) {
  for (const [chunk, owner] of owners) {
    const file = path.join(NEXT_DIR, chunk);
    if (!existsSync(file)) {
      errors.push(`${owner}: чанка ${chunk} нет на диске`);
      continue;
    }
    const context = matchContext(readFileSync(file, 'utf8'), FORBIDDEN_IN_PUBLIC_CHUNKS);
    if (context) errors.push(`${owner}: ${chunk} содержит «example»: …${context}…`);
  }

  const chunksDir = path.join(NEXT_DIR, 'static', 'chunks');
  if (!existsSync(chunksDir)) {
    errors.push('нет каталога .next/static/chunks');
    return;
  }
  for (const file of listFiles(chunksDir)) {
    if (readFileSync(file, 'utf8').includes(FORBIDDEN_ANYWHERE)) {
      errors.push(`${path.relative(NEXT_DIR, file)} содержит «${FORBIDDEN_ANYWHERE}»`);
    }
  }
}

function startStubBackend(apiBase) {
  const url = new URL(apiBase);
  if (url.protocol !== 'http:' || !['localhost', '127.0.0.1'].includes(url.hostname)) {
    throw new Error(`заглушке нужен локальный http-адрес, а сборка смотрит в ${apiBase}`);
  }

  const pagesPath = `${url.pathname.replace(/\/+$/, '')}/pages/`;
  const stats = { pagesRequests: 0 };

  // Пустой полный список CMS-слагов в форме DRF: middleware 41.0 принимает его
  // как авторитетный и отдаёт настоящий 404. На остальное — 404, как backend
  // на несуществующий товар или статью.
  const server = http.createServer((req, res) => {
    const reqPath = new URL(req.url ?? '/', 'http://stub').pathname;
    res.setHeader('Content-Type', 'application/json');
    if (reqPath === pagesPath) {
      stats.pagesRequests += 1;
      res.end(JSON.stringify({ count: 0, next: null, previous: null, results: [] }));
      return;
    }
    res.statusCode = 404;
    res.end(JSON.stringify({ detail: 'Not found.' }));
  });

  return new Promise((resolve, reject) => {
    server.once('error', error =>
      reject(new Error(`заглушка backend не поднялась на порту ${url.port}: ${error.message}`))
    );
    server.listen(Number(url.port || 80), url.hostname, () => resolve({ server, stats }));
  });
}

async function fetchPage(urlPath) {
  const res = await fetch(`http://localhost:${NEXT_PORT}${urlPath}`, {
    headers: { 'User-Agent': USER_AGENT },
    redirect: 'manual',
    signal: AbortSignal.timeout(REQUEST_TIMEOUT_MS),
  });
  return { status: res.status, location: res.headers.get('location'), html: await res.text() };
}

async function waitForServer(child) {
  const deadline = Date.now() + READY_TIMEOUT_MS;
  while (Date.now() < deadline) {
    if (child.exitCode !== null) throw new Error(`next start завершился с кодом ${child.exitCode}`);
    try {
      const res = await fetch(`http://localhost:${NEXT_PORT}/robots.txt`, {
        signal: AbortSignal.timeout(2_000),
      });
      if (res.ok) return;
    } catch {
      // сервер ещё не слушает порт
    }
    await new Promise(resolve => setTimeout(resolve, 500));
  }
  throw new Error(`next start не ответил за ${READY_TIMEOUT_MS / 1000} с`);
}

function addHtmlChunks(urlPath, html, owners, errors) {
  const refs = chunkRefsFromHtml(html);
  if (refs.length === 0) errors.push(`${urlPath}: в HTML нет ссылок на JS-чанки`);
  refs.forEach(chunk => owners.set(chunk, owners.get(chunk) ?? `HTML ${urlPath}`));
}

async function checkServedPages(apiBase, owners, errors) {
  const { server, stats } = await startStubBackend(apiBase);
  const child = spawn(
    process.execPath,
    [
      path.join(FRONTEND_DIR, 'node_modules', 'next', 'dist', 'bin', 'next'),
      'start',
      '-p',
      String(NEXT_PORT),
    ],
    { cwd: FRONTEND_DIR, env: process.env, stdio: ['ignore', 'pipe', 'pipe'] }
  );
  let serverLog = '';
  child.stdout.on('data', chunk => (serverLog += chunk));
  child.stderr.on('data', chunk => (serverLog += chunk));

  try {
    await waitForServer(child);

    for (const urlPath of PUBLIC_URLS) {
      const { status, location, html } = await fetchPage(urlPath);
      console.log(`page: ${urlPath} → ${status}${location ? ` ${location}` : ''}`);
      if (status === 200) {
        addHtmlChunks(urlPath, html, owners, errors);
      } else if (status < 300 || status >= 400 || !location) {
        // Редирект допустим (адрес назначения тоже в перечне), остальное —
        // признак сломанной страницы, чанки которой проверить не удалось.
        errors.push(`${urlPath}: ожидался HTTP 200 или редирект, получен ${status}`);
      }
    }

    for (const urlPath of NOT_FOUND_URLS) {
      const { status, html } = await fetchPage(urlPath);
      const robots = robotsMetaContents(html);
      console.log(`robots: ${urlPath} → ${status} ${JSON.stringify(robots)}`);
      if (status !== 404) errors.push(`${urlPath}: ожидался HTTP 404, получен ${status}`);
      if (robots.length !== 1 || robots[0] !== 'noindex') {
        errors.push(`${urlPath}: ожидался один robots=noindex, получено ${JSON.stringify(robots)}`);
      }
      addHtmlChunks(urlPath, html, owners, errors);
    }

    for (const urlPath of SOFT_404_URLS) {
      const { status, html } = await fetchPage(urlPath);
      const robots = robotsMetaContents(html);
      console.log(`robots: ${urlPath} → ${status} ${JSON.stringify(robots)}`);
      if (status !== 200) {
        errors.push(`${urlPath}: ожидался HTTP 200 (soft-404), получен ${status}`);
      }
      if (robots.length !== 1 || robots[0] !== 'noindex, follow') {
        errors.push(
          `${urlPath}: ожидался один robots «noindex, follow», получено ${JSON.stringify(robots)}`
        );
      }
      addHtmlChunks(urlPath, html, owners, errors);
    }

    if (stats.pagesRequests === 0) {
      errors.push(
        `middleware не запрашивал список CMS-слагов у заглушки ${apiBase} — сборка смотрит в другой адрес`
      );
    }
  } catch (error) {
    errors.push(`${error.message}\n--- вывод next start ---\n${serverLog}`);
  } finally {
    child.kill();
    server.close();
  }
}

async function main() {
  const apiBase = middlewareApiBase(process.env);
  if (!apiBase) {
    throw new Error(
      'не задан NEXT_PUBLIC_API_URL (или NEXT_PUBLIC_MIDDLEWARE_API_URL) — тот же, что при сборке'
    );
  }

  const errors = [];
  const owners = collectManifestChunks(errors);
  await checkServedPages(apiBase, owners, errors);
  scanChunks(owners, errors);
  console.log(`chunks: проверено ${owners.size}`);

  if (errors.length > 0) {
    console.error(`\nПроверка production-сборки не пройдена (${errors.length}):`);
    errors.forEach(error => console.error(`- ${error}`));
    process.exit(1);
  }
  console.log('\nПроверка production-сборки пройдена');
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  main().catch(error => {
    console.error(`Проверка production-сборки не выполнена: ${error.message}`);
    process.exit(1);
  });
}
