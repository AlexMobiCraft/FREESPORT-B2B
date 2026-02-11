/**
 * Утилиты для работы с медиа-файлами
 * Нормализация URL изображений для корректной работы в Docker
 */

/**
 * Нормализует URL изображения для отображения в браузере
 * Заменяет внутренние Docker URL на публичные
 *
 * @param url - URL изображения (может быть относительным или абсолютным)
 * @returns Нормализованный URL для браузера
 */
export function normalizeImageUrl(url: string | null | undefined): string {
  if (!url) {
    return '/images/No_image.svg';
  }

  // Заменяем внутренние Docker URL на публичные
  const internalPatterns = [
    'http://backend:8000',
    'http://nginx',
    'http://localhost:8001',
    'http://localhost:8000',
  ];

  let normalizedUrl = url;

  for (const pattern of internalPatterns) {
    if (normalizedUrl.startsWith(pattern)) {
      // Извлекаем путь после хоста
      normalizedUrl = normalizedUrl.replace(pattern, '');
      break;
    }
  }

  // Если URL относительный (начинается с /), возвращаем как есть
  // Nginx обработает /media/ пути
  if (normalizedUrl.startsWith('/')) {
    return normalizedUrl;
  }

  // Если URL уже публичный (http/https), возвращаем как есть
  return normalizedUrl;
}

/**
 * Нормализует массив URL изображений
 *
 * @param urls - Массив URL изображений
 * @returns Массив нормализованных URL
 */
export function normalizeImageUrls(urls: (string | null | undefined)[]): string[] {
  return urls.map(url => normalizeImageUrl(url)).filter(url => url !== '/images/No_image.svg');
}
