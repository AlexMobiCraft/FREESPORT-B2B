import type { Metadata } from 'next';

import ComingSoonClient from '@/app/ComingSoonClient';
import { buildMetadata } from '@/utils/seo';

// `/coming-soon` — фактическая главная прода (`GET https://optisport.ru/` даёт
// 307 сюда), поэтому собственные title/description ей нужны в первую очередь.
// `noIndex` здесь намеренно не ставится: менять индексируемость главной —
// не задача этой стори.
export const metadata: Metadata = buildMetadata({
  title: 'OPTISPORT скоро откроется — оптовые продажи спорттоваров',
  description:
    'OPTISPORT — оптовые и розничные продажи спортивных товаров. Сайт скоро откроется, по вопросам сотрудничества пишите на info@optisport.ru.',
  path: '/coming-soon',
});

export default function ComingSoonPage() {
  return <ComingSoonClient />;
}
