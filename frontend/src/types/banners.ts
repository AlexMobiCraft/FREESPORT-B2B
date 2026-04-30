/**
 * Типы для работы с баннерами
 * Интеграция с Django backend API /api/banners/
 */

export type BannerType = 'hero' | 'marketing';

export interface Banner {
  id: number;
  type: BannerType;
  title: string;
  subtitle: string;
  image_url: string; // Относительный путь /media/banners/...
  mobile_image_url: string; // Мобильное изображение (пустая строка если нет)
  image_alt: string; // Alt-текст для accessibility
  cta_text: string;
  cta_link: string;
}
