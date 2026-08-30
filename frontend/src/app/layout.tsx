import type { Metadata } from 'next';
import { Inter, Roboto_Condensed } from 'next/font/google';
import CookieConsentBanner from '@/components/layout/CookieConsentBanner';
import { DEFAULT_OG_IMAGE, OG_LOCALE, SITE_NAME } from '@/utils/seo';

const inter = Inter({
  variable: '--font-inter',
  subsets: ['latin', 'cyrillic'],
});

const robotoCondensed = Roboto_Condensed({
  variable: '--font-roboto-condensed',
  subsets: ['latin', 'cyrillic'],
  weight: ['400', '700', '900'],
  style: ['normal'],
});

const appUrl = process.env.NEXT_PUBLIC_APP_URL || 'http://localhost:3000';

const title = 'OPTISPORT Platform | B2B/B2C спортивные товары';
const description =
  'Ведущая платформа продаж спортивных товаров. B2B/B2C решения для тренеров, федераций и дистрибьюторов.';

export const metadata: Metadata = {
  title,
  description,
  keywords: 'спорт, товары, оптом, B2B, B2C, тренажеры, спортивный инвентарь',
  metadataBase: new URL(appUrl),
  // Базовые og/twitter-теги для страниц, которые не задают свои.
  // Страница со своим openGraph перекрывает этот блок целиком.
  openGraph: {
    title,
    description,
    siteName: SITE_NAME,
    locale: OG_LOCALE,
    type: 'website',
    images: [DEFAULT_OG_IMAGE],
  },
  twitter: {
    card: 'summary_large_image',
    title,
    description,
    images: [DEFAULT_OG_IMAGE],
  },
};

/**
 * Дефолт кэширования для всего дерева маршрутов (стори 41.5).
 *
 * Без него статически пререндеренные страницы отдавали `Cache-Control:
 * s-maxage=31536000` — год в общем кэше. Для `/coming-soon` это означало, что
 * после запуска сайта посетитель мог год получать заглушку «Скоро открытие».
 *
 * Правится именно здесь, а не заголовком в next.config.ts: `Cache-Control`,
 * заданный в конфиге, Next в production перезаписывает. Рычаг — сегментная
 * опция `revalidate`.
 *
 * Значение действует как потолок по умолчанию; для маршрута берётся наименьшее
 * значение по дереву сегментов, поэтому страницы со своим `revalidate`
 * ((blue)/home, (electric)/electric) и с `dynamic = 'force-dynamic'` (app/page)
 * сохраняют прежнее поведение.
 */
export const revalidate = 3600;

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="ru" suppressHydrationWarning>
      <body className={`${inter.variable} ${robotoCondensed.variable} font-sans antialiased`}>
        {children}
        <CookieConsentBanner />
      </body>
    </html>
  );
}
