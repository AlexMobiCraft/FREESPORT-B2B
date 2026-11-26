/**
 * DeliveryTeaser - Тизер "Доставка по России"
 * Story 19.2 - Homepage Teasers
 */

import React from 'react';
import Link from 'next/link';
import { Truck, MapPin, LucideIcon } from 'lucide-react';
import { Button } from '@/components/ui';

interface DeliveryOption {
  icon: LucideIcon;
  title: string;
  badge?: string;
  description: string;
  details?: string;
}

const deliveryOptions: DeliveryOption[] = [
  {
    icon: Truck,
    title: 'Доставка до ТК',
    badge: 'БЕСПЛАТНО',
    description: 'от 35 000 ₽',
    details: 'До терминала ТК по России',
  },
  {
    icon: MapPin,
    title: 'Самовывоз со склада',
    description: 'г. Ставрополь',
    details: 'ул. Коломийцева, 40/1',
  },
];

export const DeliveryTeaser: React.FC = () => {
  return (
    <section className="py-12 px-4 bg-white">
      <div className="container mx-auto max-w-7xl">
        {/* Header */}
        <div className="text-center mb-8">
          <h2 className="text-3xl md:text-4xl font-bold text-gray-900 mb-2">Доставка по России</h2>
          <p className="text-lg text-gray-600">Удобные варианты получения вашего заказа</p>
        </div>

        {/* Delivery Options Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-8">
          {deliveryOptions.map((option, index) => {
            const IconComponent = option.icon;
            return (
              <div
                key={index}
                className="group relative bg-neutral-50 rounded-2xl p-6 shadow-md hover:shadow-lg transition-all duration-200 flex flex-col items-center text-center md:items-start md:text-left hover:-translate-y-0.5"
              >
                {/* Badge */}
                {option.badge && (
                  <div className="absolute top-4 right-4">
                    <span className="inline-flex items-center px-3 py-1 rounded-full bg-green-100 text-green-700 text-sm font-semibold">
                      {option.badge}
                    </span>
                  </div>
                )}

                {/* Icon */}
                <div className="mb-4">
                  <div className="inline-flex items-center justify-center w-16 h-16 bg-primary-subtle rounded-xl shadow-sm transition-colors duration-medium group-hover:bg-secondary-subtle">
                    <IconComponent className="w-12 h-12 text-primary" strokeWidth={1.5} />
                  </div>
                </div>

                {/* Content */}
                <h3 className="text-xl font-semibold text-gray-900 mb-2">{option.title}</h3>
                <p className="text-base font-medium text-gray-700 mb-1">{option.description}</p>
                {option.details && <p className="text-sm text-gray-500">{option.details}</p>}
              </div>
            );
          })}
        </div>

        {/* CTA */}
        <div className="text-center">
          <Link href="/delivery">
            <Button size="large" variant="primary">
              Подробнее о доставке
            </Button>
          </Link>
        </div>
      </div>
    </section>
  );
};

export default DeliveryTeaser;
