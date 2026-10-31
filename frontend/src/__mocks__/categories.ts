/**
 * Mock данные для категорий (Story 12.7)
 * Используются для development и тестирования
 *
 * TODO: Заменить placeholder изображения на реальные после завершения Epic по production assets
 */

export const MOCK_CATEGORIES = [
  {
    id: 1,
    name: 'Футбол',
    slug: 'futbol',
    href: '/catalog?category=futbol',
    image: '/images/categories/football.jpg',
    alt: 'Спортивная одежда и инвентарь для футбола',
  },
  {
    id: 2,
    name: 'Фитнес',
    slug: 'fitness',
    href: '/catalog?category=fitnes',
    image: '/images/categories/fitness.jpg',
    alt: 'Товары для фитнеса и тренировок',
  },
  {
    id: 3,
    name: 'Единоборства',
    slug: 'edinoborstva',
    href: '/catalog?category=edinoborstva',
    image: '/images/categories/martial-arts.jpg',
    alt: 'Экипировка для единоборств',
  },
  {
    id: 4,
    name: 'Плавание',
    slug: 'plavanie',
    href: '/catalog?category=plavanie',
    image: '/images/categories/swimming.jpg',
    alt: 'Товары для плавания',
  },
  {
    id: 5,
    name: 'Детский транспорт',
    slug: 'detskij-transport',
    href: '/catalog?category=detskij-transport',
    image: '/images/categories/kids-transport.jpg',
    alt: 'Детские велосипеды, самокаты, ролики',
  },
];
