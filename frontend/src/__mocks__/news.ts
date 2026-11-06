/**
 * Статические данные для новостей (fallback для /news)
 */

export interface StaticNewsItem {
  id: number;
  title: string;
  slug: string;
  excerpt: string;
  image: string;
  published_at: string;
}

export const STATIC_NEWS_ITEMS: StaticNewsItem[] = [
  {
    id: 1,
    title: 'Новое поступление беговой экипировки',
    slug: 'novoe-postuplenie-begovoy-ekipirovki',
    excerpt: 'Рассказываем о ключевых моделях и технологиях в свежей коллекции.',
    image: '/images/new/running-shoes.jpg',
    published_at: '2025-11-15T10:00:00+03:00',
  },
  {
    id: 2,
    title: 'Фитнес-оборудование со скидками',
    slug: 'fitnes-oborudovanie-so-skidkami',
    excerpt: 'Гантели, гири и тренажёры доступны по специальным ценам до конца месяца.',
    image: '/images/new/fitnes.jpg',
    published_at: '2025-11-12T10:00:00+03:00',
  },
  {
    id: 3,
    title: 'Открытие обновлённого шоурума',
    slug: 'otkrytie-obnovlennogo-shouruma',
    excerpt: 'Приглашаем протестировать новинки и получить персональную консультацию.',
    image: '/images/new/mosow-shop.jpg',
    published_at: '2025-11-10T10:00:00+03:00',
  },
];
