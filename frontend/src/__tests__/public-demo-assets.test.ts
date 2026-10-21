/**
 * Тест-страж: статические демо-макеты не возвращаются в `public/` (стори 41.19, AC1, D6).
 *
 * Файлы из `public/` отдаются статикой в обход любых проверок маршрута:
 * matcher middleware исключает пути с точкой, поэтому `/examples/1.html` или
 * `/electric-orange/design.json` middleware не видит. Настоящий 404 на такие
 * адреса доказывается только отсутствием самих файлов.
 *
 * Каталог `public/electric-orange/img/` при этом остаётся: его картинки
 * использует секция категорий темы `/electric`.
 */

import { describe, it, expect } from 'vitest';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

import nextConfig from '../../next.config';

const FRONTEND_DIR = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..', '..');
const PUBLIC_DIR = path.join(FRONTEND_DIR, 'public');
const CATEGORY_SECTION = path.join(
  FRONTEND_DIR,
  'src',
  'components',
  'home',
  'ElectricCategorySection.tsx'
);

describe('Демо-макеты в public/', () => {
  it('каталога public/examples нет', () => {
    expect(fs.existsSync(path.join(PUBLIC_DIR, 'examples'))).toBe(false);
  });

  it('в public/electric-orange остался только каталог img', () => {
    const entries = fs.readdirSync(path.join(PUBLIC_DIR, 'electric-orange'), {
      withFileTypes: true,
    });

    expect(entries.map(entry => entry.name)).toEqual(['img']);
    expect(entries[0].isDirectory()).toBe(true);
  });

  it('все картинки секции категорий /electric лежат на диске', () => {
    const source = fs.readFileSync(CATEGORY_SECTION, 'utf-8');
    const images = [...source.matchAll(/['"](\/electric-orange\/img\/[^'"]+)['"]/g)].map(
      match => match[1]
    );

    expect(images.length).toBeGreaterThan(0);
    const missing = images.filter(image => !fs.existsSync(path.join(PUBLIC_DIR, image)));
    expect(missing).toEqual([]);
  });

  it('в next.config.ts нет rewrite на макет /electric-orange', async () => {
    expect(typeof nextConfig.rewrites).toBe('function');
    const result = await nextConfig.rewrites!();
    // rewrites() может вернуть массив или объект с фазами beforeFiles/afterFiles/fallback
    const rules = Array.isArray(result)
      ? result
      : [...(result.beforeFiles ?? []), ...(result.afterFiles ?? []), ...(result.fallback ?? [])];

    const sources = rules.map(rule => rule.source);
    expect(sources.filter(source => source.startsWith('/electric-orange'))).toEqual([]);
  });
});
