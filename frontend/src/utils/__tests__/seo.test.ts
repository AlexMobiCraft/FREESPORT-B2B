/**
 * Тесты `buildMetadata` в части соцпревью (стори 41.6).
 *
 * Закрепляют ровно одно решение: размеры получает ТОЛЬКО картинка по умолчанию.
 * Габариты чужих изображений (обложка статьи, фото товара) нам неизвестны —
 * объявить их значило бы соврать роботу, поэтому чужой URL обязан остаться
 * голой строкой без `width`/`height`.
 *
 * Второе, что здесь защищено: `twitter.images` остаётся массивом строк. Twitter
 * размеров не читает, а объект вместо строки там ломает карточку.
 */

import { describe, it, expect, vi, afterEach } from 'vitest';

import {
  buildMetadata,
  DEFAULT_OG_IMAGE,
  DEFAULT_OG_IMAGE_HEIGHT,
  DEFAULT_OG_IMAGE_META,
  DEFAULT_OG_IMAGE_TYPE,
  DEFAULT_OG_IMAGE_WIDTH,
  normalizeSiteUrl,
} from '../seo';

const base = {
  title: 'Заголовок',
  description: 'Описание',
  path: '/some-page',
};

describe('buildMetadata: соцпревью по умолчанию', () => {
  it('без параметра image подставляет картинку по умолчанию вместе с размерами', () => {
    const metadata = buildMetadata(base);

    expect(metadata.openGraph?.images).toEqual([DEFAULT_OG_IMAGE_META]);
  });

  it('при явном указании картинки по умолчанию строкой дополняет её размерами', () => {
    const metadata = buildMetadata({ ...base, image: DEFAULT_OG_IMAGE });

    expect(metadata.openGraph?.images).toEqual([DEFAULT_OG_IMAGE_META]);
  });

  it('сохраняет собственный alt, дополняя картинку по умолчанию размерами', () => {
    const metadata = buildMetadata({
      ...base,
      image: { url: DEFAULT_OG_IMAGE, alt: 'Свой альт' },
    });

    expect(metadata.openGraph?.images).toEqual([
      {
        url: DEFAULT_OG_IMAGE,
        width: DEFAULT_OG_IMAGE_WIDTH,
        height: DEFAULT_OG_IMAGE_HEIGHT,
        type: DEFAULT_OG_IMAGE_TYPE,
        alt: 'Свой альт',
      },
    ]);
  });

  it('константы описывают один и тот же файл', () => {
    expect(DEFAULT_OG_IMAGE_META).toMatchObject({
      url: DEFAULT_OG_IMAGE,
      width: DEFAULT_OG_IMAGE_WIDTH,
      height: DEFAULT_OG_IMAGE_HEIGHT,
      type: DEFAULT_OG_IMAGE_TYPE,
    });
  });
});

describe('buildMetadata: чужие картинки', () => {
  it('не приписывает размеры чужому URL, переданному строкой', () => {
    const metadata = buildMetadata({ ...base, image: 'http://example.com/article.jpg' });

    expect(metadata.openGraph?.images).toEqual(['http://example.com/article.jpg']);
  });

  it('не приписывает размеры чужому URL, переданному объектом', () => {
    const metadata = buildMetadata({
      ...base,
      image: { url: 'http://example.com/article.jpg', alt: 'Обложка статьи' },
    });

    expect(metadata.openGraph?.images).toEqual([
      { url: 'http://example.com/article.jpg', alt: 'Обложка статьи' },
    ]);
  });

  it('при image: null не отдаёт картинку вовсе', () => {
    const metadata = buildMetadata({ ...base, image: null });

    expect(metadata.openGraph?.images).toBeUndefined();
    expect(metadata.twitter?.images).toBeUndefined();
  });
});

describe('buildMetadata: twitter', () => {
  it('оставляет twitter.images массивом строк для картинки по умолчанию', () => {
    const metadata = buildMetadata(base);

    expect(metadata.twitter?.images).toEqual([DEFAULT_OG_IMAGE]);
  });

  it('оставляет twitter.images массивом строк для чужой картинки-объекта', () => {
    const metadata = buildMetadata({
      ...base,
      image: { url: 'http://example.com/article.jpg', alt: 'Обложка статьи' },
    });

    expect(metadata.twitter?.images).toEqual(['http://example.com/article.jpg']);
  });
});

