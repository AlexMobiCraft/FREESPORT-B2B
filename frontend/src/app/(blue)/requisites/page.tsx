import React from 'react';
import type { Metadata } from 'next';
import { Breadcrumb, Card } from '@/components/ui';

export const metadata: Metadata = {
  title: 'Реквизиты | FREESPORT',
  description:
    'Реквизиты ООО «ФРИСПОРТ»: ИНН, КПП, ОГРН, юридический и фактический адрес, контакты.',
};

// TODO: в дальнейшем заменить на fetch из API (модель Company или аналог)
const companyName = 'Общество с ограниченной ответственностью «ФРИСПОРТ»';

const requisites: ReadonlyArray<{ label: string; value: string }> = [
  { label: 'ИНН', value: '7810755524' },
  { label: 'КПП', value: '781001001' },
  { label: 'ОГРН', value: '1197847087239' },
  {
    label: 'Юридический адрес',
    value: '196006, Санкт-Петербург г, Ломаная ул, дом 11, литер А, помещение 16-Н, комната 5',
  },
  {
    label: 'Фактический адрес',
    value: '196006, Санкт-Петербург г, Ломаная ул, дом 11, литер А, помещение 16-Н, комната 5',
  },
  {
    label: 'Телефон',
    value: '+7 (8652) 22-50-78, +7 (8652) 90-97-71, +7 (968) 273-21-68',
  },
  { label: 'Электронная почта', value: 'info@freesport.ru' },
  { label: 'Руководитель', value: 'Терещенко Руслан Гумметович' },
];

const breadcrumbItems = [{ label: 'Главная', href: '/' }, { label: 'Реквизиты' }];

export default function RequisitesPage() {
  return (
    <div className="min-h-screen bg-canvas">
      <div className="container mx-auto px-4 py-4">
        <Breadcrumb items={breadcrumbItems} />
      </div>

      <section className="bg-panel py-8 sm:py-12">
        <div className="container mx-auto px-4 text-center">
          <h1 className="text-headline-l sm:text-display-m text-text-primary">Реквизиты</h1>
        </div>
      </section>

      <section className="container mx-auto px-4 py-8 sm:py-12">
        <Card className="p-6 sm:p-8">
          <h2 className="text-title-l text-text-primary mb-6 sm:mb-8">{companyName}</h2>

          <dl className="divide-y divide-neutral-300">
            {requisites.map(({ label, value }) => (
              <div key={label} className="flex flex-col gap-1 py-3 sm:flex-row sm:gap-6 sm:py-4">
                <dt className="text-body-s text-text-muted sm:w-64 sm:flex-shrink-0 sm:pt-0.5">
                  {label}
                </dt>
                <dd className="text-body-m text-text-primary font-semibold">{value}</dd>
              </div>
            ))}
          </dl>
        </Card>
      </section>
    </div>
  );
}
