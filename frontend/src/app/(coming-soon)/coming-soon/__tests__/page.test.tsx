/**
 * Метаданные страницы `/coming-soon` (стори 41.6, AC1).
 *
 * `/coming-soon` — фактическая главная прода: `GET https://optisport.ru/`
 * отдаёт 307 на неё. До стори она наследовала корневые `title`/`description`,
 * из-за чего ссылка на сайт в соцсетях разворачивалась в общий текст платформы.
 *
 * `robots` здесь намеренно НЕ проверяется на наличие — он и не должен
 * появиться: менять индексируемость фактической главной эта стори не берётся.
 */

import { describe, it, expect, vi } from 'vitest';

import { metadata } from '../page';
import { metadata as rootMetadata } from '@/app/layout';
import { DEFAULT_OG_IMAGE_META } from '@/utils/seo';

// Корневой layout импортируется ради сверки с его title/description; шрифты
// next/font в тестовой среде не резолвятся, поэтому заменяются заглушкой.
vi.mock('next/font/google', () => ({
  Inter: () => ({ variable: '--font-inter' }),
  Roboto_Condensed: () => ({ variable: '--font-roboto-condensed' }),
}));

describe('Метаданные /coming-soon', () => {
  it('задаёт собственный title', () => {
    expect(metadata.title).toBe('OPTISPORT скоро откроется — оптовые продажи спорттоваров');
  });

  it('задаёт собственный description', () => {
    expect(metadata.description).toBe(
      'OPTISPORT — оптовые и розничные продажи спортивных товаров. Сайт скоро откроется, по вопросам сотрудничества пишите на info@optisport.ru.'
    );
  });

  it('отличается от значений корневого layout', () => {
    expect(metadata.title).not.toBe(rootMetadata.title);
    expect(metadata.description).not.toBe(rootMetadata.description);
  });

  it('собран через buildMetadata: есть canonical, openGraph и twitter', () => {
    expect(metadata.alternates?.canonical).toBe('/coming-soon');
    expect(metadata.openGraph?.title).toBe(metadata.title);
    expect(metadata.openGraph?.url).toBe('/coming-soon');
    expect(metadata.openGraph?.images).toEqual([DEFAULT_OG_IMAGE_META]);
    expect(metadata.twitter?.title).toBe(metadata.title);
  });

  it('не задаёт robots — индексируемость страницы стори не меняет', () => {
    expect(metadata.robots).toBeUndefined();
  });
});