describe('buildMetadata: неизменность прочего контракта', () => {
  it('не добавляет robots, пока не запрошен noIndex', () => {
    expect(buildMetadata(base).robots).toBeUndefined();
    expect(buildMetadata({ ...base, noIndex: true }).robots).toEqual({
      index: false,
      follow: false,
    });
  });

  it('сохраняет canonical и базовые поля openGraph', () => {
    const metadata = buildMetadata(base);

    expect(metadata.alternates?.canonical).toBe('/some-page');
    expect(metadata.openGraph).toMatchObject({
      title: 'Заголовок',
      description: 'Описание',
      url: '/some-page',
      type: 'website',
    });
  });
});

describe('buildMetadata: фактические размеры картинки по умолчанию неотменяемы', () => {
  it('игнорирует переданные вызывающим width/height/type для картинки по умолчанию', () => {
    // Габариты `/image.jpg` — свойство файла, а не мнение вызывающего.
    // Прежний эталон 1200×630 живёт в старом коде и в чужих памятках; если
    // страница передаст его объектом, метатеги обязаны остаться правдивыми.
    const metadata = buildMetadata({
      ...base,
      image: { url: DEFAULT_OG_IMAGE, width: 1200, height: 630, type: 'image/png' },
    });

    expect(metadata.openGraph?.images).toEqual([
      {
        url: DEFAULT_OG_IMAGE,
        width: DEFAULT_OG_IMAGE_WIDTH,
        height: DEFAULT_OG_IMAGE_HEIGHT,
        type: DEFAULT_OG_IMAGE_TYPE,
        alt: DEFAULT_OG_IMAGE_META.alt,
      },
    ]);
  });

  it('по-прежнему разрешает переопределить только alt', () => {
    const metadata = buildMetadata({
      ...base,
      image: { url: DEFAULT_OG_IMAGE, alt: 'Свой альт', width: 999 },
    });

    expect(metadata.openGraph?.images).toEqual([
      { ...DEFAULT_OG_IMAGE_META, alt: 'Свой альт' },
    ]);
  });
});

describe('SITE_URL: хвостовой слэш', () => {
  // Снятие подмены окружения и сброс кеша модулей — только здесь: если делать
  // это в конце теста, после assertions, то первое же падение оставит
  // NEXT_PUBLIC_APP_URL подменённым и утащит за собой соседние тесты,
  // спрятав первопричину за каскадом чужих ошибок.
  afterEach(() => {
    vi.unstubAllEnvs();
    vi.resetModules();
  });

  it('normalizeSiteUrl срезает хвостовые слэши', () => {
    expect(normalizeSiteUrl('https://optisport.ru/')).toBe('https://optisport.ru');
    expect(normalizeSiteUrl('https://optisport.ru///')).toBe('https://optisport.ru');
    expect(normalizeSiteUrl('https://optisport.ru')).toBe('https://optisport.ru');
    expect(normalizeSiteUrl('http://localhost:3000/')).toBe('http://localhost:3000');
  });

  it('absoluteUrl не даёт двойного слэша при SITE_URL с хвостовым слэшем', async () => {
    vi.resetModules();
    vi.stubEnv('NEXT_PUBLIC_APP_URL', 'https://optisport.ru/');

    const seo = await import('../seo');

    expect(seo.SITE_URL).toBe('https://optisport.ru');
    expect(seo.absoluteUrl('/LOGO_OPTIsport.png')).toBe('https://optisport.ru/LOGO_OPTIsport.png');
  });

  it('идентификаторы узлов JSON-LD не получают двойного слэша', async () => {
    vi.resetModules();
    vi.stubEnv('NEXT_PUBLIC_APP_URL', 'https://optisport.ru/');

    const organization = await import('@/config/organization');

    expect(organization.ORGANIZATION_ID).toBe('https://optisport.ru/#organization');
    expect(organization.WEBSITE_ID).toBe('https://optisport.ru/#website');
    expect(organization.ORGANIZATION_JSON_LD.logo.url).toBe(
      'https://optisport.ru/LOGO_OPTIsport.png'
    );
  });

});
