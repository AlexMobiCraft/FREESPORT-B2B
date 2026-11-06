/**
 * Страж публичных текстов (стори 41.21, AC6, решение R1 и 38-ФЗ ст. 5 ч. 3 п. 1).
 *
 * Розничная регистрация отключена, поэтому метаданные и карточка `/coming-soon`
 * описывают только оптовое предложение. Превосходная степень без подтверждения
 * и непроверяемые числа («более 10 000 товаров») тоже запрещены.
 *
 * Вне охвата: description `/catalog` («рекомендованные розничные цены», D2) и
 * `og:image:alt` картинки по умолчанию (`utils/seo.ts`) — оба корректны.
 */

import { createElement } from 'react';
import type { Metadata } from 'next';
import { describe, it, expect, vi } from 'vitest';
import { render } from '@testing-library/react';

import { metadata as rootMetadata } from '@/app/layout';
import { metadata as homeMetadata } from '@/app/(blue)/home/page';
import { metadata as comingSoonMetadata } from '@/app/(coming-soon)/coming-soon/page';
import { metadata as electricMetadata } from '@/app/(electric)/electric/page';
import { generateMetadata as generateSearchMetadata } from '@/app/(blue)/search/page';
import ComingSoonClient from '@/app/ComingSoonClient';

// Шрифты next/font в тестовой среде не резолвятся, поэтому заменяются заглушкой.
vi.mock('next/font/google', () => ({
  Inter: () => ({ variable: '--font-inter' }),
  Roboto_Condensed: () => ({ variable: '--font-roboto-condensed' }),
}));

// Анимации не нужны, важен только текст карточки.
vi.mock('motion/react', async () => {
  const { createElement: h } = await import('react');
  const motionKeys = ['initial', 'animate', 'exit', 'transition', 'variants', 'whileHover'];
  return {
    motion: {
      div: ({ children, ...props }: Record<string, unknown>) =>
        h(
          'div',
          Object.fromEntries(Object.entries(props).filter(([key]) => !motionKeys.includes(key))),
          children as never
        ),
    },
  };
});

const FORBIDDEN = /рознич|розниц|B2C|B2B|платформ|ведущ|крупнейш|лучш|10\s?000/i;

/**
 * Строки поля метаданных. Title в Next бывает и объектом
 * (`{ absolute }`, `{ default, template }`): проверяются все его строки,
 * иначе `String(объект)` дал бы `[object Object]` и страж молча бы прошёл.
 * Непредусмотренная форма — ошибка, а не пропуск.
 */
function textsOf(value: unknown): string[] {
  if (value == null) return [];
  if (typeof value === 'string') return [value];
  if (typeof value === 'object') {
    const texts = ['absolute', 'default', 'template']
      .map(key => (value as Record<string, unknown>)[key])
      .filter((text): text is string => typeof text === 'string');
    if (texts.length > 0) return texts;
  }
  throw new Error(`неизвестная форма текста метаданных: ${JSON.stringify(value)}`);
}

/** Строки title, description, og и twitter, которые видит сканер и соцсети. */
function copyFields(metadata: Metadata): string[] {
  return [
    metadata.title,
    metadata.description,
    metadata.openGraph?.title,
    metadata.openGraph?.description,
    metadata.twitter?.title,
    metadata.twitter?.description,
  ].flatMap(textsOf);
}

describe('Публичные тексты без розницы и превосходных степеней', () => {
  it.each<[string, () => Promise<Metadata> | Metadata]>([
    ['/', () => rootMetadata],
    ['/home', () => homeMetadata],
    ['/coming-soon', () => comingSoonMetadata],
    ['/electric', () => electricMetadata],
    ['/search?q=мяч', () => generateSearchMetadata({ searchParams: Promise.resolve({ q: 'мяч' }) })],
  ])('метаданные %s', async (_path, getMetadata) => {
    const fields = copyFields(await getMetadata());

    expect(fields.length).toBeGreaterThan(0);
    for (const field of fields) {
      expect(field).not.toMatch(FORBIDDEN);
    }
  });

  it.each<[string, Metadata]>([
    ['title.absolute', { title: { absolute: 'Лучшие цены' } }],
    ['title.default', { title: { default: 'Лучшие цены', template: '%s | OPTISPORT' } }],
    ['title.template', { title: { default: 'OPTISPORT', template: '%s — лучшие цены' } }],
    ['openGraph.title', { openGraph: { title: { absolute: 'Лучшие цены' } } }],
    ['twitter.title', { twitter: { title: { default: 'Лучшие цены', template: '%s' } } }],
  ])('страж видит текст объектного %s', (_field, metadata) => {
    expect(copyFields(metadata).join(' ')).toMatch(FORBIDDEN);
  });

  it('видимый текст карточки /coming-soon', () => {
    const { container } = render(createElement(ComingSoonClient));

    expect(container.textContent).toContain('Оптовые заказы');
    expect(container.textContent).not.toMatch(FORBIDDEN);
  });
});
