import React from 'react';
import type { Metadata } from 'next';
import { Breadcrumb, Card } from '@/components/ui';
import { buildMetadata } from '@/utils/seo';

export const metadata: Metadata = buildMetadata({
  title: 'Реквизиты | OPTISPORT',
  description:
    'Реквизиты OPTISPORT: ИНН, ОГРНИП, банковские реквизиты и адреса владельца и пользователя сайта.',
  path: '/requisites',
});

/** Роль стороны. Union, а не string: значение участвует в разметке и ловится компилятором. */
type OrganizationRole = 'Владелец сайта' | 'Пользователь сайта';

interface RequisiteItem {
  label: string;
  value: string;
  /** Задан только у телефона и почты — остальные реквизиты остаются текстом */
  href?: string;
}

interface Organization {
  role: OrganizationRole;
  /** Полное наименование в том виде, в каком оно указано в ЕГРИП */
  name: string;
  items: ReadonlyArray<RequisiteItem>;
}

// TODO: в дальнейшем заменить на fetch из API (модель Company или аналог)
const organizations: ReadonlyArray<Organization> = [
  {
    role: 'Владелец сайта',
    name: 'Индивидуальный предприниматель Терещенко Людмила Викторовна',
    items: [
      {
        label: 'Юридический адрес',
        value:
          '359046, Республика Калмыкия, р-н Приютненский, п Первомайский, ул Южная, д. 2, кв. 2',
      },
      { label: 'Телефон', value: '+7 962 000 35 21', href: 'tel:+79620003521' },
      { label: 'ИНН', value: '263622926082' },
      { label: 'ОГРНИП', value: '321265100078260' },
      { label: 'Расчётный счёт', value: '40802810310590002502' },
      { label: 'Корреспондентский счёт', value: '30101810145250000411' },
      { label: 'БИК банка', value: '044525411' },
      { label: 'Банк', value: 'Филиал «ЦЕНТРАЛЬНЫЙ» БАНКА ВТБ (ПАО)' },
      { label: 'Почта', value: 'tili-bom@bk.ru', href: 'mailto:tili-bom@bk.ru' },
    ],
  },
  {
    role: 'Пользователь сайта',
    name: 'Индивидуальный предприниматель Семерюк Дмитрий Владимирович',
    items: [
      {
        label: 'Юридический адрес',
        value: '359010, Республика Калмыкия, р-н Яшалтинский, с Яшалта, ул Трудовая, д. 24, кв. 5',
      },
      {
        label: 'Почтовый адрес',
        value:
          '355041, Ставропольский край, г.о. городской округ город Ставрополь, г Ставрополь, ул Лермонтова, д. 271, а/я 4601',
      },
      { label: 'Телефон', value: '+7 962 000 35 21', href: 'tel:+79620003521' },
      { label: 'ИНН', value: '263511809023' },
      { label: 'ОГРНИП', value: '321265100084165' },
      { label: 'Расчётный счёт', value: '40802810860100012258' },
      { label: 'Корреспондентский счёт', value: '30101810907020000615' },
      { label: 'БИК банка', value: '040702615' },
      { label: 'Банк', value: 'СТАВРОПОЛЬСКОЕ ОТДЕЛЕНИЕ N5230 ПАО СБЕРБАНК' },
      { label: 'Почта', value: 'semerukdv@yandex.ru', href: 'mailto:semerukdv@yandex.ru' },
      { label: 'Номер GLN', value: '4630551359997' },
    ],
  },
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

      <section className="container mx-auto space-y-6 px-4 py-8 sm:space-y-8 sm:py-12">
        {organizations.map(({ role, name, items }, orgIndex) => {
          // Роль внутри h2: иначе при навигации по заголовкам два блока неразличимы на слух
          const headingId = `requisites-org-${orgIndex}`;

          return (
            <Card key={`${role}-${orgIndex}`} className="p-6 sm:p-8">
              <h2
                id={headingId}
                className="text-title-l text-text-primary mb-6 break-words sm:mb-8"
              >
                <span className="text-body-s text-text-muted mb-1 block">{role}</span>
                {name}
              </h2>

              <dl aria-labelledby={headingId} className="divide-y divide-neutral-300">
                {items.map(({ label, value, href }, itemIndex) => (
                  <div
                    key={`${label}-${itemIndex}`}
                    className="flex flex-col gap-1 py-3 sm:flex-row sm:gap-6 sm:py-4"
                  >
                    <dt className="text-body-s text-text-muted sm:w-64 sm:flex-shrink-0 sm:pt-0.5">
                      {label}
                    </dt>
                    <dd className="text-body-m text-text-primary min-w-0 font-semibold break-words">
                      {href ? (
                        <a
                          href={href}
                          className="text-primary hover:text-primary-hover hover:underline"
                        >
                          {value}
                        </a>
                      ) : (
                        value
                      )}
                    </dd>
                  </div>
                ))}
              </dl>
            </Card>
          );
        })}
      </section>
    </div>
  );
}
