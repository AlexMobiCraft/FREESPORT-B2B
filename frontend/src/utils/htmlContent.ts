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

// Содержимое <script>/<style> — не текст описания: вырезается вместе с тегами.
const SCRIPT_STYLE_RE = /<(script|style)\b[^>]*>[\s\S]*?<\/\1\s*>/gi;
// <br> с любыми атрибутами → перевод строки; два <br> подряд дают пустую строку
const BR_RE = /<br\b[^>]*>/gi;
// Цепочка блочных тегов (открывающих и закрывающих) → один перевод строки,
// иначе соседние блоки склеились бы: «<li>NBR</li><li>183 см</li>» → «NBR183 см»
const BLOCK_RUN_RE =
  /(?:\s*<\/?(?:p|div|li|ul|ol|h[1-6]|tr|table|blockquote|section|article)\b[^>]*>)+\s*/gi;
// Ячейки таблицы → пробел
const CELL_RE = /<\/?t[dh]\b[^>]*>/gi;
// Тег — только `<` + буква, `/`, `!` (комментарий, DOCTYPE): «размер < 5 и > 3» остаётся текстом.
const TAG_RE = /<(?:\/?[a-zA-Z][^>]*|!--[\s\S]*?--|![^>]*)>/g;
const ENTITY_RE = /&(#\d+|#x[0-9a-f]+|[a-z]+);/gi;
const NAMED_ENTITIES: Record<string, string> = {
  amp: '&',
  lt: '<',
  gt: '>',
  quot: '"',
  apos: "'",
  nbsp: ' ',
  laquo: '«',
  raquo: '»',
  bdquo: '„',
  ldquo: '“',
  rdquo: '”',
  lsquo: '‘',
  rsquo: '’',
  mdash: '—',
  ndash: '–',
  minus: '−',
  hellip: '…',
  deg: '°',
  times: '×',
  middot: '·',
  copy: '©',
  reg: '®',
  trade: '™',
};

/**
 * Декодирует сущности за один проход: `&amp;lt;` даёт `&lt;`, а не `<`.
 * Неизвестная сущность остаётся как есть.
 */
function decodeEntities(text: string): string {
  return text.replace(ENTITY_RE, (entity, code: string) => {
    if (code[0] === '#') {
      const isHex = code[1] === 'x' || code[1] === 'X';
      const codePoint = parseInt(code.slice(isHex ? 2 : 1), isHex ? 16 : 10);
      const valid =
        codePoint > 0 && codePoint <= 0x10ffff && (codePoint < 0xd800 || codePoint > 0xdfff);
      return valid ? String.fromCodePoint(codePoint) : entity;
    }
    return NAMED_ENTITIES[code.toLowerCase()] ?? entity;
  });
}

/**
 * Переводит HTML-фрагмент из 1С в простой текст для вывода как текст.
 * `<br>` и блочные теги → перевод строки, `<script>`/`<style>` вырезаются
 * с содержимым, остальные теги удаляются, сущности декодируются. Это не
 * санитайзер: результат нельзя вставлять как HTML — только как текст,
 * который экранирует React.
 */
export function htmlToPlainText(html: string | null | undefined): string {
  if (!html || typeof html !== 'string') {
    return '';
  }

  const text = decodeEntities(
    html
      .replace(/\r\n?/g, '\n')
      .replace(SCRIPT_STYLE_RE, '')
      .replace(BLOCK_RUN_RE, '\n')
      .replace(BR_RE, '\n')
      .replace(CELL_RE, ' ')
      .replace(TAG_RE, '')
  );

  return (
    text
      .split('\n')
      // Любые пробельные символы, кроме перевода строки (в том числе U+00A0 от &nbsp;)
      .map(line => line.replace(/[^\S\n]+/g, ' ').trim())
      .join('\n')
      .replace(/\n{3,}/g, '\n\n')
      .trim()
  );
}

/**
 * Схлопывает пробелы и переводы строк в один пробел (для meta и JSON-LD).
 */
export function collapseWhitespace(text: string): string {
  return (text ?? '').replace(/\s+/g, ' ').trim();
}

const WORD_CHAR_RE = /[\p{L}\p{N}]/u;

/**
 * Текст для meta/og description: пробелы и переводы строк схлопнуты,
 * длина не больше `max`, обрезка по границе слова без многоточия.
 */
export function toMetaDescription(text: string, max = 160): string {
  const collapsed = collapseWhitespace(text);
  if (collapsed.length <= max) {
    return collapsed;
  }

  let cut = collapsed.slice(0, max);
  // Слово разорвано, только если по обе стороны среза буквы или цифры
  if (WORD_CHAR_RE.test(collapsed[max]) && WORD_CHAR_RE.test(cut[cut.length - 1])) {
    const lastSpace = cut.lastIndexOf(' ');
    if (lastSpace > 0) {
      cut = cut.slice(0, lastSpace);
    }
  }
  // Жёсткая обрезка могла разделить суррогатную пару (эмодзи)
  const lastCode = cut.charCodeAt(cut.length - 1);
  if (lastCode >= 0xd800 && lastCode <= 0xdbff) {
    cut = cut.slice(0, -1);
  }
  // Висящие знаки препинания и открывающие скобки/кавычки в конце не нужны
  return cut.replace(/[\s,;:—–(«"„“[-]+$/, '');
}
