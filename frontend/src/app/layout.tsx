import type { Metadata } from 'next';
import { Inter, Roboto_Condensed } from 'next/font/google';

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

export const metadata: Metadata = {
  title: 'FREESPORT Platform | B2B/B2C спортивные товары',
  description:
    'Ведущая платформа продаж спортивных товаров. B2B/B2C решения для тренеров, федераций и дистрибьюторов.',
  keywords: 'спорт, товары, оптом, B2B, B2C, тренажеры, спортивный инвентарь',
  metadataBase: new URL(appUrl),
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="ru" suppressHydrationWarning>
      <body className={`${inter.variable} ${robotoCondensed.variable} font-sans antialiased`}>
        {children}
      </body>
    </html>
  );
}
