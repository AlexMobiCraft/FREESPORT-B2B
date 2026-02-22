/**
 * About Page (/about)
 * Story 19.3 - Страница «О компании»
 *
 * Секции:
 * 1. Breadcrumb навигация
 * 2. Hero секция с заголовком
 * 3. "Кто мы" описание
 * 4. Наши ценности (4 карточки)
 * 5. Статистика (4 счётчика)
 * 6. CTA секция
 */

import React from 'react';
import type { Metadata } from 'next';
import Link from 'next/link';
import { Zap, Check, Lightbulb, Shield } from 'lucide-react';
import { Breadcrumb, FeatureCard, StatCounter, Button } from '@/components/ui';

export const metadata: Metadata = {
  title: 'О компании | FREESPORT',
  description:
    'FREESPORT — федеральный оптовый поставщик и производитель спортивных товаров. Более 1000 товаров, 50+ брендов, 10+ лет на рынке.',
  openGraph: {
    title: 'О компании | FREESPORT',
    description: 'Федеральный оптовый поставщик спортивных товаров',
  },
};

// Данные для ценностей
const values = [
  {
    icon: Zap,
    title: 'Оперативность',
    description: 'Быстрая обработка заказов и доставка по всей России',
  },
  {
    icon: Check,
    title: 'Качество',
    description: 'Контроль на всех этапах производства и поставки',
  },
  {
    icon: Lightbulb,
    title: 'Инновации',
    description: 'Современные технологии и решения для партнёров',
  },
  {
    icon: Shield,
    title: 'Надёжность',
    description: 'Гарантия качества на все товары и долгосрочное партнёрство',
  },
];

// Данные для статистики
const stats = [
  { value: 1000, suffix: '+', label: 'товаров' },
  { value: 50, suffix: '+', label: 'брендов' },
  { value: 10, suffix: '+', label: 'лет' },
  { value: 100, suffix: '%', label: 'гарантия' },
];

export default function AboutPage() {
  const breadcrumbItems = [{ label: 'Главная', href: '/' }, { label: 'О компании' }];

  return (
    <div className="min-h-screen bg-neutral-50">
      {/* Breadcrumb */}
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
        <Breadcrumb items={breadcrumbItems} />
      </div>

      {/* Hero Section */}
      <section className="bg-white py-16 sm:py-20">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 text-center">
          <h1 className="text-4xl sm:text-5xl lg:text-6xl font-bold text-text-primary mb-4">
            О компании FREESPORT
          </h1>
          <p className="text-lg sm:text-xl text-text-secondary max-w-3xl mx-auto">
            Федеральный оптовый поставщик и производитель спортивных товаров с 2015 года
          </p>
        </div>
      </section>

      {/* "Кто мы" Section */}
      <section className="py-12 sm:py-16">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="max-w-3xl mx-auto">
            <h2 className="text-3xl sm:text-4xl font-bold text-text-primary mb-6 text-center">
              Кто мы
            </h2>
            <div className="prose prose-lg max-w-none text-text-secondary space-y-4">
              <p>
                <strong>FREESPORT</strong> — федеральный оптовый поставщик и производитель
                спортивных товаров.
              </p>
              <p>
                Компания разрабатывает собственную продукцию, контролирует производственные процессы
                и обеспечивает стабильные оптовые поставки по всей России.
              </p>
              <p>Основные принципы работы — качество, надёжность и долгосрочное партнёрство.</p>
            </div>
          </div>
        </div>
      </section>

      {/* Наши ценности Section */}
      <section className="bg-white py-12 sm:py-16">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <h2 className="text-3xl sm:text-4xl font-bold text-text-primary mb-10 text-center">
            Наши ценности
          </h2>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6">
            {values.map(value => (
              <FeatureCard
                key={value.title}
                icon={value.icon}
                title={value.title}
                description={value.description}
              />
            ))}
          </div>
        </div>
      </section>

      {/* Статистика Section */}
      <section className="py-12 sm:py-16">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <h2 className="text-3xl sm:text-4xl font-bold text-text-primary mb-10 text-center">
            В цифрах
          </h2>
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-8">
            {stats.map(stat => (
              <StatCounter
                key={stat.label}
                value={stat.value}
                suffix={stat.suffix}
                label={stat.label}
              />
            ))}
          </div>
        </div>
      </section>

      {/* CTA Section */}
      <section className="bg-primary py-16 sm:py-20">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 text-center">
          <h2 className="text-3xl sm:text-4xl font-bold text-white mb-6">
            Присоединяйтесь к числу наших партнёров!
          </h2>
          <p className="text-lg text-white/90 mb-8 max-w-2xl mx-auto">
            Станьте частью команды профессионалов и получите доступ к эксклюзивным условиям
            сотрудничества
          </p>
          <Link href="/register">
            <Button variant="secondary" size="large">
              Стать партнёром
            </Button>
          </Link>
        </div>
      </section>
    </div>
  );
}
