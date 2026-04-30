import { describe, it, expect, vi, beforeEach } from 'vitest';
import { middleware } from '../middleware';
import { NextRequest, NextResponse } from 'next/server';

// Mock NextResponse
vi.mock('next/server', async () => {
  const actual = await vi.importActual('next/server');
  return {
    ...actual,
    NextResponse: {
      next: vi.fn(),
      redirect: vi.fn(),
    },
  };
});

describe('Middleware', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  const createRequest = (pathname: string, hasToken: boolean = false, nextParam?: string) => {
    const url = new URL(`http://localhost:3000${pathname}`);
    if (nextParam) {
      url.searchParams.set('next', nextParam);
    }

    const req = {
      nextUrl: url,
      cookies: {
        get: (name: string) =>
          name === 'refreshToken' && hasToken ? { value: 'token' } : undefined,
      },
      url: url.toString(),
    } as unknown as NextRequest;

    // Helper needed because NextRequest clone() is complex to mock fully
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    req.nextUrl.clone = () => new URL(url.toString()) as any;

    return req;
  };

  it('redirects unauthenticated user to login when accessing protected route', () => {
    const req = createRequest('/profile');
    middleware(req);

    expect(NextResponse.redirect).toHaveBeenCalled();
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const redirectUrl = (NextResponse.redirect as any).mock.calls[0][0];
    expect(redirectUrl.pathname).toBe('/login');
    expect(redirectUrl.searchParams.get('next')).toBe('/profile');
  });

  it('allows authenticated user to access protected route', () => {
    const req = createRequest('/profile', true);
    middleware(req);

    expect(NextResponse.next).toHaveBeenCalled();
  });

  it('redirects authenticated user to home from auth page when no next param', () => {
    const req = createRequest('/login', true);
    middleware(req);

    expect(NextResponse.redirect).toHaveBeenCalled();
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const redirectUrl = (NextResponse.redirect as any).mock.calls[0][0];
    expect(redirectUrl.pathname).toBe('/');
  });

  it('redirects authenticated user to next param url from auth page', () => {
    const req = createRequest('/login', true, '/cart');
    middleware(req);

    expect(NextResponse.redirect).toHaveBeenCalled();
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const callArgs = (NextResponse.redirect as any).mock.calls[0];
    // NextResponse.redirect(new URL(...))
    const redirectUrl = callArgs[0];
    expect(redirectUrl.pathname).toBe('/cart');
  });

  it('redirects authenticated user to redirect param url from auth page', () => {
    const url = new URL('http://localhost:3000/login');
    url.searchParams.set('redirect', '/checkout');
    const req = {
      nextUrl: url,
      cookies: {
        get: (name: string) => (name === 'refreshToken' ? { value: 'token' } : undefined),
      },
      url: url.toString(),
    } as unknown as NextRequest;
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    req.nextUrl.clone = () => new URL(url.toString()) as any;

    middleware(req);

    expect(NextResponse.redirect).toHaveBeenCalled();
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const redirectUrl = (NextResponse.redirect as any).mock.calls[0][0];
    expect(redirectUrl.pathname).toBe('/checkout');
  });

  it('sanitizes next param: redirects to home if next param is external domain', () => {
    const req = createRequest('/login', true, '//google.com');
    middleware(req);

    expect(NextResponse.redirect).toHaveBeenCalled();
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const redirectUrl = (NextResponse.redirect as any).mock.calls[0][0];
    expect(redirectUrl.pathname).toBe('/');
  });

  it('sanitizes next param: redirects to home if next param does not start with /', () => {
    const req = createRequest('/login', true, 'javascript:alert(1)');
    middleware(req);

    expect(NextResponse.redirect).toHaveBeenCalled();
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const redirectUrl = (NextResponse.redirect as any).mock.calls[0][0];
    expect(redirectUrl.pathname).toBe('/');
  });
});
