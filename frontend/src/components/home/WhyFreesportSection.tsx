/**
 * WhyFreesportSection - Тизер "Почему партнёры выбирают FREESPORT?"
 * Story 19.2 - Homepage Teasers
 */

import React from 'react';
import Link from 'next/link';
import { Factory, Truck, Handshake, Package, LucideIcon } from 'lucide-react';
import { FeatureCard } from '@/components/ui';
import { Button } from '@/components/ui';

interface Advantage {
  icon: LucideIcon;
  title: string;
  description: string;
}

const advantages: Advantage[] = [
  {
    icon: Factory,
    title: 'Собственное производство',
    description: 'Контроль качества',
  },
  {
    icon: Truck,
    title: 'Бесплатная доставка',
    description: 'До ТК от 35 000 ₽',
  },
  {
    icon: Handshake,
    title: 'Персональный менеджер',
    description: 'Сопровождение на всех этапах',
  },
  {
    icon: Package,
    title: 'Минимальный заказ',
    description: 'От 1 500 ₽ самовывоз',
  },
];

export const WhyFreesportSection: React.FC = () => {
  return (
    <section className="py-12 px-4 bg-neutral-50">
      <div className="container mx-auto max-w-7xl">
        {/* Header */}
        <div className="text-center mb-8">
          <h2 className="text-3xl md:text-4xl font-bold text-gray-900 mb-4">
            Почему партнёры выбирают FREESPORT?
          </h2>
        </div>

        {/* Advantages Grid */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
          {advantages.map((advantage, index) => (
            <FeatureCard
              key={index}
              icon={advantage.icon}
              title={advantage.title}
              description={advantage.description}
              variant="default"
            />
          ))}
        </div>

        {/* CTA */}
        <div className="text-center">
          <Link href="/partners">
            <Button size="large" variant="primary">
              Стать партнёром
            </Button>
          </Link>
        </div>
      </div>
    </section>
  );
};

export default WhyFreesportSection;
