/**
 * Данные организации для разметки schema.org (Story 41.6).
 *
 * Контакты берутся из `contacts.ts` — второй копии телефона и почты здесь
 * не заводится. Абсолютные URL строятся только из `SITE_URL`/`absoluteUrl`:
 * локально это `http://localhost:3000`, на проде — значение `SITE_URL` из
 * окружения. Локальный JSON-LD с `localhost` — ожидаемое поведение, а не дефект.
 */

import { SUPPORT_EMAIL, SUPPORT_PHONE_DISPLAY } from './contacts';
import { SITE_NAME, SITE_URL, absoluteUrl } from '@/utils/seo';

/** Идентификаторы узлов графа: связывают WebSite с Organization */
export const ORGANIZATION_ID = `${SITE_URL}/#organization`;
export const WEBSITE_ID = `${SITE_URL}/#website`;

/**
 * Соцсети организации — те же три адреса, что в подвале (`Footer.tsx`,
 * `DEFAULT_SOCIAL_LINKS`). Мёртвая ссылка здесь хуже отсутствия `sameAs`,
 * поэтому список правится вместе с подвалом, а не отдельно от него.
 */
export const ORGANIZATION_SAME_AS = [
  'https://vk.com/optisport',
  'https://t.me/optisport',
  'https://youtube.com/@optisport',
];

/**
 * Узел Organization. Размеры логотипа — фактические параметры файла
 * `public/LOGO_OPTIsport.png` (1014×101).
 */
export const ORGANIZATION_JSON_LD = {
  '@type': 'Organization',
  '@id': ORGANIZATION_ID,
  name: SITE_NAME,
  url: SITE_URL,
  logo: {
    '@type': 'ImageObject',
    url: absoluteUrl('/LOGO_OPTIsport.png'),
    width: 1014,
    height: 101,
  },
  email: SUPPORT_EMAIL,
  telephone: SUPPORT_PHONE_DISPLAY,
  address: {
    '@type': 'PostalAddress',
    addressCountry: 'RU',
    addressLocality: 'Ставрополь',
    streetAddress: 'ул. Коломийцева, 40/1',
  },
  sameAs: ORGANIZATION_SAME_AS,
};

/**
 * Узел WebSite. `potentialAction`/`SearchAction` намеренно отсутствует:
 * `/search` перечислен в `Disallow` (`app/robots.ts`), а sitelinks searchbox
 * требует индексируемую страницу результатов.
 */
export const WEBSITE_JSON_LD = {
  '@type': 'WebSite',
  '@id': WEBSITE_ID,
  name: SITE_NAME,
  url: SITE_URL,
  inLanguage: 'ru-RU',
  publisher: { '@id': ORGANIZATION_ID },
};
