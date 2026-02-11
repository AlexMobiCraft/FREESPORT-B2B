/**
 * Страница «Доставка» (/delivery)
 * Story 19.5: Условия доставки и самовывоза
 */

import React from 'react';
import type { Metadata } from 'next';
import { Truck, MapPin, Phone, Mail, AlertTriangle } from 'lucide-react';
import { Breadcrumb, Badge, Card } from '@/components/ui';
import { cn } from '@/utils/cn';

// SEO Metadata
export const metadata: Metadata = {
  title: 'Доставка | FREESPORT',
  description:
    'Условия доставки FREESPORT. Бесплатная доставка до ТК от 35 000 ₽. Самовывоз со склада в Ставрополе от 1 500 ₽.',
};

// Данные для доставки
const deliveryOptions = {
  tk: {
    icon: Truck,
    title: 'Доставка до транспортной компании',
    badge: 'БЕСПЛАТНО от 35 000 ₽',
    conditions: [
      'Согласуем выбранную ТК после оформления заказа',
      'Доставим до терминала без дополнительной платы',
      'Дальнейшую доставку осуществляет ТК по её тарифам',
    ],
  },
  pickup: {
    icon: MapPin,
    title: 'Самовывоз со склада',
    minOrder: 'от 1 500 ₽',
    address: 'г. Ставрополь, ул. Коломийцева, 40/1',
    warning: 'Перед приездом уточните готовность заказа',
  },
};

// Контакты
const contacts = {
  phone: '+7 968 273-21-68',
  phoneLink: 'tel:+79682732168',
  email: 'logist@freesportopt.ru',
  emailLink: 'mailto:logist@freesportopt.ru',
};

// Breadcrumb данные
const breadcrumbItems = [{ label: 'Главная', href: '/' }, { label: 'Доставка' }];

/**
 * Компонент карты (lazy loading)
 */
const MapEmbed: React.FC = () => {
  return (
    <div className="w-full h-[300px] rounded-lg overflow-hidden shadow-default">
      <iframe
        src="https://yandex.ru/map-widget/v1/?ll=41.930429%2C45.096235&z=17&pt=41.930429,45.096235,pm2rdm"
        width="100%"
        height="300"
        loading="lazy"
        title="Пункт самовывоза FREESPORT"
        className="border-0"
      />
    </div>
  );
};

/**
 * Страница «Доставка»
 */
export default function DeliveryPage() {
  const TKIcon = deliveryOptions.tk.icon;
  const PickupIcon = deliveryOptions.pickup.icon;

  return (
    <div className="min-h-screen bg-neutral-100">
      {/* Breadcrumb */}
      <div className="container mx-auto px-4 py-4">
        <Breadcrumb items={breadcrumbItems} />
      </div>

      {/* Hero Section */}
      <section className="bg-white py-12">
        <div className="container mx-auto px-4 text-center">
          <h1 className="text-headline-xl font-bold text-text-primary mb-4">Условия доставки</h1>
          <p className="text-body-l text-text-secondary max-w-2xl mx-auto">
            Мы предлагаем удобные варианты получения заказа
          </p>
        </div>
      </section>

      {/* Main Content */}
      <section className="container mx-auto px-4 py-12 space-y-8">
        {/* Доставка до ТК */}
        <Card className="p-8">
          <div className="flex items-start gap-6">
            <div className="flex-shrink-0">
              <div className="w-16 h-16 rounded-full bg-primary-subtle flex items-center justify-center">
                <TKIcon className="w-8 h-8 text-primary" />
              </div>
            </div>

            <div className="flex-grow">
              <div className="flex items-center gap-4 mb-4">
                <h2 className="text-title-l font-semibold text-text-primary">
                  {deliveryOptions.tk.title}
                </h2>
                <Badge variant="delivered">{deliveryOptions.tk.badge}</Badge>
              </div>

              <ul className="space-y-3">
                {deliveryOptions.tk.conditions.map((condition, index) => (
                  <li key={index} className="flex items-start gap-3">
                    <span className="text-primary mt-1">•</span>
                    <span className="text-body-m text-text-secondary">{condition}</span>
                  </li>
                ))}
              </ul>
            </div>
          </div>
        </Card>

        {/* Самовывоз */}
        <Card className="p-8">
          <div className="flex items-start gap-6">
            <div className="flex-shrink-0">
              <div className="w-16 h-16 rounded-full bg-primary-subtle flex items-center justify-center">
                <PickupIcon className="w-8 h-8 text-primary" />
              </div>
            </div>

            <div className="flex-grow">
              <h2 className="text-title-l font-semibold text-text-primary mb-4">
                {deliveryOptions.pickup.title}
              </h2>

              <div className="space-y-4">
                <div>
                  <span className="text-body-s text-text-secondary">Минимальный заказ: </span>
                  <span className="text-body-m font-semibold text-text-primary">
                    {deliveryOptions.pickup.minOrder}
                  </span>
                </div>

                <div>
                  <span className="text-body-s text-text-secondary">Адрес: </span>
                  <span className="text-body-m text-text-primary">
                    {deliveryOptions.pickup.address}
                  </span>
                </div>

                {/* Карта */}
                <div className="mt-6">
                  <MapEmbed />
                </div>

                {/* Предупреждение */}
                <div className="flex items-start gap-3 mt-6 p-4 bg-warning-subtle rounded-lg">
                  <AlertTriangle className="w-5 h-5 text-warning flex-shrink-0 mt-0.5" />
                  <p className="text-body-s text-text-secondary">
                    {deliveryOptions.pickup.warning}
                  </p>
                </div>
              </div>
            </div>
          </div>
        </Card>

        {/* Контакты логистики */}
        <Card className="p-8">
          <h2 className="text-title-l font-semibold text-text-primary mb-6">
            Контакты отдела логистики
          </h2>

          <div className="space-y-4">
            {/* Телефон */}
            <div className="flex items-center gap-4">
              <div className="w-12 h-12 rounded-full bg-primary-subtle flex items-center justify-center">
                <Phone className="w-6 h-6 text-primary" />
              </div>
              <a
                href={contacts.phoneLink}
                className={cn(
                  'text-body-l text-primary',
                  'hover:text-primary-hover transition-colors duration-short'
                )}
              >
                {contacts.phone}
              </a>
            </div>

            {/* Email */}
            <div className="flex items-center gap-4">
              <div className="w-12 h-12 rounded-full bg-primary-subtle flex items-center justify-center">
                <Mail className="w-6 h-6 text-primary" />
              </div>
              <a
                href={contacts.emailLink}
                className={cn(
                  'text-body-l text-primary',
                  'hover:text-primary-hover transition-colors duration-short'
                )}
              >
                {contacts.email}
              </a>
            </div>
          </div>
        </Card>
      </section>
    </div>
  );
}
