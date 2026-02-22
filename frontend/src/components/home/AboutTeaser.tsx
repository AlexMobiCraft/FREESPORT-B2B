/**
 * AboutTeaser - Тизер "О компании"
 * Story 19.2 - Homepage Teasers
 */

import React from 'react';
import Link from 'next/link';
import { Trophy, Zap, Check, Lightbulb, Shield } from 'lucide-react';
import { Button } from '@/components/ui';

interface CompanyValue {
  icon: React.ComponentType<{ className?: string }>;
  label: string;
}

const companyInfo = {
  title: 'FREESPORT',
  subtitle: 'Федеральный оптовый поставщик и производитель спортивных товаров',
  description:
    'Мы создаём качественные спортивные товары и предоставляем широкий ассортимент для розничных магазинов, спортивных клубов и федераций по всей России.',
  values: [
    { icon: Zap, label: 'Оперативность' },
    { icon: Check, label: 'Качество' },
    { icon: Lightbulb, label: 'Инновации' },
    { icon: Shield, label: 'Надёжность' },
  ] as CompanyValue[],
};

export const AboutTeaser: React.FC = () => {
  return (
    <section className="py-12 px-4 bg-neutral-50">
      <div className="container mx-auto max-w-7xl">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-8 items-center">
          {/* Left Column - Company Description */}
          <div className="space-y-4">
            {/* Icon & Title */}
            <div className="flex items-center gap-3 mb-4">
              <div className="inline-flex items-center justify-center w-12 h-12 bg-yellow-100 rounded-full">
                <Trophy className="w-6 h-6 text-yellow-600" />
              </div>
              <h2 className="text-3xl md:text-4xl font-bold text-gray-900">{companyInfo.title}</h2>
            </div>

            {/* Subtitle */}
            <p className="text-lg font-semibold text-gray-700">{companyInfo.subtitle}</p>

            {/* Description */}
            <p className="text-base text-gray-600 leading-relaxed">{companyInfo.description}</p>

            {/* CTA Button */}
            <div className="pt-4">
              <Link href="/about">
                <Button size="large" variant="primary">
                  Узнать больше о нас
                </Button>
              </Link>
            </div>
          </div>

          {/* Right Column - Values */}
          <div className="bg-white rounded-2xl p-8 shadow-md">
            <h3 className="text-2xl font-bold text-gray-900 mb-6">Наши ценности</h3>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              {companyInfo.values.map((value, index) => {
                const IconComponent = value.icon;
                return (
                  <div
                    key={index}
                    className="flex items-center gap-3 p-3 bg-neutral-50 rounded-lg hover:bg-primary-subtle transition-colors duration-200"
                  >
                    <div className="flex-shrink-0">
                      <div className="inline-flex items-center justify-center w-10 h-10 bg-primary-subtle rounded-full">
                        <IconComponent className="w-5 h-5 text-primary" />
                      </div>
                    </div>
                    <span className="text-base font-medium text-gray-800">{value.label}</span>
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      </div>
    </section>
  );
};

export default AboutTeaser;
