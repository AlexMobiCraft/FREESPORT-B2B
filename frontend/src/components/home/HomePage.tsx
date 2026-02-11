/**
 * HomePage - Главная страница
 *
 * Порядок секций:
 * 1. HeroSection (баннеры)
 * 2. HitsSection (хиты продаж)
 * 3. NewArrivalsSection (новинки)
 * 4. PromoSection (акция)
 * 5. SaleSection (распродажа)
 * 6. NewsSection (новости)
 * 7. BlogSection (блог)
 * 8. SubscribeNewsSection (подписка)
 * 9. WhyFreesportSection (почему выбирают)
 * 10. DeliveryTeaser (доставка)
 * 11. AboutTeaser (FREESPORT + ценности)
 */

'use client';

import React from 'react';
import {
  HeroSection,
  HitsSection,
  NewArrivalsSection,
  PromoSection,
  SaleSection,
  NewsSection,
  BlogSection,
  SubscribeNewsSection,
  WhyFreesportSection,
  DeliveryTeaser,
  AboutTeaser,
  CategoriesSection,
} from '@/components/home';

export const HomePage: React.FC = () => {
  return (
    <main className="min-h-screen bg-white">
      {/* 1. Hero Section - Баннеры */}
      <HeroSection />

      {/* 2. Popular Categories - Популярные категории */}
      <CategoriesSection />

      {/* 2. Hits Section - Хиты продаж */}
      <HitsSection />

      {/* 3. New Arrivals Section - Новинки */}
      <NewArrivalsSection />

      {/* 4. Promo Section - Акция */}
      <PromoSection />

      {/* 5. Sale Section - Распродажа */}
      <SaleSection />

      {/* 6. News Section - Новости */}
      <NewsSection />

      {/* 7. Blog Section - Наш блог */}
      <BlogSection />

      {/* 8. Subscribe Section - Подписка на новости */}
      <SubscribeNewsSection />

      {/* 9. Why FREESPORT Section */}
      <WhyFreesportSection />

      {/* 10. Delivery Teaser - Доставка по России */}
      <DeliveryTeaser />

      {/* 11. About Teaser - FREESPORT + Наши ценности */}
      <AboutTeaser />

      {/* Footer рендерится в layout */}
    </main>
  );
};

export default HomePage;
