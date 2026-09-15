/* eslint-disable @next/next/no-img-element */
'use client';

/**
 * Electric Orange Design System Test Page
 *
 * URL: /electric-orange-test
 *
 * Эта страница демонстрирует все компоненты дизайн-системы Electric Orange:
 * - Typography (Display, Headline, Body)
 * - Buttons (Primary, Outline, Ghost)
 * - Inputs (Default, Focus, Error)
 * - Badges (Primary, Sale, New, Hit)
 * - Cards (Product, Category)
 * - Skew geometry demo
 * - Cursor Fix: Explicit default cursor enforced
 */

import React, { useState } from 'react';
import { ElectricNewsCard } from '@/components/ui/NewsCard/ElectricNewsCard';
import { ElectricTabs } from '@/components/ui/Tabs/ElectricTabs';
import { ElectricSidebar } from '@/components/ui/Sidebar/ElectricSidebar';
import ElectricHeader from '@/components/layout/ElectricHeader';
import ElectricFooter from '@/components/layout/ElectricFooter';
import ElectricHeroBanner from '@/components/ui/Hero/ElectricHeroBanner';
import { ElectricProductCard } from '@/components/ui/ProductCard/ElectricProductCard';
import ElectricSectionHeader from '@/components/ui/SectionHeader/ElectricSectionHeader';
import { ElectricBreadcrumbs } from '@/components/ui/Breadcrumb/ElectricBreadcrumbs';
import { ElectricPagination } from '@/components/ui/Pagination/ElectricPagination';
import { ElectricModal } from '@/components/ui/Modal/ElectricModal';
import { ElectricToast, ElectricToastVariant } from '@/components/ui/Toast/ElectricToast';
import { ElectricAccordion } from '@/components/ui/Accordion/ElectricAccordion';
import { ElectricSelect } from '@/components/ui/Select/ElectricSelect';
import { ElectricRadioGroup } from '@/components/ui/Radio/ElectricRadioButton';
import { ElectricTooltip } from '@/components/ui/Tooltip/ElectricTooltip';
import { ElectricTable } from '@/components/ui/Table/ElectricTable';
import { ElectricSpinner, ElectricLoading } from '@/components/ui/Spinner/ElectricSpinner';
import { ElectricFeaturesBlock } from '@/components/ui/Features/ElectricFeaturesBlock';
import { ElectricCartWidget } from '@/components/ui/Cart/ElectricCartWidget';
import { ElectricSearchResults } from '@/components/ui/Search/ElectricSearchResults';
import { Info } from 'lucide-react';

