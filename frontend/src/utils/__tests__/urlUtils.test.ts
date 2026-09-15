/**
 * Тесты единого предиката допустимости redirect-цели (Story 41.12 — Task 5.4).
 *
 * Таблица закрепляет контракт `isSafeRedirectUrl`: безопасные внутренние
 * адреса, внешние/неоднозначные значения, обратный слэш в декодированном
 * runtime-значении и внутренние auth-route как недопустимую конечную точку.
 *
 * Deferred-префиксы без границы сегмента (`/login-foo`) в таблицу намеренно
 * не включены — их семантика остаётся вне scope стори (AC12).
 */

import { describe, expect, it } from 'vitest';
import { isSafeRedirectUrl } from '../urlUtils';

describe('isSafeRedirectUrl', () => {
  describe('безопасные внутренние адреса', () => {
    it.each(['/', '/checkout', '/profile', '/catalog?category=x', '/delivery#pickup'])(
      '%s → true',
      url => {
        expect(isSafeRedirectUrl(url)).toBe(true);
      }
    );
  });

  describe('внешние и неоднозначные значения', () => {
    it.each([
      'https://evil.com',
      '//evil.com',
      'javascript:alert(1)',
      '',
      null,
      undefined,
      'checkout',
    ])('%s → false', url => {
      expect(isSafeRedirectUrl(url)).toBe(false);
    });
  });

  describe('обратный слэш в декодированном runtime-значении', () => {
    it.each([
      '\\evil.com', // %5Cevil.com
      '/\\evil.com', // %2F%5Cevil.com
      '/catalog\\item', // %2Fcatalog%5Citem
    ])('%s → false', url => {
      expect(isSafeRedirectUrl(url)).toBe(false);
    });
  });

  describe('auth-route как недопустимая конечная точка после входа', () => {
    it.each([
      '/login',
      '/login/',
      '/login/anything',
      '/login?next=%2Fprofile',
      '/register',
      '/register/',
      '/register/anything',
      '/b2b-register',
      '/b2b-register/',
      '/b2b-register/anything',
      '/password-reset',
      '/password-reset/',
      '/password-reset/confirm/u/t',
      '/foo/../login',
    ])('%s → false', url => {
      expect(isSafeRedirectUrl(url)).toBe(false);
    });
  });

  describe('границы контракта', () => {
    it('/login-foo остаётся безопасным — deferred-префикс вне scope (AC12)', () => {
      expect(isSafeRedirectUrl('/login-foo')).toBe(true);
    });
  });
});
