import type { Metadata } from 'next';
import { HomePage } from '@/components/home/HomePage';
import brandsService from '@/services/brandsService';
import type { Brand } from '@/types/api';

export const metadata: Metadata = {
  title: 'FREESPORT - Спортивные товары оптом и в розницу',
  description:
    'Платформа для оптовых и розничных продаж спортивных товаров. Широкий ассортимент, выгодные условия для бизнеса.',
  keywords:
    'спортивные товары оптом, спортивные товары в розницу, FREESPORT, спортивная экипировка',
  openGraph: {
    title: 'FREESPORT - Спортивные товары оптом и в розницу',
    description:
      'Платформа для оптовых и розничных продаж спортивных товаров. Широкий ассортимент, выгодные условия для бизнеса.',
    images: ['/og-image.jpg'],
  },
  twitter: {
    card: 'summary_large_image',
    title: 'FREESPORT - Спортивные товары оптом и в розницу',
    description:
      'Платформа для оптовых и розничных продаж спортивных товаров. Широкий ассортимент, выгодные условия для бизнеса.',
    images: ['/og-image.jpg'],
  },
};

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