export default function ElectricOrangeTestPage() {
  const [inputValue, setInputValue] = useState('');
  const [checkboxChecked, setCheckboxChecked] = useState(false);
  const [currentPage, setCurrentPage] = useState(3);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [toasts, setToasts] = useState<
    Array<{
      id: string;
      variant: ElectricToastVariant;
      title?: string;
      message: string;
    }>
  >([]);
  const [selectedSize, setSelectedSize] = useState('');
  const [selectedDelivery, setSelectedDelivery] = useState('');
  const [searchQuery, setSearchQuery] = useState('');
  const [currentPage2, setCurrentPage2] = useState(2);

  return (
    <div className="min-h-screen bg-[var(--bg-body)] text-[var(--foreground)] cursor-default">
      {/* 1. Header Component */}
      <ElectricHeader />
      {/* Main Content Wrapper - Added padding for fixed header */}
      <div className="pt-[80px]">
        {/* 2. Hero Component */}
        <ElectricHeroBanner />
        <div className="p-8">
          {/* Page Header (Legacy/Demo Title) */}
          <header className="mb-16 border-b border-[var(--border-default)] pb-8 mt-8">
            <h1
              className="text-5xl font-black uppercase mb-4"
              style={{
                fontFamily: "'Roboto Condensed', sans-serif",
                transform: 'skewX(-12deg)',
              }}
            >
              <span style={{ transform: 'skewX(12deg)', display: 'inline-block' }}>
                Electric Orange
              </span>
            </h1>
            <p className="text-[var(--color-text-secondary)]">
              Design System Test Page • Digital Brutalism & Kinetic Energy
            </p>
          </header>

          {/* Color Palette */}
          <section className="mb-16">
            <ElectricSectionHeader title="Цветовая палитра" />

            <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-4">
              <ColorSwatch color="#FF6B00" name="Primary" />
              <ColorSwatch color="#FF8533" name="Primary Hover" />
              <ColorSwatch color="#E55A00" name="Primary Active" />
              <ColorSwatch color="#0F0F0F" name="BG Body" border />
              <ColorSwatch color="#1A1A1A" name="BG Card" border />
              <ColorSwatch color="#333333" name="Border" border />
              <ColorSwatch color="#FFFFFF" name="Text Primary" border />
              <ColorSwatch color="#A0A0A0" name="Text Secondary" border />
              <ColorSwatch color="#666666" name="Text Muted" border />
              <ColorSwatch color="#22C55E" name="Success" />
              <ColorSwatch color="#EAB308" name="Warning" />
              <ColorSwatch color="#EF4444" name="Danger" />
            </div>
          </section>

          {/* Typography */}
          <section className="mb-16">
            <ElectricSectionHeader title="Типография" />

            <div className="space-y-8 bg-[var(--bg-card)] p-8 border border-[var(--border-default)]">
              {/* Display - Skewed */}
              <div>
                <p className="text-[var(--color-text-muted)] text-sm mb-2">
                  Display XL (72px, Roboto Condensed, Skewed)
                </p>
                <h2
                  className="text-6xl font-black uppercase text-[var(--foreground)]"
                  style={{
                    fontFamily: "'Roboto Condensed', sans-serif",
                    transform: 'skewX(-12deg)',
                  }}
                >
                  <span style={{ transform: 'skewX(12deg)', display: 'inline-block' }}>
                    Преодолей границы
                  </span>
                </h2>
              </div>

              {/* Headline - Skewed */}
              <div>
                <p className="text-[var(--color-text-muted)] text-sm mb-2">
                  Headline L (36px, Roboto Condensed, Skewed)
                </p>
                <h3
                  className="text-4xl font-bold uppercase text-[var(--foreground)]"
                  style={{
                    fontFamily: "'Roboto Condensed', sans-serif",
                    transform: 'skewX(-12deg)',
                  }}
                >
                  <span style={{ transform: 'skewX(12deg)', display: 'inline-block' }}>
                    Хиты продаж
                  </span>
                </h3>
              </div>

              {/* Title - Straight */}
              <div>
                <p className="text-[var(--color-text-muted)] text-sm mb-2">
                  Title L (24px, Inter, Straight)
                </p>
                <h4 className="text-2xl font-semibold text-[var(--foreground)]">
                  Перчатки боксерские BOYBO STAIN
                </h4>
              </div>

              {/* Body - Straight */}
              <div>
                <p className="text-[var(--color-text-muted)] text-sm mb-2">
                  Body M (16px, Inter, Straight)
                </p>
                <p className="text-base text-[var(--color-text-secondary)]">
                  Боксерские перчатки BOYBO STAIN — профессиональный выбор для тренировок и
                  соревнований. Изготовлены из высококачественной синтетической кожи.
                </p>
              </div>

              {/* Price - Skewed */}
              <div>
                <p className="text-[var(--color-text-muted)] text-sm mb-2">
                  Price Tag (Skewed, Orange)
                </p>
                <span
                  className="text-3xl font-bold text-[var(--color-primary)] inline-block"
                  style={{
                    fontFamily: "'Roboto Condensed', sans-serif",
                    transform: 'skewX(-12deg)',
                  }}
                >
                  7 990 ₽
                </span>
              </div>
            </div>
          </section>

          {/* Buttons */}
          <section className="mb-16">
            <ElectricSectionHeader title="Кнопки" />

            <div className="space-y-8 bg-[var(--bg-card)] p-8 border border-[var(--border-default)]">
              {/* Primary Buttons */}
              <div>
                <p className="text-[var(--color-text-muted)] text-sm mb-4">
                  Primary (Skewed, Orange)
                </p>
                <div className="flex flex-wrap gap-4">
                  <SkewedButton variant="primary" size="sm">
                    Small
                  </SkewedButton>
                  <SkewedButton variant="primary" size="md">
                    Medium
                  </SkewedButton>
                  <SkewedButton variant="primary" size="lg">
                    Large
                  </SkewedButton>
                </div>
              </div>

              {/* Outline Buttons */}
              <div>
                <p className="text-[var(--color-text-muted)] text-sm mb-4">
                  Outline (Skewed, White Border)
                </p>
                <div className="flex flex-wrap gap-4">
                  <SkewedButton variant="outline" size="sm">
                    Small
                  </SkewedButton>
                  <SkewedButton variant="outline" size="md">
                    Medium
                  </SkewedButton>
                  <SkewedButton variant="outline" size="lg">
                    Large
                  </SkewedButton>
                </div>
              </div>

              {/* Ghost Buttons */}
              <div>
                <p className="text-[var(--color-text-muted)] text-sm mb-4">
                  Ghost (Skewed, Transparent)
                </p>
                <div className="flex flex-wrap gap-4">
                  <SkewedButton variant="ghost" size="sm">
                    Small
                  </SkewedButton>
                  <SkewedButton variant="ghost" size="md">
                    Medium
                  </SkewedButton>
                  <SkewedButton variant="ghost" size="lg">
                    Large
                  </SkewedButton>
                </div>
              </div>

              {/* CTA Example */}
              <div>
                <p className="text-[var(--color-text-muted)] text-sm mb-4">CTA Example</p>
                <div className="flex gap-4">
                  <SkewedButton variant="primary" size="lg">
                    Добавить в корзину
                  </SkewedButton>
                  <SkewedButton variant="outline" size="lg">
                    ♡
                  </SkewedButton>
                </div>
              </div>
            </div>
          </section>

          {/* Form Elements */}
          <section className="mb-16">
            <ElectricSectionHeader title="Форма" />

            <div className="bg-[var(--bg-card)] p-8 border border-[var(--border-default)]">
              <div className="max-w-md space-y-6">
                {/* Text Input */}
                <div>
                  <label className="block text-[var(--color-text-secondary)] text-sm mb-2">
                    Имя
                  </label>
                  <input
                    type="text"
                    placeholder="Введите имя"
                    value={inputValue}
                    onChange={e => setInputValue(e.target.value)}
                    className="w-full h-11 px-4 bg-transparent border border-[var(--border-default)] text-[var(--foreground)] placeholder-[var(--color-text-muted)] focus:border-[var(--color-primary)] focus:outline-none transition-colors"
                  />
                </div>

                {/* Input with error */}
                <div>
                  <label className="block text-[var(--color-text-secondary)] text-sm mb-2">
                    Email (с ошибкой)
                  </label>
                  <input
                    type="email"
                    placeholder="Введите email"
                    className="w-full h-11 px-4 bg-transparent border border-[var(--color-danger)] text-[var(--foreground)] placeholder-[var(--color-text-muted)] focus:outline-none"
                  />
                  <p className="text-[var(--color-danger)] text-sm mt-1">Некорректный email</p>
                </div>

                {/* Checkbox */}
                <div className="flex items-center gap-3">
                  <button
                    onClick={() => setCheckboxChecked(!checkboxChecked)}
                    className={`w-5 h-5 border-2 flex items-center justify-center transition-colors ${
                      checkboxChecked
                        ? 'bg-[var(--color-primary)] border-[var(--color-primary)]'
                        : 'border-[var(--border-default)] hover:border-[var(--color-primary)]'
                    }`}
                    style={{ transform: 'skewX(-12deg)' }}
                  >
                    {checkboxChecked && (
                      <span
                        className="text-black text-xs font-bold"
                        style={{ transform: 'skewX(12deg)' }}
                      >
                        ✓
                      </span>
                    )}
                  </button>
                  <span className="text-[var(--foreground)]">Согласен с условиями</span>
                </div>
              </div>
            </div>
          </section>

          {/* Badges */}
          <section className="mb-16">
            <ElectricSectionHeader title="Бейджи" />

            <div className="bg-[var(--bg-card)] p-8 border border-[var(--border-default)]">
              <div className="flex flex-wrap gap-4">
                <SkewedBadge variant="primary">Новинка</SkewedBadge>
                <SkewedBadge variant="sale">-20%</SkewedBadge>
                <SkewedBadge variant="hit">Хит</SkewedBadge>
                <SkewedBadge variant="new">New</SkewedBadge>
              </div>
            </div>
          </section>

          {/* Product Cards */}
          <section className="mb-16">
            <ElectricSectionHeader title="Карточки товаров" />

            <div className="grid grid-cols-[repeat(4,270px)] gap-5">
              <ElectricProductCard
                id="1"
                brand="Espado"
                title="Гантель неопреновая Espado ES1115 зеленая"
                price={225}
                badge="hit"
                image="/electric-orange/img/8f07c7eb-899f-11eb-81dd-00155d3cae02_6a52988c-8c7b-11eb-81de-00155d3cae02.jpg"
              />
              <ElectricProductCard
                id="2"
                brand="BOYBO"
                title="Борцовки BoyBo на толстой подошве, на липучке красные"
                price={2200}
                oldPrice={2990}
                badge="sale"
                image="/electric-orange/img/6976ce61-be0d-11ea-81c4-00155d3cae02_09591dd0-565f-11eb-81d3-00155d3cae02.jpg"
              />
              <ElectricProductCard
                id="3"
                brand="Adidas"
                title="Кроссовки Ultraboost 22"
                price={14990}
                badge="new"
                image="/electric-orange/img/Gemini_Generated_Image_36n5hd36n5hd36n5.png"
              />
              <ElectricProductCard
                id="4"
                brand="VECTOR"
                title="Спортивная куртка WindBreaker"
                price={8990}
                image="/electric-orange/img/Gemini_Generated_Image_k7t8bpk7t8bpk7t8.png"
              />
            </div>
          </section>

          {/* Slider & Tabs */}
          <section className="mb-16">
            <ElectricSectionHeader title="Слайдер и Табы" />

            <div className="grid grid-cols-[repeat(4,270px)] gap-5">
              <CategoryCardDemo title="Единоборства" image="/electric-orange/img/bags.jpg" />
              <CategoryCardDemo
                title="Фитнес"
                image="/electric-orange/img/photo-1534438327276-14e5300c3a48.avif"
              />
              <CategoryCardDemo
                title="Игровые виды"
                image="/electric-orange/img/Gemini_Generated_Image_36n5hd36n5hd36n5.png"
              />
              <CategoryCardDemo
                title="Гимнастика"
                image="/electric-orange/img/Gemini_Generated_Image_k7t8bpk7t8bpk7t8.png"
              />
            </div>
          </section>

          {/* Sidebar */}
          <section className="mb-16">
            <ElectricSectionHeader title="Сайдбар виджет" />

            <div className="flex gap-8">
              <ElectricSidebar
                filterGroups={[
                  {
                    id: 'category',
                    title: 'КАТЕГОРИИ',
                    type: 'checkbox',
                    options: [
                      { id: 'crossfit', label: 'Кроссфит', count: 24 },
                      { id: 'fitness', label: 'Фитнес', count: 156 },
                      { id: 'martial_arts', label: 'Единоборства', count: 89 },
                    ],
                  },
                  {
                    id: 'brand',
                    title: 'БРЕНД',
                    type: 'checkbox',
                    options: [
                      { id: 'nike', label: 'Nike', count: 45 },
                      { id: 'adidas', label: 'Adidas', count: 38 },
                      { id: 'ua', label: 'Under Armour', count: 22 },
                      { id: 'boybo', label: 'BoyBo', count: 67 },
                    ],
                  },
                  {
                    id: 'price',
                    title: 'ЦЕНА (₽)',
                    type: 'price',
                    options: [],
                  },
                ]}
                priceRange={{ min: 1, max: 50000 }}
                currentPrice={{ min: 1000, max: 25000 }}
                className="w-full max-w-[300px]"
              />

              <div className="flex-1 bg-[var(--bg-card)] border border-[var(--border-default)] p-8 hidden md:block">
                <p className="text-[var(--color-text-muted)] text-sm mb-4">
                  Sidebar Widget Features:
                </p>
                <ul className="text-[var(--color-text-secondary)] space-y-2 text-sm">
                  <li>• Filter titles with -12° skew</li>
                  <li>• Skewed checkboxes (-12°) with counter-skewed text</li>
                  <li>• Price range inputs (rectangular)</li>
                  <li>• Skewed range slider container</li>
                  <li>• CTA button with apply action</li>
                </ul>
              </div>
            </div>
          </section>

          {/* News Cards */}
          <section className="mb-16">
            <ElectricSectionHeader title="Новости" />
            <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
              <ElectricNewsCard
                image="/electric-orange/img/bags.jpg"
                category="Фитнес"
                date="15 января 2026"
                title="Как выбрать идеальные кроссовки для бега зимой"
                excerpt="Полное руководство по выбору зимней экипировки. Советы профессионалов и обзор новинок сезона 2026 года."
              />
              <ElectricNewsCard
                image="/electric-orange/img/photo-1534438327276-14e5300c3a48.avif"
                category="Обзоры"
                date="12 января 2026"
                title="Топ-10 тренажеров для дома"
                excerpt="Рейтинг лучших тренажеров для домашнего использования. Сравнение цен, характеристик и отзывы покупателей."
              />
            </div>
          </section>

          {/* Tabs Demo */}
          <section className="mb-16">
            <ElectricSectionHeader title="Tabs" />
            <div className="bg-[var(--bg-card)] border border-[var(--border-default)] p-8">
              <ElectricTabs
                tabs={[
                  { id: 'desc', label: 'ОПИСАНИЕ' },
                  { id: 'specs', label: 'ХАРАКТЕРИСТИКИ' },
                  { id: 'reviews', label: 'ОТЗЫВЫ', count: 12 },
                ]}
                defaultActiveId="desc"
                className="mb-8"
              />
              <div className="text-[var(--color-text-secondary)] leading-relaxed">
                <p>
                  Высокотехнологичный материал обеспечивает максимальный комфорт во время
                  интенсивных тренировок. Специальная структура ткани{' '}
                  <span className="text-[var(--foreground)]">Dry-Fit</span> эффективно отводит влагу
                  от тела, сохраняя кожу сухой. Эргономичный крой не сковывает движений, позволяя
                  выполнять упражнения любой сложности с полной амплитудой.
                </p>
              </div>
            </div>
          </section>

          {/* Glow Effects */}
          <section className="mb-16">
            <ElectricSectionHeader title="Эффекты свечения" />

            <div className="bg-[var(--bg-card)] p-8 border border-[var(--border-default)]">
              <div className="flex flex-wrap gap-8 items-center justify-center">
                <div className="w-32 h-32 bg-[var(--color-primary)] flex items-center justify-center shadow-[var(--shadow-glow)]">
                  <span className="text-black font-bold">GLOW</span>
                </div>

                <div className="w-32 h-32 border-2 border-[var(--color-primary)] flex items-center justify-center transition-shadow hover:shadow-[var(--shadow-glow-intense)]">
                  <span className="text-[var(--color-primary)] font-bold">HOVER</span>
                </div>
              </div>
            </div>
          </section>

          {/* NEW: Breadcrumbs Demo */}
          <section className="mb-16">
            <ElectricSectionHeader title="Хлебные крошки" />

            <div className="bg-[var(--bg-card)] p-8 border border-[var(--border-default)] space-y-6">
              <div>
                <p className="text-[var(--color-text-muted)] text-sm mb-4">
                  Default (with Home icon)
                </p>
                <ElectricBreadcrumbs
                  items={[
                    { label: 'Главная', href: '/' },
                    { label: 'Каталог', href: '/catalog' },
                    { label: 'Единоборства', href: '/catalog/martial-arts' },
                    { label: 'Перчатки боксерские' },
                  ]}
                />
              </div>
              <div>
                <p className="text-[var(--color-text-muted)] text-sm mb-4">Without Home icon</p>
                <ElectricBreadcrumbs
                  items={[{ label: 'Главная', href: '/' }, { label: 'Акции' }]}
                  showHomeIcon={false}
                />
              </div>
            </div>
          </section>

          {/* NEW: Pagination Demo */}
          <section className="mb-16">
            <ElectricSectionHeader title="Пагинация" />

            <div className="bg-[var(--bg-card)] p-8 border border-[var(--border-default)] space-y-8">
              <div>
                <p className="text-[var(--color-text-muted)] text-sm mb-4">
                  Активная страница: {currentPage} из 10
                </p>
                <ElectricPagination
                  currentPage={currentPage}
                  totalPages={10}
                  onPageChange={setCurrentPage}
                />
              </div>
              <div>
                <p className="text-[var(--color-text-muted)] text-sm mb-4">
                  Маленький диапазон (5 страниц). Активная: {currentPage2}
                </p>
                <ElectricPagination
                  currentPage={currentPage2}
                  totalPages={5}
                  onPageChange={setCurrentPage2}
                />
              </div>
            </div>
          </section>

          {/* NEW: Modal Demo */}
          <section className="mb-16">
            <ElectricSectionHeader title="Модальное окно" />

            <div className="bg-[var(--bg-card)] p-8 border border-[var(--border-default)]">
              <button
                onClick={() => setIsModalOpen(true)}
                className="bg-[var(--color-primary)] text-black font-bold uppercase px-6 py-3 transform -skew-x-12 hover:bg-white hover:text-[var(--color-primary)] transition-all"
              >
                <span className="transform skew-x-12 inline-block">Открыть модал</span>
              </button>

              <ElectricModal
                isOpen={isModalOpen}
                onClose={() => setIsModalOpen(false)}
                title="Подтверждение действия"
                footer={
                  <div className="flex gap-3">
                    <button
                      onClick={() => setIsModalOpen(false)}
                      className="bg-transparent border border-[var(--border-default)] text-[var(--foreground)] font-bold uppercase px-6 py-3 transform -skew-x-12 hover:border-[var(--color-primary)] hover:text-[var(--color-primary)] transition-all"
                    >
                      <span className="transform skew-x-12 inline-block">Отмена</span>
                    </button>
                    <button
                      onClick={() => setIsModalOpen(false)}
                      className="bg-[var(--color-primary)] text-black font-bold uppercase px-6 py-3 transform -skew-x-12 hover:bg-white hover:text-[var(--color-primary)] transition-all"
                    >
                      <span className="transform skew-x-12 inline-block">Подтвердить</span>
                    </button>
                  </div>
                }
              >
                <p className="text-[var(--color-text-secondary)] leading-relaxed">
                  Вы уверены, что хотите добавить товар в корзину? Этот товар имеет ограниченное
                  количество на складе.
                </p>
              </ElectricModal>
            </div>
          </section>

          {/* NEW: Toast Demo */}
          <section className="mb-16">
            <ElectricSectionHeader title="Уведомления (Toast)" />

            <div className="bg-[var(--bg-card)] p-8 border border-[var(--border-default)]">
              <div className="flex flex-wrap gap-4 mb-8">
                {(['success', 'error', 'warning', 'info'] as const).map(variant => (
                  <button
                    key={variant}
                    onClick={() => {
                      const id = Date.now().toString();
                      setToasts(prev => [
                        ...prev,
                        {
                          id,
                          variant,
                          title:
                            variant === 'success'
                              ? 'Успех!'
                              : variant === 'error'
                                ? 'Ошибка!'
                                : variant === 'warning'
                                  ? 'Внимание!'
                                  : 'Информация',
                          message: `Это демонстрация ${variant} уведомления в стиле Electric Orange.`,
                        },
                      ]);
                    }}
                    className={`border font-bold uppercase px-4 py-2 transform -skew-x-12 transition-all ${
                      variant === 'success'
                        ? 'border-[var(--color-success)] text-[var(--color-success)] hover:bg-[var(--color-success)] hover:text-black'
                        : variant === 'error'
                          ? 'border-[var(--color-danger)] text-[var(--color-danger)] hover:bg-[var(--color-danger)] hover:text-white'
                          : variant === 'warning'
                            ? 'border-[var(--color-warning)] text-[var(--color-warning)] hover:bg-[var(--color-warning)] hover:text-black'
                            : 'border-[var(--color-primary)] text-[var(--color-primary)] hover:bg-[var(--color-primary)] hover:text-black'
                    }`}
                  >
                    <span className="transform skew-x-12 inline-block text-sm">{variant}</span>
                  </button>
                ))}
              </div>

              {/* Static Toast Examples */}
              <div className="space-y-4">
                <p className="text-[var(--color-text-muted)] text-sm mb-4">
                  Примеры уведомлений (статичные):
                </p>
                <div className="flex flex-col gap-4">
                  <ElectricToast
                    id="demo-1"
                    variant="success"
                    title="Товар добавлен!"
                    message="Перчатки боксерские BOYBO добавлены в корзину."
                    duration={0}
                    onClose={() => {}}
                  />
                  <ElectricToast
                    id="demo-2"
                    variant="error"
                    message="Произошла ошибка при оформлении заказа."
                    duration={0}
                    onClose={() => {}}
                  />
                </div>
              </div>
            </div>
          </section>

          {/* Toast Container for dynamic toasts */}
          {toasts.length > 0 && (
            <div className="fixed top-24 right-4 z-50 flex flex-col gap-3">
              {toasts.map(toast => (
                <ElectricToast
                  key={toast.id}
                  {...toast}
                  onClose={id => setToasts(prev => prev.filter(t => t.id !== id))}
                />
              ))}
            </div>
          )}

          {/* NEW: Select Demo */}
          <section className="mb-16">
            <ElectricSectionHeader title="Выпадающий список (Select)" />

            <div className="bg-[var(--bg-card)] p-8 border border-[var(--border-default)]">
              <div className="max-w-sm space-y-4">
                <p className="text-[var(--color-text-muted)] text-sm mb-4">Выберите размер:</p>
                <ElectricSelect
                  options={[
                    { value: 'xs', label: 'XS (42-44)' },
                    { value: 's', label: 'S (44-46)' },
                    { value: 'm', label: 'M (46-48)' },
                    { value: 'l', label: 'L (48-50)' },
                    { value: 'xl', label: 'XL (50-52)' },
                  ]}
                  value={selectedSize}
                  placeholder="Выберите размер..."
                  onChange={setSelectedSize}
                />
                {selectedSize && (
                  <p className="text-[var(--color-text-secondary)] text-sm">
                    Выбрано:{' '}
                    <span className="text-[var(--color-primary)]">
                      {selectedSize.toUpperCase()}
                    </span>
                  </p>
                )}
              </div>
            </div>
          </section>

          {/* NEW: Accordion Demo */}
          <section className="mb-16">
            <ElectricSectionHeader title="Аккордеон (FAQ)" />

            <div className="bg-[var(--bg-card)] p-8 border border-[var(--border-default)]">
              <ElectricAccordion
                items={[
                  {
                    id: 'faq-1',
                    title: 'Как оформить заказ?',
                    content:
                      'Выберите товары, добавьте их в корзину, перейдите к оформлению и заполните данные для доставки.',
                  },
                  {
                    id: 'faq-2',
                    title: 'Какие способы оплаты доступны?',
                    content:
                      'Мы принимаем банковские карты, электронные кошельки и наличные при получении.',
                  },
                  {
                    id: 'faq-3',
                    title: 'Как отследить заказ?',
                    content:
                      'После отправки заказа вы получите трек-номер на email для отслеживания.',
                  },
                ]}
                defaultOpenId="faq-1"
              />
            </div>
          </section>

          {/* NEW: Radio Button Demo */}
          <section className="mb-16">
            <ElectricSectionHeader title="Радио-кнопки" />

            <div className="bg-[var(--bg-card)] p-8 border border-[var(--border-default)]">
              <p className="text-[var(--color-text-muted)] text-sm mb-4">Способ доставки:</p>
              <ElectricRadioGroup
                name="delivery"
                options={[
                  { value: 'pickup', label: 'Самовывоз из магазина' },
                  { value: 'courier', label: 'Курьерская доставка' },
                  { value: 'cdek', label: 'СДЭК' },
                  { value: 'post', label: 'Почта России', disabled: true },
                ]}
                value={selectedDelivery}
                onChange={setSelectedDelivery}
              />
              {selectedDelivery && (
                <p className="text-[var(--color-text-secondary)] text-sm mt-4">
                  Выбрано: <span className="text-[var(--color-primary)]">{selectedDelivery}</span>
                </p>
              )}
            </div>
          </section>

          {/* NEW: Tooltip Demo */}
          <section className="mb-16">
            <ElectricSectionHeader title="Всплывающие подсказки (Tooltip)" />

            <div className="bg-[var(--bg-card)] p-8 border border-[var(--border-default)]">
              <div className="flex flex-wrap gap-8 items-center justify-center">
                <ElectricTooltip content="Подсказка сверху" position="top">
                  <button className="px-4 py-2 border border-[var(--border-default)] text-[var(--foreground)] hover:border-[var(--color-primary)] transition-colors">
                    Hover (top)
                  </button>
                </ElectricTooltip>

                <ElectricTooltip content="Подсказка снизу" position="bottom">
                  <button className="px-4 py-2 border border-[var(--border-default)] text-[var(--foreground)] hover:border-[var(--color-primary)] transition-colors">
                    Hover (bottom)
                  </button>
                </ElectricTooltip>

                <ElectricTooltip content="Подсказка слева" position="left">
                  <button className="px-4 py-2 border border-[var(--border-default)] text-[var(--foreground)] hover:border-[var(--color-primary)] transition-colors">
                    Hover (left)
                  </button>
                </ElectricTooltip>

                <ElectricTooltip content="Подсказка справа" position="right">
                  <button className="px-4 py-2 border border-[var(--border-default)] text-[var(--foreground)] hover:border-[var(--color-primary)] transition-colors">
                    Hover (right)
                  </button>
                </ElectricTooltip>

                <ElectricTooltip content="Информация о товаре" position="top">
                  <span className="cursor-help">
                    <Info className="w-5 h-5 text-[var(--color-primary)]" />
                  </span>
                </ElectricTooltip>
              </div>
            </div>
          </section>

          {/* NEW: Table Demo */}
          <section className="mb-16">
            <ElectricSectionHeader title="Таблица" />

            <div className="bg-[var(--bg-card)] p-8 border border-[var(--border-default)]">
              <ElectricTable
                columns={[
                  { key: 'sku', header: 'Артикул', width: '120px' },
                  { key: 'name', header: 'Наименование' },
                  { key: 'quantity', header: 'Кол-во', align: 'center', width: '80px' },
                  {
                    key: 'price',
                    header: 'Цена',
                    align: 'right',
                    width: '120px',
                    render: row => (
                      <span className="text-[var(--color-primary)] font-bold">{row.price} ₽</span>
                    ),
                  },
                ]}
                data={[
                  {
                    id: '1',
                    sku: 'BX-001',
                    name: 'Перчатки боксерские BOYBO',
                    quantity: 2,
                    price: '3 500',
                  },
                  {
                    id: '2',
                    sku: 'KM-042',
                    name: 'Кимоно для карате',
                    quantity: 1,
                    price: '4 200',
                  },
                  {
                    id: '3',
                    sku: 'SH-015',
                    name: 'Шлем для единоборств',
                    quantity: 1,
                    price: '2 800',
                  },
                ]}
                getRowKey={row => row.id}
                onRowClick={row => console.log('Clicked:', row)}
              />
            </div>
          </section>

          {/* NEW: Spinner Demo */}
          <section className="mb-16">
            <ElectricSectionHeader title="Индикатор загрузки (Spinner)" />

            <div className="bg-[var(--bg-card)] p-8 border border-[var(--border-default)]">
              <div className="flex flex-wrap gap-12 items-center justify-center">
                <div className="text-center">
                  <ElectricSpinner size="sm" />
                  <p className="text-[var(--color-text-muted)] text-xs mt-4">Small</p>
                </div>
                <div className="text-center">
                  <ElectricSpinner size="md" />
                  <p className="text-[var(--color-text-muted)] text-xs mt-4">Medium</p>
                </div>
                <div className="text-center">
                  <ElectricSpinner size="lg" />
                  <p className="text-[var(--color-text-muted)] text-xs mt-4">Large</p>
                </div>
                <div className="text-center">
                  <ElectricLoading text="Загружаем каталог..." />
                </div>
              </div>
            </div>
          </section>

          {/* NEW: Features Block Demo */}
          <section className="mb-16">
            <ElectricSectionHeader title="Блок преимуществ" />
            <ElectricFeaturesBlock />
          </section>

          {/* NEW: Cart Widget Demo */}
          <section className="mb-16">
            <ElectricSectionHeader title="Виджет корзины" />

            <div className="bg-[var(--bg-card)] p-8 border border-[var(--border-default)]">
              <div className="flex items-center gap-8">
                <p className="text-[var(--color-text-muted)] text-sm">Нажмите на иконку корзины:</p>
                <ElectricCartWidget
                  items={[
                    {
                      id: '1',
                      title: 'Перчатки боксерские BOYBO',
                      price: 3500,
                      quantity: 2,
                      image: '/images/placeholder.jpg',
                    },
                    { id: '2', title: 'Шлем для единоборств', price: 2800, quantity: 1 },
                  ]}
                  onRemoveItem={id => console.log('Remove:', id)}
                  onCheckout={() => console.log('Checkout')}
                  onViewCart={() => console.log('View Cart')}
                />
              </div>
            </div>
          </section>

          {/* NEW: Search Results Demo */}
          <section className="mb-16">
            <ElectricSectionHeader title="Поиск с автокомплитом" />

            <div className="bg-[var(--bg-card)] p-8 border border-[var(--border-default)]">
              <div className="max-w-md">
                <ElectricSearchResults
                  query={searchQuery}
                  onQueryChange={setSearchQuery}
                  onSelect={item => console.log('Selected:', item)}
                  onSubmit={q => console.log('Search:', q)}
                  results={
                    searchQuery.length > 1
                      ? [
                          {
                            id: '1',
                            type: 'product',
                            title: 'Перчатки боксерские BOYBO',
                            subtitle: 'Единоборства',
                          },
                          {
                            id: '2',
                            type: 'product',
                            title: 'Шлем для бокса',
                            subtitle: 'Единоборства',
                          },
                          { id: '3', type: 'category', title: 'Единоборства' },
                          { id: '4', type: 'brand', title: 'BOYBO' },
                        ]
                      : []
                  }
                />
                <p className="text-[var(--color-text-muted)] text-xs mt-4">
                  Введите минимум 2 символа для поиска
                </p>
              </div>
            </div>
          </section>
        </div>{' '}
        {/* End of p-8 */}
        <ElectricFooter />
      </div>{' '}
      {/* End of pt-[80px] wrapper */}
    </div>
  );
}

