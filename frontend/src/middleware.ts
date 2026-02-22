/**
 * Next.js Middleware - защита маршрутов
 *
 * Edge Runtime - совместимый код (только Web APIs)
 * Проверяет authenticated routes и редиректит неавторизованных пользователей на /login
 */

import { NextResponse } from 'next/server';
import type { NextRequest } from 'next/server';
import { isSafeRedirectUrl } from '@/utils/urlUtils';

/**
 * Проверяет, является ли маршрут защищенным
 */
function isProtectedRoute(pathname: string): boolean {
  const protectedPaths = ['/profile', '/orders', '/b2b-dashboard'];
  return protectedPaths.some(path => pathname.startsWith(path));
}

/**
 * Проверяет, является ли маршрут публичным (auth routes)
 */
function isAuthRoute(pathname: string): boolean {
  const authPaths = ['/login', '/register', '/password-reset', '/b2b-register'];
  return authPaths.some(path => pathname.startsWith(path));
}

/**
 * Middleware function
 */
export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;

  // Проверяем наличие refresh token в cookies
  // ВАЖНО: В Edge Runtime нет доступа к localStorage, используем cookies
  const refreshToken = request.cookies.get('refreshToken')?.value;
  const isAuthenticated = !!refreshToken;

  // Если это protected route и пользователь не авторизован - редирект на /login
  if (isProtectedRoute(pathname) && !isAuthenticated) {
    const url = request.nextUrl.clone();
    url.pathname = '/login';

    // Сохраняем исходный путь для редиректа после входа
    // НЕ добавляем next параметр, если уже на /login (предотвращение бесконечного редиректа)
    if (pathname !== '/login') {
      url.searchParams.set('next', pathname);
    }

    return NextResponse.redirect(url);
  }

  // Если пользователь авторизован и пытается открыть auth route - редирект на главную
  if (isAuthRoute(pathname) && isAuthenticated) {
    const url = request.nextUrl.clone();
    const nextParam = url.searchParams.get('next') || url.searchParams.get('redirect');

    // Если есть next/redirect параметр и он валидный
    if (isSafeRedirectUrl(nextParam)) {
      return NextResponse.redirect(new URL(nextParam!, request.url));
    }

    url.pathname = '/';
    return NextResponse.redirect(url);
  }

  return NextResponse.next();
}

/**
 * Matcher config - определяет маршруты, к которым применяется middleware
 *
 * ВАЖНО: Matcher запускается для ВСЕХ указанных путей
 * Внутри middleware мы делаем дополнительную проверку
 */
export const config = {
  matcher: [
    /*
     * Match all request paths except for:
     * - _next/static (static files)
     * - _next/image (image optimization)
     * - favicon.ico (favicon)
     * - public folder
     * - API routes (handled separately)
     */
    '/((?!_next/static|_next/image|favicon.ico|.*\\..*|api/).*)',
  ],
};
