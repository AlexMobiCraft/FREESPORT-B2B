/**
 * Mock данные для блога (Story 12.7)
 */

export interface BlogPost {
  id: string;
  title: string;
  excerpt: string;
  image: string;
  date: string;
  slug: string;
  author?: string;
  category?: string;
}

export const MOCK_BLOG_POSTS: BlogPost[] = [
  {
    id: '1',
    title: 'Как выбрать правильные кроссовки?',
    excerpt: 'Разбираем типы покрытия, поддержку стопы и нюансы посадки для разных дистанций.',
    image: '/images/blog/cross.jpg',
    date: '2025-11-15',
    slug: 'kak-vybrat-pravilnye-krossovki',
    author: 'Редакция FREESPORT',
    category: 'Советы',
  },
  {
    id: '2',
    title: 'Обзор новой линейки одежды для йоги',
    excerpt: 'Тестируем мягкие ткани, свободный крой и новые цвета для комфортных занятий.',
    image: '/images/blog/joga.jpg',
    date: '2025-11-12',
    slug: 'obzor-odezhdy-dlya-yogi',
    author: 'Редакция FREESPORT',
    category: 'Обзоры',
  },
  {
    id: '3',
    title: 'Топ-5 упражнений для силовых тренировок',
    excerpt: 'Подборка базовых движений для дома и зала: техника, подходы и советы тренера.',
    image: '/images/blog/top-5.jpg',
    date: '2025-11-10',
    slug: 'top-5-uprazhneniy-dlya-sily',
    author: 'Редакция FREESPORT',
    category: 'Тренировки',
  },
];
