import type { Metadata } from 'next';

import { buildMetadata } from '@/utils/seo';

// Сама страница регистрации — клиентский компонент ('use client'), экспортировать
// metadata из неё нельзя, поэтому SEO-теги живут в этом layout
// (тот же приём, что и в login/layout.tsx).
//
// noIndex не ставится: адрес закрыт Disallow в robots.txt, а такие адреса
// meta noindex не несут (решение D4) — робот страницу не читает и тег не увидит.
export const metadata: Metadata = buildMetadata({
  title: 'Регистрация | OPTISPORT',
  description:
    'Заявка на аккаунт OPTISPORT для оптовых покупателей, тренеров, спортивных клубов и федераций. Доступ к ценам откроется после проверки заявки.',
  path: '/register',
});

export default function RegisterLayout({ children }: { children: React.ReactNode }) {
  return children;
}
