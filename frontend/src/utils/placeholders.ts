/**
 * Placeholder utilities для изображений
 * Используется до получения финальных assets (Story 12.7)
 */

/**
 * Генерирует shimmer placeholder для Next.js Image
 */
export function shimmer(width: number, height: number): string {
  return `
<svg width="${width}" height="${height}" version="1.1" xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink">
  <defs>
    <linearGradient id="g">
      <stop stop-color="#F5F7FB" offset="20%" />
      <stop stop-color="#E0E0E0" offset="50%" />
      <stop stop-color="#F5F7FB" offset="70%" />
    </linearGradient>
  </defs>
  <rect width="${width}" height="${height}" fill="#F5F7FB" />
  <rect id="r" width="${width}" height="${height}" fill="url(#g)" />
  <animate xlink:href="#r" attributeName="x" from="-${width}" to="${width}" dur="1s" repeatCount="indefinite"  />
</svg>`;
}

/**
 * Конвертирует SVG в base64 data URI
 */
export function toBase64(str: string): string {
  return typeof window === 'undefined'
    ? Buffer.from(str).toString('base64')
    : window.btoa(unescape(encodeURIComponent(str)));
}

/**
 * Генерирует placeholder категории с названием
 */
export function categoryPlaceholder(
  name: string,
  width: number = 300,
  height: number = 200
): string {
  const svg = `
<svg width="${width}" height="${height}" xmlns="http://www.w3.org/2000/svg">
  <rect width="${width}" height="${height}" fill="#F5F7FB"/>
  <text
    x="50%"
    y="50%"
    font-family="Arial, sans-serif"
    font-size="24"
    font-weight="600"
    fill="#1F1F1F"
    text-anchor="middle"
    dominant-baseline="middle"
  >
    ${name}
  </text>
</svg>`;

  return `data:image/svg+xml;base64,${toBase64(svg)}`;
}

/**
 * Генерирует blog post placeholder
 */
export function blogPlaceholder(width: number = 400, height: number = 225): string {
  return `data:image/svg+xml;base64,${toBase64(shimmer(width, height))}`;
}
