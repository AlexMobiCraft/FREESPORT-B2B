import { redirect } from 'next/navigation';
import { cookies } from 'next/headers';

const THEME_ROUTES = {
  coming_soon: '/coming-soon',
  blue: '/home',
  electric_orange: '/electric',
} as const;

type ThemeKey = keyof typeof THEME_ROUTES;

// Default fallback theme for authenticated users when coming_soon is active
const AUTHENTICATED_FALLBACK_THEME: ThemeKey = 'blue';

export const dynamic = 'force-dynamic';

export default async function RootPage() {
  const cookieStore = await cookies();
  const refreshToken = cookieStore.get('refreshToken')?.value;
  const isAuthenticated = !!refreshToken;

  const activeTheme = (process.env.ACTIVE_THEME || 'coming_soon') as ThemeKey;

  // Smart redirect: authenticated users bypass 'coming_soon' placeholder
  let targetTheme = activeTheme;
  if (isAuthenticated && activeTheme === 'coming_soon') {
    targetTheme = AUTHENTICATED_FALLBACK_THEME;
  }

  const targetRoute = THEME_ROUTES[targetTheme] || '/coming-soon';
  redirect(targetRoute);
}
