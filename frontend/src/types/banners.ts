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
  /** Баннер помечен как реклама — показывать метку «Реклама» с реквизитами */
  is_advertisement: boolean;
  /** Наименование рекламодателя, например: ООО "Прайм Спорт Рус" */
  advertiser_name: string;
  /** ИНН рекламодателя: 10 цифр (юрлицо) или 12 (ИП, физлицо) */
  advertiser_inn: string;
  /** Токен ERID из ОРД (пустая строка, если не присвоен) */
  erid: string;
}
