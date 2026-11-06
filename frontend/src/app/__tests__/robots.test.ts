/**
 * robots.txt (стори 41.19, AC2).
 *
 * Демо-маршруты удалены из репозитория и отдают настоящий 404, поэтому в
 * `Disallow` им больше не место. Полный список закреплён снимком: 41.18 читает
 * его в тесте инварианта D4, и любое изменение должно быть осознанным.
 */

import { describe, it, expect } from 'vitest';

import robots from '../robots';

type Rule = { userAgent?: string | string[]; disallow?: string | string[] };

function getDisallow(): string[] {
  const { rules } = robots();
  const list = (Array.isArray(rules) ? rules : [rules]) as Rule[];
  expect(list).toHaveLength(1);
  expect(list[0].userAgent).toBe('*');
  const { disallow } = list[0];
  return Array.isArray(disallow) ? disallow : disallow ? [disallow] : [];
}

describe('robots', () => {
  it.each(['/electric-orange-test', '/design-comparison', '/examples', '/test'])(
    'не закрывает удалённый демо-маршрут %s',
    path => {
      expect(getDisallow()).not.toContain(path);
    }
  );

  it.each(['/electric', '/register', '/b2b-register'])('закрывает %s', path => {
    expect(getDisallow()).toContain(path);
  });

  it('список Disallow совпадает со снимком', () => {
    expect(getDisallow()).toEqual([
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
      '/electric',
    ]);
  });
});
