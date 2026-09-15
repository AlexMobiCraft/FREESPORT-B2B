import type { Metadata } from 'next';
import UnsubscribeClient from './UnsubscribeClient';

export const dynamic = 'force-dynamic';

export const metadata: Metadata = {
  title: 'Отписка от рассылки | OPTISPORT',
  description: 'Управление подпиской на маркетинговую рассылку OPTISPORT.',
  robots: { index: false, follow: false },
  referrer: 'no-referrer',
};

export default function UnsubscribePage() {
  return (
    <main className="flex min-h-screen items-center justify-center bg-slate-100 px-4 py-12">
      <section
        aria-labelledby="unsubscribe-title"
        className="w-full max-w-xl rounded-2xl bg-white p-6 shadow-lg sm:p-10"
      >
        <p className="mb-3 font-semibold tracking-wide text-orange-600">OPTISPORT</p>
        <h1 id="unsubscribe-title" className="mb-5 text-3xl font-bold text-slate-950">
          Отписка от маркетинговой рассылки
        </h1>
        <UnsubscribeClient />
      </section>
    </main>
  );
}
