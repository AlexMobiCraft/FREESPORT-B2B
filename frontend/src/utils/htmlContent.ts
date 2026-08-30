/**
 * Извлекает содержимое <body> из полного HTML-документа.
 * Если <body> отсутствует, возвращает исходную строку как есть.
 */
export function extractBodyContent(html: string): string {
  if (!html || typeof html !== 'string') {
    return '';
  }

  const match = html.match(/<body[^>]*>([\s\S]*)<\/body>/i);
  return match ? match[1].trim() : html.trim();
}