// ============================================
// Helper Components
// ============================================

function ColorSwatch({ color, name, border }: { color: string; name: string; border?: boolean }) {
  return (
    <div className="text-center">
      <div
        className={`w-full h-16 mb-2 ${border ? 'border border-[#333333]' : ''}`}
        style={{ backgroundColor: color }}
      />
      <p className="text-xs text-[var(--color-text-secondary)]">{name}</p>
      <p className="text-xs text-[var(--color-text-muted)]">{color}</p>
    </div>
  );
}

interface SkewedButtonProps {
  variant: 'primary' | 'outline' | 'ghost';
  size: 'sm' | 'md' | 'lg';
  children: React.ReactNode;
}

function SkewedButton({ variant, size, children }: SkewedButtonProps) {
  const sizeClasses = {
    sm: 'h-9 px-4 text-sm',
    md: 'h-11 px-6 text-base',
    lg: 'h-14 px-8 text-lg',
  };

  const variantClasses = {
    primary:
      'bg-[var(--color-primary)] text-black hover:bg-[var(--color-text-primary)] hover:text-[var(--color-primary-active)] hover:shadow-[var(--shadow-hover)]',
    outline:
      'bg-transparent border-2 border-[var(--foreground)] text-[var(--foreground)] hover:border-[var(--color-primary)] hover:text-[var(--color-primary)]',
    ghost:
      'bg-transparent text-[var(--foreground)] hover:text-[var(--color-primary)] hover:bg-[var(--color-primary-subtle)]',
  };

  return (
    <button
      className={`font-semibold uppercase transition-all ${sizeClasses[size]} ${variantClasses[variant]}`}
      style={{ transform: 'skewX(-12deg)' }}
    >
      <span style={{ transform: 'skewX(12deg)', display: 'inline-block' }}>{children}</span>
    </button>
  );
}

