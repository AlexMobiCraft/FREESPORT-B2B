/**
 * SEO-хелперы для метаданных страниц.
 *
 * Собирает единообразный набор тегов: canonical, Open Graph (включая url, siteName,
 * locale, type) и Twitter Card. Пути передаются относительными — `metadataBase`
 * из корневого layout разворачивает их в абсолютные URL.
 */

import type { Metadata } from 'next';

/**
 * Срезает хвостовые слэши базового адреса. Значение приходит из окружения
 * (`NEXT_PUBLIC_APP_URL`), а там `https://optisport.ru/` пишут так же часто,
 * как `https://optisport.ru`. Без нормализации `absoluteUrl` и идентификаторы
 * узлов JSON-LD получают двойной слэш: `https://optisport.ru//#organization`.
 */
export function normalizeSiteUrl(url: string): string {
  return url.replace(/\/+$/, '');
}

export const SITE_URL = normalizeSiteUrl(
  process.env.NEXT_PUBLIC_APP_URL || 'http://localhost:3000'
);
export const SITE_NAME = 'OPTISPORT';
export const OG_LOCALE = 'ru_RU';
export const DEFAULT_OG_IMAGE = '/image.jpg';

/**
 * Фактические параметры файла public/image.jpg. Меняются вместе с файлом —
 * расхождение ловит тест-страж соцпревью в src/__tests__/.
 */
export const DEFAULT_OG_IMAGE_WIDTH = 1040;
export const DEFAULT_OG_IMAGE_HEIGHT = 680;
export const DEFAULT_OG_IMAGE_TYPE = 'image/jpeg';

/**
 * Готовый объект соцпревью по умолчанию. Next разворачивает его в
 * `og:image`, `og:image:width`, `og:image:height`, `og:image:type` и
 * `og:image:alt`; голая строка дала бы только `og:image`.
 */
export const DEFAULT_OG_IMAGE_META = {
  url: DEFAULT_OG_IMAGE,
  width: DEFAULT_OG_IMAGE_WIDTH,
  height: DEFAULT_OG_IMAGE_HEIGHT,
  type: DEFAULT_OG_IMAGE_TYPE,
  alt: 'OPTISPORT — платформа продаж спортивных товаров',
} as const;

export interface PageSeoOptions {
  /** Заголовок страницы (он же og:title / twitter:title) */
  title: string;
  /** Описание (оно же og:description / twitter:description) */
  description: string;
  /** Канонический путь от корня сайта, например `/about` */
  path: string;
  /**
   * Заголовок для соцсетей, если он должен отличаться от `title`.
   * Карточки товаров и статей шерятся без суффикса «| FREESPORT».
   */
  ogTitle?: string;
  /** Описание для соцсетей, если оно должно отличаться от `description` */
  ogDescription?: string;
  keywords?: string;
  /**
   * Картинка для соцсетей. `null` — отдать превью без картинки.
   *
   * Размеры передавать не нужно: картинке по умолчанию их подставляет сама
   * `buildMetadata`, а у чужих изображений они неизвестны.
   */
  image?:
    | string
    | { url: string; alt?: string; width?: number; height?: number; type?: string }
    | null;
  /**
   * Тип Open Graph: `website` по умолчанию. Типы Next.js не включают `product`,
   * поэтому карточки товаров остаются `website`.
   */
  ogType?: 'website' | 'article';
  /** Закрыть страницу от индексации (корзина, оформление, личный кабинет) */
  noIndex?: boolean;
  /** Дополнительные поля Open Graph — например `publishedTime` для статей */
  openGraphExtra?: Record<string, unknown>;
}

/**
 * Нормализует путь к виду `/path` без хвостового слэша (кроме корня).
 */
export function normalizePath(path: string): string {
  if (!path || path === '/') return '/';
  const withLeadingSlash = path.startsWith('/') ? path : `/${path}`;
  return withLeadingSlash.length > 1 && withLeadingSlash.endsWith('/')
    ? withLeadingSlash.slice(0, -1)
    : withLeadingSlash;
}

/**
 * Абсолютный URL для случаев, где относительный путь не подходит
 * (sitemap, JSON-LD).
 */
export function absoluteUrl(path: string): string {
  return `${SITE_URL}${normalizePath(path)}`;
}

/**
 * Дополняет размерами ровно картинку по умолчанию: габариты чужих
 * изображений (карточки товара, обложки статей) нам неизвестны.
 */
function withDefaultImageMeta(image: NonNullable<PageSeoOptions['image']>) {
  const url = typeof image === 'string' ? image : image.url;
  if (url !== DEFAULT_OG_IMAGE) return image;
  if (typeof image === 'string') return DEFAULT_OG_IMAGE_META;

  // Габариты и MIME-тип — свойства файла, а не мнение вызывающего: значения
  // из констант ставятся ПОСЛЕ разворачивания `image`, поэтому переданный
  // страницей `width: 1200` не может сделать метатеги лживыми. Всё остальное
  // (прежде всего `alt`) вызывающий переопределяет свободно.
  return {
    ...DEFAULT_OG_IMAGE_META,
    ...image,
    width: DEFAULT_OG_IMAGE_WIDTH,
    height: DEFAULT_OG_IMAGE_HEIGHT,
    type: DEFAULT_OG_IMAGE_TYPE,
  };
}

export function buildMetadata({
  title,
  description,
  path,
  ogTitle,
  ogDescription,
  keywords,
  image = DEFAULT_OG_IMAGE,
  ogType = 'website',
  noIndex = false,
  openGraphExtra,
}: PageSeoOptions): Metadata {
  const canonical = normalizePath(path);
  const images = image ? [withDefaultImageMeta(image)] : undefined;
  // Twitter не понимает объект с alt — для него оставляем только URL
  const twitterImages = images?.map(i => (typeof i === 'string' ? i : i.url));
  const normalizedTitle = title.replaceAll('FREESPORT', SITE_NAME);
  const normalizedDescription = description.replaceAll('FREESPORT', SITE_NAME);
  const socialTitle = (ogTitle ?? title).replaceAll('FREESPORT', SITE_NAME);
  const socialDescription = (ogDescription ?? description).replaceAll('FREESPORT', SITE_NAME);

  return {
    title: normalizedTitle,
    description: normalizedDescription,
    ...(keywords ? { keywords } : {}),
    alternates: { canonical },
    openGraph: {
      title: socialTitle,
      description: socialDescription,
      url: canonical,
      siteName: SITE_NAME,
      locale: OG_LOCALE,
      type: ogType,
      ...(images ? { images } : {}),
      ...(openGraphExtra ?? {}),
    },
    twitter: {
      card: twitterImages ? 'summary_large_image' : 'summary',
      title: socialTitle,
      description: socialDescription,
      ...(twitterImages ? { images: twitterImages } : {}),
    },
    ...(noIndex ? { robots: { index: false, follow: false } } : {}),
  };
}
