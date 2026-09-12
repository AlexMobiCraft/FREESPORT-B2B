import type { Metadata } from 'next';

import { buildMetadata } from '@/utils/seo';

// Сама страница входа — клиентский компонент ('use client'), экспортировать
// metadata из неё нельзя, поэтому SEO-теги живут в этом layout
// (тот же приём, что и в (blue)/catalog/layout.tsx).
export const metadata: Metadata = buildMetadata({
  title: 'Вход в личный кабинет | OPTISPORT',
  description:
    'Вход в личный кабинет OPTISPORT для оптовых клиентов: заказы, цены по вашей роли, история отгрузок и документы.',
  path: '/login',
  noIndex: true,
});

export default function LoginLayout({ children }: { children: React.ReactNode }) {
  return children;
}