interface SkewedBadgeProps {
  variant: 'primary' | 'sale' | 'hit' | 'new';
  children: React.ReactNode;
}

function SkewedBadge({ variant, children }: SkewedBadgeProps) {
  const variantClasses = {
    primary: 'bg-[var(--color-primary)] text-black',
    sale: 'bg-[var(--color-danger)] text-white',
    hit: 'bg-[var(--color-success)] text-black',
    new: 'bg-[var(--color-primary)] text-black',
  };

  return (
    <span
      className={`inline-flex px-3 py-1 text-xs font-bold uppercase ${variantClasses[variant]}`}
      style={{
        fontFamily: "'Roboto Condensed', sans-serif",
        transform: 'skewX(-12deg)',
      }}
    >
      <span style={{ transform: 'skewX(12deg)', display: 'inline-block' }}>{children}</span>
    </span>
  );
}

function CategoryCardDemo({ title, image }: { title: string; image?: string }) {
  return (
    <div className="category-card group">
      {/* Category Image */}
      {image && <img src={image} alt={title} className="category-image" />}

      {/* Title - 1.8rem per design_v2.3.0.json */}
      <h3 className="category-title">
        <span className="counter-skew">{title}</span>
      </h3>

      {/* Hover flash effect is now handled by CSS ::after on .category-card */}
    </div>
  );
}
