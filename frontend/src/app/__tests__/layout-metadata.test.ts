/**
 * Корневые умолчания метаданных `app/layout.tsx` (стори 41.19, AC4, решение D7).
 *
 * Их наследует каждая страница без собственных title/description, а страница
 * без своего `openGraph` — ещё og- и twitter-теги. До 41.19 здесь стояли
 * «OPTISPORT Platform | B2B/B2C…» и «Ведущая платформа…» — латиница и
 * превосходная степень, которые сканер аудита находил на /register.
 */

import { describe, it, expect, vi } from 'vitest';

import { metadata } from '@/app/layout';

// Шрифты next/font в тестовой среде не резолвятся, поэтому заменяются заглушкой.
vi.mock('next/font/google', () => ({
  Inter: () => ({ variable: '--font-inter' }),
  Roboto_Condensed: () => ({ variable: '--font-roboto-condensed' }),
}));

const TITLE = 'OPTISPORT — спортивные товары оптом';
const DESCRIPTION =
  'Оптовые продажи спортивных товаров: каталог, условия для оптовых покупателей, доставка по России.';

describe('Корневые метаданные app/layout.tsx', () => {
  it('title и description — дословно по D7', () => {
    expect(metadata.title).toBe(TITLE);
    expect(metadata.description).toBe(DESCRIPTION);
  });

  it('Open Graph и Twitter повторяют title и description', () => {
    expect(metadata.openGraph?.title).toBe(TITLE);
    expect(metadata.openGraph?.description).toBe(DESCRIPTION);
    expect(metadata.twitter?.title).toBe(TITLE);
    expect(metadata.twitter?.description).toBe(DESCRIPTION);
  });

  it('не содержит keywords: поисковики meta keywords не используют', () => {
    expect('keywords' in metadata).toBe(false);
  });

  it('не содержит «Platform», «B2B», «B2C», «Ведущая»', () => {
    // С учётом регистра: alt картинки по умолчанию содержит кириллическое
    // «платформа» (utils/seo.ts) — это не нарушение AC4.
    expect(JSON.stringify(metadata)).not.toMatch(/Platform|B2B|B2C|Ведущая/);
  });
});
