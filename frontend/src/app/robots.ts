import type { MetadataRoute } from 'next';

import { SITE_URL } from '@/utils/seo';

/**
 * robots.txt для поисковых роботов.
 *
 * Без этого файла запрос `/robots.txt` проваливался в catch-all роут CMS-страниц
 * `(blue)/[slug]` и отдавал HTML со статусом 200.
 */
export default function robots(): MetadataRoute.Robots {
  return {
    rules: [
      {
        userAgent: '*',
        allow: '/',
        disallow: [
          '/api/',
          '/admin/',
          '/cart',
          '/checkout',
          '/profile',
          '/search',
          '/login',
          '/register',
          '/b2b-register',
          '/password-reset',
          '/portal-link',
          '/coming-soon',
          // Витрины альтернативной темы и демо-страницы — не для индекса
          '/electric',
          '/electric-orange-test',
          '/design-comparison',
          '/examples',
          '/test',
        ],
      },
    ],
    sitemap: `${SITE_URL}/sitemap.xml`,
    host: SITE_URL,
  };
}
