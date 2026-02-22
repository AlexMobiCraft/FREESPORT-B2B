/**
 * Partners Page (/electric/partners)
 * Electric Orange Theme
 */

import React from 'react';
import { Metadata } from 'next';
import Link from 'next/link';
import { Store, Globe, Dumbbell, Heart, Trophy, GraduationCap, UserCheck } from 'lucide-react';
import { Breadcrumb } from '@/components/ui';
import type { ProcessStep, AccordionItemData } from '@/components/ui';

export const metadata: Metadata = {
  title: 'Партнёрам — условия сотрудничества | FREESPORT (Electric)',
  description:
    'Станьте партнёром FREESPORT. Оптовые поставки спортивных товаров, персональный менеджер, гибкие условия сотрудничества.',
};

// Типы клиентов (Same as Blue for now)
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

export default function ElectricPartnersPage() {
  return (
    <div className="min-h-screen bg-[var(--bg-body)]">
      <div className="container mx-auto px-4 py-8">
        {/* Breadcrumb */}
        <Breadcrumb
          items={[
            { label: 'Главная', href: '/electric' },
            { label: 'Партнёрам', href: '/electric/partners' },
          ]}
          className="mb-6"
        />

        {/* Hero секция */}
        <section className="mb-12 text-center bg-[var(--bg-card)] py-12 border border-[var(--border-default)]">
          <h1 className="mb-4 text-4xl font-bold text-[var(--foreground)] uppercase transform -skew-x-12">
            <span className="inline-block transform skew-x-12">Условия сотрудничества</span>
          </h1>
          <p className="text-lg text-[var(--color-text-secondary)]">
            Выстраиваем долгосрочные партнёрские отношения
          </p>
        </section>

        {/* Типы клиентов */}
        <section className="mb-16">
          <h2 className="mb-8 text-center text-3xl font-bold text-[var(--foreground)] uppercase transform -skew-x-12">
            <span className="inline-block transform skew-x-12">Типы клиентов</span>
          </h2>
          <div className="grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-3">
            {clientTypes.map((type, index) => (
              <div
                key={index}
                className="bg-[var(--bg-card)] p-6 border border-[var(--border-default)] hover:border-[var(--color-primary)] transition-colors group"
              >
                <div className="w-12 h-12 mb-4 bg-[var(--color-primary)] flex items-center justify-center transform -skew-x-12 text-black">
                  <type.icon className="w-6 h-6 transform skew-x-12" />
                </div>
                <h3 className="text-xl font-bold text-[var(--foreground)] mb-2 uppercase">
                  {type.title}
                </h3>
                <p className="text-[var(--color-text-secondary)]">{type.description}</p>
              </div>
            ))}
          </div>
        </section>

        {/* Как начать сотрудничество */}
        <section className="mb-16">
          <h2 className="mb-8 text-center text-3xl font-bold text-[var(--foreground)] uppercase transform -skew-x-12">
            <span className="inline-block transform skew-x-12">Как начать сотрудничество</span>
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
            {processSteps.map(step => (
              <div
                key={step.number}
                className="relative bg-[var(--bg-card)] p-6 border border-[var(--border-default)]"
              >
                <div className="absolute -top-4 -left-4 w-10 h-10 bg-[var(--color-primary)] flex items-center justify-center text-black font-bold text-xl transform -skew-x-12 border-2 border-[var(--bg-body)]">
                  <span className="transform skew-x-12">{step.number}</span>
                </div>
                <h3 className="mt-4 text-xl font-bold text-[var(--foreground)] mb-2 uppercase">
                  {step.title}
                </h3>
                <p className="text-[var(--color-text-secondary)]">{step.description}</p>
              </div>
            ))}
          </div>
        </section>

        {/* Персональный менеджер */}
        <section className="mb-16">
          <div className="bg-[var(--bg-card)] p-8 border border-[var(--border-default)] flex items-start gap-6">
            <div className="hidden md:block w-24 h-24 bg-[var(--color-primary)] flex-shrink-0 flex items-center justify-center text-black transform -skew-x-12">
              <UserCheck className="w-12 h-12 transform skew-x-12" />
            </div>
            <div>
              <h3 className="text-2xl font-bold text-[var(--foreground)] mb-3 uppercase">
                Персональный менеджер
              </h3>
              <p className="text-[var(--color-text-secondary)] leading-relaxed">
                На всех этапах сотрудничества с вами работает персональный менеджер. Он поможет
                подобрать товар, оформить заказ, проконсультирует по всем вопросам и обеспечит
                своевременную доставку.
              </p>
            </div>
          </div>
        </section>

        {/* FAQ */}
        <section className="mb-16">
          <h2 className="mb-8 text-center text-3xl font-bold text-[var(--foreground)] uppercase transform -skew-x-12">
            <span className="inline-block transform skew-x-12">Часто задаваемые вопросы</span>
          </h2>
          <div className="mx-auto max-w-3xl space-y-4">
            {faqItems.map((item, i) => (
              <details
                key={i}
                className="bg-[var(--bg-card)] border border-[var(--border-default)] group"
              >
                <summary className="p-4 cursor-pointer font-bold text-[var(--foreground)] flex justify-between items-center">
                  {item.question}
                  <span className="w-6 h-6 flex items-center justify-center border border-[var(--border-default)] bg-[var(--bg-body)] text-[var(--color-primary)] group-open:bg-[var(--color-primary)] group-open:text-black transition-colors">
                    +
                  </span>
                </summary>
                <div className="p-4 pt-0 text-[var(--color-text-secondary)] border-t border-[var(--border-default)] mt-2">
                  {item.answer}
                </div>
              </details>
            ))}
          </div>
        </section>

        {/* CTA секция */}
        <section className="mb-12">
          <div className="mx-auto max-w-2xl bg-[var(--bg-card)] border border-[var(--color-primary)] p-8 text-center transform -skew-x-2">
            <div className="transform skew-x-2">
              <h2 className="mb-4 text-2xl font-bold text-[var(--foreground)] uppercase">
                Готовы начать сотрудничество?
              </h2>
              <p className="mb-6 text-[var(--color-text-secondary)]">
                Зарегистрируйтесь на сайте и получите доступ к оптовым ценам
              </p>
              <div className="flex flex-col items-center justify-center gap-4 sm:flex-row">
                <Link href="/register?from=partners" className="inline-block">
                  <button className="px-8 py-3 bg-[var(--color-primary)] text-black font-bold uppercase transform -skew-x-12 hover:bg-white transition-colors border border-[var(--color-primary)]">
                    <span className="inline-block transform skew-x-12">Зарегистрироваться</span>
                  </button>
                </Link>
                <div className="text-sm text-[var(--color-text-secondary)]">
                  Уже есть аккаунт?{' '}
                  <Link
                    href="/login"
                    className="font-bold text-[var(--color-primary)] hover:underline"
                  >
                    Войти
                  </Link>
                </div>
              </div>
            </div>
          </div>
        </section>
      </div>
    </div>
  );
}
