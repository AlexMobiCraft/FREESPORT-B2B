/**
 * HomePage - Главная страница
 *
 * Порядок секций:
 * 1. HeroSection (баннеры)
 * 2. QuickLinksSection (быстрые ссылки)
 * 3. MarketingBannersSection (маркетинговые баннеры)
 * 4. BrandsBlock (популярные бренды)
 * 5. CategoriesSection (популярные категории)
 * 6. AboutTeaser (О нас)
 * 7. HitsSection (хиты продаж)
 * 8. NewArrivalsSection (новинки)
 * 9. PromoSection (акция)
 * 10. SaleSection (распродажа)
 * 11. NewsSection (новости)
 * 12. WhyFreesportSection (почему выбирают)
 * 13. SubscribeNewsSection (подписка)
 * 14. DeliveryTeaser (доставка)
 */

'use client';

import React from 'react';
import {
  HeroSection,
  QuickLinksSection,
  MarketingBannersSection,
  HitsSection,
  NewArrivalsSection,
  PromoSection,
  SaleSection,
  NewsSection,
  SubscribeNewsSection,
  WhyFreesportSection,
  DeliveryTeaser,
  AboutTeaser,
  CategoriesSection,
} from '@/components/home';
import { BrandsBlock } from '@/components/business/home/BrandsBlock';
import type { Brand } from '@/types/api';

interface HomePageProps {
  featuredBrands: Brand[];
}

export const HomePage: React.FC<HomePageProps> = ({ featuredBrands }) => {
  return (
    <main className="min-h-screen bg-white">
      {/* 1. Hero Section - Баннеры */}
      <HeroSection />

      {/* 2. Quick Links - Быстрые ссылки */}
      <QuickLinksSection />

      {/* 3. Marketing Banners - Маркетинговые баннеры */}
      <MarketingBannersSection />

      {/* 4. Brands Block - Популярные бренды */}
      {featuredBrands.length > 0 && <BrandsBlock brands={featuredBrands} />}

      {/* 5. Popular Categories - Популярные категории */}
      <CategoriesSection />

      {/* 6. About Teaser - О нас (Перемещен под категории) */}
      <AboutTeaser />

      {/* 7. Hits Section - Хиты продаж */}
      <HitsSection />

      {/* 8. New Arrivals Section - Новинки */}
      <NewArrivalsSection />

      {/* 9. Promo Section - Акция */}
      <PromoSection />

      {/* 10. Sale Section - Распродажа */}
      <SaleSection />

      {/* 11. News Section - Новости */}
      <NewsSection />

      {/* 12. Why FREESPORT Section (Перемещен под новости) */}
      <WhyFreesportSection />

      {/* 13. Subscribe Section - Подписка на новости */}
      <SubscribeNewsSection />

      {/* 14. Delivery Teaser - Доставка по России */}
      <DeliveryTeaser />

      {/* Footer рендерится в layout */}
    </main>
  );
};

export default HomePage;
