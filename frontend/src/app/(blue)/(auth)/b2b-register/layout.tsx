import type { Metadata } from 'next';

import { buildMetadata } from '@/utils/seo';

// Сама страница регистрации компании — клиентский компонент ('use client'),
// экспортировать metadata из неё нельзя, поэтому SEO-теги живут в этом layout
// (тот же приём, что и в login/layout.tsx).
//
// noIndex не ставится: адрес закрыт Disallow в robots.txt, а такие адреса
// meta noindex не несут (решение D4) — робот страницу не читает и тег не увидит.
export const metadata: Metadata = buildMetadata({
  title: 'Регистрация компании | OPTISPORT',
  description:
    'Заявка на оптовый аккаунт OPTISPORT для организаций и ИП: контактное лицо и реквизиты компании. Оптовые цены откроются после проверки заявки.',
  path: '/b2b-register',
});

export default function B2BRegisterLayout({ children }: { children: React.ReactNode }) {
  return children;
}
