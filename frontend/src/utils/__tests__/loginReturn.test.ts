/**
 * Модуль точки возврата после входа (Story 41.18 — Task 1, AC1–AC3).
 *
 * `resolvePostLoginTarget` без cookie обязан повторять матрицы A и B из 41.12:
 * кандидат из URL — это `next || redirect` целиком, опасный непустой `next`
 * не уступает место `redirect`.
 *
 * Cookie ставится с `Path=/login` и не видна документу на `/`, поэтому
 * проверки чтения идут на документе `/login` (happy-dom).
 */

import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import {
  LOGIN_RETURN_COOKIE,
  LOGIN_RETURN_COOKIE_MAX_AGE,
  LOGIN_RETURN_COOKIE_PATH,
  clearLoginReturnCookie,
  loginReturnCookieOptions,
  readLoginReturnCookie,
  resolvePostLoginTarget,
  writeLoginReturnCookie,
} from '../loginReturn';

/** `next || redirect` так же, как его вычисляют страница входа и middleware. */
function urlCandidate(encoded: string): string | null {
  const params = new URLSearchParams(encoded);
  return params.get('next') || params.get('redirect') || null;
}

describe('константы и атрибуты cookie', () => {
  it('имя, путь и срок жизни', () => {
    expect(LOGIN_RETURN_COOKIE).toBe('loginReturnTo');
    expect(LOGIN_RETURN_COOKIE_PATH).toBe('/login');
    expect(LOGIN_RETURN_COOKIE_MAX_AGE).toBe(600);
  });

  it('loginReturnCookieOptions вне production — без Secure', () => {
    expect(loginReturnCookieOptions()).toEqual({
      path: '/login',
      maxAge: 600,
      sameSite: 'lax',
      secure: false,
      httpOnly: false,
    });
  });
});

describe('resolvePostLoginTarget без cookie — матрицы 41.12 не меняются', () => {
  const matrixA = [
    { encoded: '', expected: '/' },
    { encoded: 'next=', expected: '/' },
    { encoded: 'next=%2F', expected: '/' },
    { encoded: 'next=%2Fcheckout', expected: '/checkout' },
    { encoded: 'next=%2Fprofile', expected: '/profile' },
    { encoded: 'next=%2Fcatalog%3Fcategory%3Dx%23top', expected: '/catalog?category=x#top' },
    { encoded: 'next=https%3A%2F%2Fevil.com', expected: '/' },
    { encoded: 'next=%2F%2Fevil.com', expected: '/' },
    { encoded: 'next=javascript%3Aalert%281%29', expected: '/' },
    { encoded: 'next=%5Cevil.com', expected: '/' },
    { encoded: 'next=%2F%5Cevil.com', expected: '/' },
    { encoded: 'next=%2Fcatalog%5Citem', expected: '/' },
    { encoded: 'next=%2Flogin', expected: '/' },
    { encoded: 'next=%2Fregister%2Fanything', expected: '/' },
    { encoded: 'next=%2Ffoo%2F..%2Flogin', expected: '/' },
  ];

  const matrixB = [
    { encoded: 'next=%2Fcheckout&redirect=%2Fprofile', expected: '/checkout' },
    { encoded: 'next=%2Fprofile&redirect=https%3A%2F%2Fevil.com', expected: '/profile' },
    { encoded: 'next=https%3A%2F%2Fevil.com&redirect=%2Fprofile', expected: '/' },
    { encoded: 'next=%2Flogin%2F&redirect=%2Fprofile', expected: '/' },
    { encoded: 'next=%2F%5Cevil.com&redirect=%2Fprofile', expected: '/' },
    { encoded: 'next=&redirect=%2Fprofile', expected: '/profile' },
    { encoded: 'redirect=%2Fprofile', expected: '/profile' },
    { encoded: 'next=&redirect=', expected: '/' },
  ];

  it.each([...matrixA, ...matrixB])('"$encoded" → $expected', ({ encoded, expected }) => {
    expect(resolvePostLoginTarget(urlCandidate(encoded), null)).toBe(expected);
  });

  it('undefined в обоих кандидатах → "/"', () => {
    expect(resolvePostLoginTarget(undefined, undefined)).toBe('/');
  });
});

