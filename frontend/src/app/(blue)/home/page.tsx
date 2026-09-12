import type { Metadata } from 'next';
import { HomePage } from '@/components/home/HomePage';
import brandsService from '@/services/brandsService';
import { buildMetadata } from '@/utils/seo';
import type { Brand } from '@/types/api';

export const metadata: Metadata = buildMetadata({
  title: 'Спортивные товары оптом и в розницу',
  description:
    'Платформа для оптовых и розничных продаж спортивных товаров. Широкий ассортимент, выгодные условия для бизнеса.',
  keywords: 'спортивные товары оптом, спортивные товары в розницу, спортивная экипировка',
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
