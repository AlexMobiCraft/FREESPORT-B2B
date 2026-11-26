import type { Metadata } from 'next';
import { HomePage } from '@/components/home/HomePage';
import brandsService from '@/services/brandsService';
import { buildMetadata } from '@/utils/seo';
import type { Brand } from '@/types/api';

export const metadata: Metadata = buildMetadata({
  title: 'Спортивные товары оптом — каталог и условия | OPTISPORT',
  description:
    'Оптовые поставки спортивных товаров для магазинов, спортивных клубов и федераций: каталог, цены для оптовых покупателей, доставка по России.',
  // Корневой `/` редиректит на `/home`, поэтому канонический адрес главной — `/home`
  path: '/home',
});

export const revalidate = 3600; // ISR: обновление каждый час

export default async function BlueHomePage() {
  let featuredBrands: Brand[] = [];
  try {
    featuredBrands = await brandsService.getFeatured();
  } catch (error) {
    console.error('[BlueHomePage] Failed to fetch featured brands:', error);
  }

  return <HomePage featuredBrands={featuredBrands} />;
}
