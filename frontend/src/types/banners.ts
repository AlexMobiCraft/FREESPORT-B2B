/**
 * Типы для работы с баннерами
 * Интеграция с Django backend API /api/banners/
 */

export interface Banner {
  id: number;
  title: string;
  subtitle: string;
  image_url: string; // Относительный путь /media/banners/...
  image_alt: string; // Alt-текст для accessibility
  cta_text: string;
  cta_link: string;
}
