/**
 * Electric Orange Home Page
 *
 * Главная страница OPTISPORT в стиле Electric Orange Design System.
 * Parallel Route для миграции дизайн-системы.
 *
 * Структура (9 секций из спецификации 03-page-specs.md):
 * 1. Hero Баннер
 * 2. Хиты продаж
 * 3. Новинки
 * 4. Акция
 * 5. Распродажа
 * 6. Категории
 * 7. Новости
 * 8. Наш блог
 * 9. Подписка
 *
 * ISR: revalidate = 3600 (1 час)
 */

import type { Metadata } from 'next';

import { buildMetadata } from '@/utils/seo';

// Electric-specific components
import { ElectricHeroSection } from '@/components/home/ElectricHeroSection';
import { ElectricCategorySection } from '@/components/home/ElectricCategorySection';
import { ElectricProductSection } from '@/components/home/ElectricProductSection';

// Refactored components with variant support
import { HitsSection } from '@/components/home/HitsSection';

// Components pending refactoring (temporarily using default style)
// TODO: Refactor these with variant="electric" support
import { NewsSection } from '@/components/home/NewsSection';
import { BlogSection } from '@/components/home/BlogSection';
import { ElectricSubscribeSection } from '@/components/home/ElectricSubscribeSection';

// ISR: ревалидация каждый час
export const revalidate = 3600;

// SEO Metadata: тексты корневого умолчания D7 (стори 41.21, R2). Адрес закрыт
// `Disallow: /electric`, поэтому `noIndex` не ставится (D4 стори 41.18).
export const metadata: Metadata = buildMetadata({
  title: 'OPTISPORT — спортивные товары оптом',
  description:
    'Оптовые продажи спортивных товаров: каталог, условия для оптовых покупателей, доставка по России.',
  path: '/electric',
});

export default function ElectricHomePage() {
  // Единственный <main> страницы рендерит ElectricLayout, здесь — обычный контейнер
  return (
    <div className="bg-[var(--bg-body)] min-h-screen">
      {/* 1. Hero Section — Electric-specific component */}
      <ElectricHeroSection />

      {/* 2. Хиты продаж — Refactored with variant */}
      <HitsSection
        variant="electric"
        title="Лидеры продаж"
        viewAllLink="/electric/catalog?is_hit=true"
      />

      {/* 3. Новинки — Temporary: using ElectricProductSection */}
      {/* TODO: Refactor NewArrivalsSection with variant="electric" */}
      <ElectricProductSection
        title="НОВИНКИ"
        fetchType="new"
        badge="new"
        viewAllLink="/electric/catalog?is_new=true"
        viewAllText="Все новинки"
      />

      {/* 4. Акция — Temporary: using ElectricProductSection */}
      {/* TODO: Refactor PromoSection with variant="electric" */}
      <ElectricProductSection
        title="АКЦИЯ"
        fetchType="promo"
        badge="primary"
        viewAllLink="/electric/catalog?is_promo=true"
        viewAllText="Все акции"
      />

      {/* 5. Распродажа — Temporary: using ElectricProductSection */}
      {/* TODO: Refactor SaleSection with variant="electric" */}
      <ElectricProductSection
        title="РАСПРОДАЖА"
        fetchType="sale"
        badge="sale"
        viewAllLink="/electric/catalog?is_sale=true"
        viewAllText="Вся распродажа"
      />

      {/* 6. Категории — Electric-specific component */}
      <ElectricCategorySection />

      {/* 7. Новости — Refactored with variant */}
      <NewsSection variant="electric" viewAllLink="/electric/news" />

      {/* 8. Наш блог — Refactored with variant */}
      <BlogSection variant="electric" viewAllLink="/electric/blog" />

      {/* 9. Подписка */}
      <ElectricSubscribeSection />
    </div>
  );
}
