/**
 * Метаданные `/electric` (стори 41.21, AC5, решение R2).
 *
 * Тема остаётся доступной, меняются только метаданные: тексты корневого
 * умолчания D7 через `buildMetadata`. До 41.21 здесь стояли «в розницу»,
 * «Крупнейший», «Более 10 000 товаров от ведущих брендов», «B2B», а `og:url`
 * указывал на корень сайта. Адрес закрыт `Disallow: /electric`, поэтому
 * `robots` не задаётся (D4 стори 41.18), `keywords` не нужны (D7).
 */

import { describe, it, expect } from 'vitest';

import { metadata } from '../page';
import { DEFAULT_OG_IMAGE_META } from '@/utils/seo';

const TITLE = 'OPTISPORT — спортивные товары оптом';
const DESCRIPTION =
  'Оптовые продажи спортивных товаров: каталог, условия для оптовых покупателей, доставка по России.';

describe('Метаданные /electric', () => {
  it('title и description — тексты корневого умолчания D7', () => {
    expect(metadata.title).toBe(TITLE);
    expect(metadata.description).toBe(DESCRIPTION);
  });

  it('Open Graph и Twitter повторяют title и description', () => {
    expect(metadata.openGraph?.title).toBe(TITLE);
    expect(metadata.openGraph?.description).toBe(DESCRIPTION);
    expect(metadata.twitter?.title).toBe(TITLE);
    expect(metadata.twitter?.description).toBe(DESCRIPTION);
  });

  it('canonical и og:url — /electric', () => {
    expect(metadata.alternates?.canonical).toBe('/electric');
    expect((metadata.openGraph as { url?: string } | undefined)?.url).toBe('/electric');
  });

  it('картинка — соцпревью по умолчанию', () => {
    expect(metadata.openGraph?.images).toEqual([DEFAULT_OG_IMAGE_META]);
  });

  it('не содержит keywords и robots', () => {
    expect(metadata.keywords).toBeUndefined();
    expect(metadata.robots).toBeUndefined();
  });
});
