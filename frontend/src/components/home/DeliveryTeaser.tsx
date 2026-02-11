/**
 * DeliveryTeaser - Тизер "Доставка по России"
 * Story 19.2 - Homepage Teasers
 */

import React from 'react';
import Link from 'next/link';
import { Truck, MapPin } from 'lucide-react';
import { Button } from '@/components/ui';

interface DeliveryOption {
  icon: React.ComponentType<{ className?: string }>;
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
                className="relative bg-neutral-50 rounded-2xl p-6 shadow-md hover:shadow-lg transition-shadow duration-200"
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
                  <div className="inline-flex items-center justify-center w-16 h-16 bg-primary-subtle rounded-full">
                    <IconComponent className="w-8 h-8 text-primary" />
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
