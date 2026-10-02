/**
 * Тест-страж: срок `stale-while-revalidate` HTML (стори 41.19, AC5, решение D8).
 *
 * Next выводит `Cache-Control: s-maxage=<revalidate>, stale-while-revalidate=
 * <expireTime − revalidate>`, и SWR появляется только при `revalidate <
 * expireTime`. Без `expireTime` в конфиге Next 15.5.18 берёт год, и прод отдавал
 * `stale-while-revalidate=31532400` (tech-debt п. 29).
 *
 * Доказывается «объявлено», а не «доехало до браузера»: фактический заголовок
 * проверяется на production-сборке (см. стори 41.19, Task 7.3).
 */

import { describe, it, expect } from 'vitest';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { getCacheControlHeader } from 'next/dist/server/lib/cache-control';

import nextConfig from '../../next.config';

const EXPIRE_TIME = 86400;
const APP_DIR = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..', 'app');

/** Все исходники `src/app`, кроме тестов */
function collectSources(dir: string): string[] {
  const files: string[] = [];

  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      if (entry.name !== '__tests__') files.push(...collectSources(full));
    } else if (/\.tsx?$/.test(entry.name)) {
      files.push(full);
    }
  }

  return files;
}

describe('Срок stale-while-revalidate', () => {
  it(`expireTime = ${EXPIRE_TIME}`, () => {
    expect(nextConfig.expireTime).toBe(EXPIRE_TIME);
  });

  it('каждый числовой revalidate в src/app меньше expireTime', () => {
    const found = collectSources(APP_DIR).flatMap(file => {
      const source = fs.readFileSync(file, 'utf-8');
      return [...source.matchAll(/export const revalidate\s*=\s*(\d+)/g)].map(match => ({
        file: path.relative(APP_DIR, file),
        value: Number(match[1]),
      }));
    });

    // Сегменты с revalidate есть — иначе проверка ниже прошла бы впустую
    expect(found.length).toBeGreaterThan(0);
    const invalid = found.filter(({ value }) => !(value > 0 && value < EXPIRE_TIME));
    expect(invalid).toEqual([]);
  });

  it('заголовок для revalidate = 3600 — s-maxage=3600, stale-while-revalidate=82800', () => {
    expect(getCacheControlHeader({ revalidate: 3600, expire: nextConfig.expireTime })).toBe(
      's-maxage=3600, stale-while-revalidate=82800'
    );
  });
});
