/**
 * Контакты службы поддержки OPTISPORT.
 *
 * Единая точка правды для нового кода (Story 41.4). Значения взяты дословно
 * из подвала темы blue (`Footer.tsx`) — они уже отребрендены на OPTISPORT.
 *
 * Существующие места хардкода (`Footer.tsx`, `ElectricFooter.tsx`,
 * `delivery/page.tsx`, `ComingSoonClient.tsx`) сознательно НЕ мигрируются
 * в рамках 41.4 — миграция вынесена в deferred-work.
 */

/** Телефон поддержки в человекочитаемом виде */
export const SUPPORT_PHONE_DISPLAY = '8 800 700 70 89';

/** Телефон поддержки для атрибута href */
export const SUPPORT_PHONE_HREF = 'tel:88007007089';

/** Электронная почта поддержки */
export const SUPPORT_EMAIL = 'info@optisport.ru';