describe('resolvePostLoginTarget с cookie', () => {
  it.each([
    { url: '/cart', cookie: '/profile/favorites', expected: '/cart', why: 'URL безопасен → URL' },
    {
      url: 'https://evil.com',
      cookie: '/checkout',
      expected: '/checkout',
      why: 'URL опасен → cookie',
    },
    { url: null, cookie: '/profile/favorites', expected: '/profile/favorites', why: 'URL пуст' },
    { url: '', cookie: '/profile', expected: '/profile', why: 'URL пустая строка' },
    { url: '//evil.com', cookie: '//evil.com', expected: '/', why: 'оба опасны' },
    { url: null, cookie: '/login', expected: '/', why: 'cookie = /login' },
    { url: null, cookie: 'https://evil.com', expected: '/', why: 'cookie чужой origin' },
  ])('$why: ($url, $cookie) → $expected', ({ url, cookie, expected }) => {
    expect(resolvePostLoginTarget(url, cookie)).toBe(expected);
  });
});

describe('запись, чтение и удаление cookie', () => {
  beforeEach(() => {
    window.history.pushState({}, '', '/login');
    clearLoginReturnCookie();
  });

  afterEach(() => {
    window.history.pushState({}, '', '/login');
    clearLoginReturnCookie();
    window.history.pushState({}, '', '/');
  });

  it('запись и чтение на документе /login', () => {
    writeLoginReturnCookie('/profile/favorites');
    expect(document.cookie).toContain(`${LOGIN_RETURN_COOKIE}=%2Fprofile%2Ffavorites`);
    expect(readLoginReturnCookie()).toBe('/profile/favorites');
  });

  it('cookie с Path=/login не видна документу на /', () => {
    writeLoginReturnCookie('/checkout');
    window.history.pushState({}, '', '/');
    expect(document.cookie).not.toContain(LOGIN_RETURN_COOKIE);
    expect(readLoginReturnCookie()).toBeNull();
  });

  it('запись с другой страницы видна на /login (путь cookie явный)', () => {
    window.history.pushState({}, '', '/checkout');
    writeLoginReturnCookie('/checkout');
    window.history.pushState({}, '', '/login');
    expect(readLoginReturnCookie()).toBe('/checkout');
  });

  it.each(['//evil.com', '/login', 'https://evil.com', '/\\evil.com', ''])(
    'небезопасный путь "%s" не записывается',
    path => {
      writeLoginReturnCookie(path);
      expect(document.cookie).not.toContain(LOGIN_RETURN_COOKIE);
      expect(readLoginReturnCookie()).toBeNull();
    }
  );

  it('clearLoginReturnCookie убирает cookie полностью — без пустого значения', () => {
    writeLoginReturnCookie('/profile');
    expect(readLoginReturnCookie()).toBe('/profile');
    clearLoginReturnCookie();
    expect(document.cookie).not.toContain(`${LOGIN_RETURN_COOKIE}=`);
    expect(readLoginReturnCookie()).toBeNull();
  });

  it('битое значение %E0 → null, без исключения', () => {
    document.cookie = `${LOGIN_RETURN_COOKIE}=%E0; Path=/login`;
    expect(() => readLoginReturnCookie()).not.toThrow();
    expect(readLoginReturnCookie()).toBeNull();
  });

  it('чужие cookie с похожим именем не читаются', () => {
    document.cookie = `x${LOGIN_RETURN_COOKIE}=%2Fprofile; Path=/login`;
    expect(readLoginReturnCookie()).toBeNull();
    document.cookie = `x${LOGIN_RETURN_COOKIE}=; Path=/login; Max-Age=-1`;
  });
});
