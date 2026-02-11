/**
 * Страница "Партнёрам" (/partners)
 * Story 19.4
 */

import React from 'react';
import { Metadata } from 'next';
import Link from 'next/link';
import { Store, Globe, Dumbbell, Heart, Trophy, GraduationCap, UserCheck } from 'lucide-react';
import {
  FeatureCard,
  ProcessSteps,
  Accordion,
  InfoPanel,
  Breadcrumb,
  Button,
} from '@/components/ui';
import type { ProcessStep, AccordionItemData } from '@/components/ui';

export const metadata: Metadata = {
  title: 'Партнёрам — условия сотрудничества | FREESPORT',
  description:
    'Станьте партнёром FREESPORT. Оптовые поставки спортивных товаров, персональный менеджер, гибкие условия сотрудничества.',
};

// Типы клиентов
const clientTypes = [
  {
    icon: Store,
    title: 'Спортивные магазины',
    description: 'Широкий ассортимент для вашего магазина',
  },
  {
    icon: Globe,
    title: 'Интернет-магазины',
    description: 'Быстрая обработка заказов и доставка',
  },
  {
    icon: Dumbbell,
    title: 'Тренеры',
    description: 'Специальные условия для тренеров',
  },
  {
    icon: Heart,
    title: 'Фитнес-клубы',
    description: 'Оптовые цены на оборудование',
  },
  {
    icon: Trophy,
    title: 'Федерации',
    description: 'Партнёрство со спортивными федерациями',
  },
  {
    icon: GraduationCap,
    title: 'Школы и ДЮСШ',
    description: 'Специальные программы для образовательных учреждений',
  },
];

// Шаги процесса
const processSteps: ProcessStep[] = [
  {
    number: 1,
    title: 'Подайте заявку',
    description: 'На сайте или по телефону',
  },
  {
    number: 2,
    title: 'Получите доступ',
    description: 'К оптовым ценам',
  },
  {
    number: 3,
    title: 'Работайте с менеджером',
    description: 'На всех этапах сотрудничества',
  },
];

// FAQ
const faqItems: AccordionItemData[] = [
  {
    question: 'Какие документы нужны для сотрудничества?',
    answer: 'Для оформления договора потребуются: ИНН, ОГРН, реквизиты организации.',
  },
  {
    question: 'Как происходит оплата?',
    answer:
      'Оплата производится по безналичному расчёту по реквизитам, указанным в сопроводительных документах.',
  },
  {
    question: 'Есть ли минимальная сумма заказа?',
    answer:
      'Минимальная сумма заказа для самовывоза — от 1 500 ₽, для доставки до ТК — от 35 000 ₽.',
  },
  {
    question: 'Работаете ли вы с ЭДО?',
    answer: 'Да, мы поддерживаем электронный документооборот через популярные сервисы.',
  },
];

export default function PartnersPage() {
  return (
    <div className="container mx-auto px-4 py-8">
      {/* Breadcrumb */}
      <Breadcrumb
        items={[
          { label: 'Главная', href: '/' },
          { label: 'Партнёрам', href: '/partners' },
        ]}
        className="mb-6"
      />

      {/* Hero секция */}
      <section className="mb-12 text-center">
        <h1 className="mb-4 text-4xl font-bold text-gray-900">Условия сотрудничества</h1>
        <p className="text-lg text-gray-600">Выстраиваем долгосрочные партнёрские отношения</p>
      </section>

      {/* Типы клиентов */}
      <section className="mb-16">
        <h2 className="mb-8 text-center text-3xl font-semibold text-gray-900">Типы клиентов</h2>
        <div className="grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-3">
          {clientTypes.map((type, index) => (
            <FeatureCard
              key={index}
              icon={type.icon}
              title={type.title}
              description={type.description}
              variant="compact"
            />
          ))}
        </div>
      </section>

      {/* Как начать сотрудничество */}
      <section className="mb-16">
        <h2 className="mb-8 text-center text-3xl font-semibold text-gray-900">
          Как начать сотрудничество
        </h2>
        <ProcessSteps steps={processSteps} variant="numbered" />
      </section>

      {/* Персональный менеджер */}
      <section className="mb-16">
        <InfoPanel
          variant="info"
          icon={<UserCheck className="w-full h-full" />}
          title="Персональный менеджер"
          message="На всех этапах сотрудничества с вами работает персональный менеджер. Он поможет подобрать товар, оформить заказ, проконсультирует по всем вопросам и обеспечит своевременную доставку."
        />
      </section>

      {/* Рекламации и возвраты */}
      <section className="mb-16">
        <h2 className="mb-6 text-center text-3xl font-semibold text-gray-900">
          Рекламации и возвраты
        </h2>
        <div className="mx-auto max-w-3xl rounded-lg border border-gray-200 bg-white p-8 shadow-sm">
          <p className="mb-4 text-gray-700">При недовложении или пересортице необходимо:</p>
          <ol className="list-inside list-decimal space-y-2 text-gray-700">
            <li>Составить акт о недостаче или пересортице в момент получения товара</li>
            <li>Сфотографировать содержимое коробки и маркировку</li>
            <li>Направить акт и фотографии менеджеру в течение 24 часов с момента получения</li>
            <li>
              Недостающий товар будет отправлен в ближайшую отгрузку, излишки — возвращены при
              следующей доставке
            </li>
          </ol>
          <p className="mt-4 text-sm text-gray-600">
            Рекламации по качеству товара принимаются в течение 14 дней с момента получения при
            наличии товарного вида и упаковки.
          </p>
        </div>
      </section>

      {/* FAQ */}
      <section className="mb-16">
        <h2 className="mb-8 text-center text-3xl font-semibold text-gray-900">
          Часто задаваемые вопросы
        </h2>
        <div className="mx-auto max-w-3xl">
          <Accordion items={faqItems} allowMultiple={false} />
        </div>
      </section>

      {/* CTA секция */}
      <section className="mb-12">
        <div className="mx-auto max-w-2xl rounded-lg border border-gray-200 bg-gradient-to-br from-primary-subtle to-orange-50 p-8 text-center shadow-md">
          <h2 className="mb-4 text-2xl font-semibold text-gray-900">
            Готовы начать сотрудничество?
          </h2>
          <p className="mb-6 text-gray-600">
            Зарегистрируйтесь на сайте и получите доступ к оптовым ценам
          </p>
          <div className="flex flex-col items-center justify-center gap-4 sm:flex-row">
            <Link href="/register?from=partners" className="inline-block">
              <Button variant="primary" size="large">
                Зарегистрироваться
              </Button>
            </Link>
            <div className="text-sm text-gray-600">
              Уже есть аккаунт?{' '}
              <Link
                href="/login"
                className="font-medium text-primary hover:text-primary-hover hover:underline"
              >
                Войти
              </Link>
            </div>
          </div>
        </div>
      </section>
    </div>
  );
}
