import type { Metadata } from 'next';
import { Breadcrumb } from '@/components/ui';
import UnsubscribeClient from './UnsubscribeClient';

export const dynamic = 'force-dynamic';

export const metadata: Metadata = {
  title: 'Отписка от рассылки | OPTISPORT',
  description: 'Управление подпиской на маркетинговую рассылку OPTISPORT.',
  robots: { index: false, follow: false },
  referrer: 'no-referrer',
};

const breadcrumbItems = [{ label: 'Главная', href: '/' }, { label: 'Отписка от рассылки' }];

export default function UnsubscribePage() {
  // Единственный <main> страницы рендерит LayoutWrapper, здесь — обычный контейнер
  return (
    <div className="max-w-[1280px] mx-auto px-4 lg:px-6 py-6">
      <Breadcrumb items={breadcrumbItems} className="mb-6" />

      <h1 id="unsubscribe-title" className="text-display-m font-bold text-text-primary mb-8">
        Отписка от маркетинговой рассылки
      </h1>

      <section
        aria-labelledby="unsubscribe-title"
        className="bg-white rounded-[var(--radius-md)] shadow-[var(--shadow-default)] p-6 sm:p-10"
      >
        <UnsubscribeClient />
      </section>
    </div>
  );
}
