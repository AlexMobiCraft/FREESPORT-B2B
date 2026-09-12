import type { Metadata } from 'next';

import { buildMetadata } from '@/utils/seo';

// Сама страница каталога — клиентский компонент ('use client'), экспортировать
// metadata из неё нельзя, поэтому SEO-теги живут в этом layout.
export const metadata: Metadata = buildMetadata({
  title: 'Каталог спортивных товаров | OPTISPORT',
  description:
    'Каталог спортивных товаров: фитнес и атлетика, единоборства, спортивные игры, плавание, туризм. Оптовые и розничные цены, доставка по России.',
  keywords: 'каталог спортивных товаров, спортинвентарь оптом, спортивная экипировка',
  path: '/catalog',
  image: '/image.jpg',
});

export default function CatalogLayout({ children }: { children: React.ReactNode }) {
  return children;
}
