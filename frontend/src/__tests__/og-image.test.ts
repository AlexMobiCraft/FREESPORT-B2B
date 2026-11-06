/**
 * Тест-страж соцпревью (стори 41.6, AC4/AC5/AC7).
 *
 * Размеры `og:image` объявляются константами в `utils/seo.ts`, а браузер и
 * робот читают их из файла. Сверять две константы между собой бессмысленно —
 * поэтому здесь разбирается заголовок самого `public/image.jpg`. Когда владелец
 * принесёт файл 1200×630, тест сразу скажет, если константы не поменяли.
 *
 * Вторая половина — про `og-image.jpg`. Файл назывался как соцпревью, а работал
 * как заглушка hero: его читали `HeroSection` и `ElectricHeroSection`, и простое
 * удаление дало бы битую картинку ровно в тот момент, когда API баннеров
 * недоступен. Стори переименовала его в `hero-fallback.jpg`; здесь закреплено,
 * что старое имя не вернулось ни файлом, ни ссылкой из кода.
 */

import { describe, it, expect } from 'vitest';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

import {
  DEFAULT_OG_IMAGE,
  DEFAULT_OG_IMAGE_HEIGHT,
  DEFAULT_OG_IMAGE_TYPE,
  DEFAULT_OG_IMAGE_WIDTH,
} from '@/utils/seo';

const SRC_DIR = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const FRONTEND_DIR = path.resolve(SRC_DIR, '..');
const PUBLIC_DIR = path.join(FRONTEND_DIR, 'public');

/**
 * Разбирает габариты JPEG по маркеру SOF (0xFFC0…0xFFCF, кроме 0xC4/0xC8/0xCC).
 * Заголовок читается напрямую, чтобы не тянуть в тесты графическую зависимость.
 *
 * Страж обязан падать с внятным сообщением, а не возвращать правдоподобный
 * мусор: молча разобранные «размеры» испорченного файла — худший исход, чем
 * упавший тест. Отсюда проверки SOI, границ сегмента и его минимальной длины.
 */
function readJpegSize(file: string): { width: number; height: number } {
  const data = fs.readFileSync(file);

  if (data.length < 4 || data[0] !== 0xff || data[1] !== 0xd8) {
    throw new Error(`Файл ${file} не начинается с маркера SOI (0xFFD8) — это не JPEG`);
  }

  let offset = 2; // пропускаем SOI (0xFFD8)

  while (offset + 1 < data.length) {
    if (data[offset] !== 0xff) {
      offset += 1;
      continue;
    }

    const marker = data[offset + 1];

    // Байт-заполнитель: перед маркером стандарт разрешает сколько угодно 0xFF.
    // Сдвигаемся на один байт, иначе `FF FF C0` разберётся как маркер 0xFF,
    // а следующие два байта — как его длина, то есть как мусор.
    if (marker === 0xff) {
      offset += 1;
      continue;
    }

    // Маркеры без полезной нагрузки
    if (marker === 0xd8 || marker === 0x01 || (marker >= 0xd0 && marker <= 0xd7)) {
      offset += 2;
      continue;
    }

    // EOI: дальше данных нет, SOF уже не встретится
    if (marker === 0xd9) break;

    if (offset + 4 > data.length) {
      throw new Error(`Обрезанный сегмент JPEG в файле ${file}: не хватает поля длины`);
    }

    const segmentLength = data.readUInt16BE(offset + 2);

    if (segmentLength < 2 || offset + 2 + segmentLength > data.length) {
      throw new Error(
        `Некорректный сегмент JPEG в файле ${file}: длина ${segmentLength} выходит за границы`
      );
    }

    const isStartOfFrame =
      marker >= 0xc0 && marker <= 0xcf && marker !== 0xc4 && marker !== 0xc8 && marker !== 0xcc;

    if (isStartOfFrame) {
      // SOF: длина(2) + точность(1) + высота(2) + ширина(2) = минимум 7 байт
      if (segmentLength < 7) {
        throw new Error(`Сегмент SOF в файле ${file} короче обязательных 7 байт`);
      }

      return {
        height: data.readUInt16BE(offset + 5),
        width: data.readUInt16BE(offset + 7),
      };
    }

    offset += 2 + segmentLength;
  }

  throw new Error(`Не найден SOF-маркер JPEG в файле ${file}`);
}

/** Все файлы `src/`, кроме каталогов сборки */
function collectSourceFiles(dir: string, acc: string[] = []): string[] {
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    const full = path.join(dir, entry.name);

    if (entry.isDirectory()) {
      if (entry.name === 'node_modules' || entry.name === '.next') continue;
      collectSourceFiles(full, acc);
    } else {
      acc.push(full);
    }
  }

  return acc;
}

describe('Соцпревью: константы совпадают с файлом', () => {
  it('размеры public/image.jpg равны объявленным в utils/seo.ts', () => {
    const { width, height } = readJpegSize(path.join(PUBLIC_DIR, 'image.jpg'));

    expect(width).toBe(DEFAULT_OG_IMAGE_WIDTH);
    expect(height).toBe(DEFAULT_OG_IMAGE_HEIGHT);
  });

  it('объявленный MIME-тип соответствует расширению файла', () => {
    expect(DEFAULT_OG_IMAGE.endsWith('.jpg')).toBe(true);
    expect(DEFAULT_OG_IMAGE_TYPE).toBe('image/jpeg');
  });

  it('файл соцпревью существует по объявленному пути', () => {
    expect(fs.existsSync(path.join(PUBLIC_DIR, DEFAULT_OG_IMAGE.replace(/^\//, '')))).toBe(true);
  });
});

describe('Заглушка hero: og-image.jpg не вернулся', () => {
  it('public/og-image.jpg отсутствует', () => {
    expect(fs.existsSync(path.join(PUBLIC_DIR, 'og-image.jpg'))).toBe(false);
  });

  it('public/hero-fallback.jpg существует', () => {
    expect(fs.existsSync(path.join(PUBLIC_DIR, 'hero-fallback.jpg'))).toBe(true);
  });

  it('в src/ нет ссылок на /og-image', () => {
    // Ищем именно путь к файлу: голая подстрока `og-image` даёт ложное
    // срабатывание на чужой фикстуре `blog-image.jpg` в тестах блога.
    const pattern = /(^|[^\w-])og-image/;
    const offenders = collectSourceFiles(SRC_DIR).filter(file => {
      if (file === fileURLToPath(import.meta.url)) return false;
      return pattern.test(fs.readFileSync(file, 'utf-8'));
    });

    expect(offenders.map(file => path.relative(FRONTEND_DIR, file))).toEqual([]);
  });
});

describe('Разбор JPEG: корректность самого стража', () => {
  /** Собирает минимальный JPEG: SOI + произвольные сегменты + SOF0 */
  function buildJpeg({
    width,
    height,
    fillBytes = 0,
    withApp0 = true,
  }: {
    width: number;
    height: number;
    fillBytes?: number;
    withApp0?: boolean;
  }): Buffer {
    const parts: Buffer[] = [Buffer.from([0xff, 0xd8])];

    if (withApp0) {
      // APP0 с двумя байтами полезной нагрузки: длина считает саму себя
      parts.push(Buffer.from([0xff, 0xe0, 0x00, 0x04, 0x4a, 0x46]));
    }

    // Байты-заполнители: по стандарту перед маркером их может быть сколько угодно
    if (fillBytes > 0) parts.push(Buffer.alloc(fillBytes, 0xff));

    const sof = Buffer.alloc(11);
    sof.writeUInt8(0xff, 0);
    sof.writeUInt8(0xc0, 1);
    sof.writeUInt16BE(9, 2); // длина сегмента
    sof.writeUInt8(8, 4); // точность
    sof.writeUInt16BE(height, 5);
    sof.writeUInt16BE(width, 7);
    sof.writeUInt8(1, 9); // число компонентов
    parts.push(sof);

    return Buffer.concat(parts);
  }

  /** Кладёт буфер во временный файл — страж работает с путями, не с буферами */
  function withTempFile(buffer: Buffer, run: (file: string) => void): void {
    const file = path.join(
      fs.mkdtempSync(path.join(os.tmpdir(), 'og-image-guard-')),
      'sample.jpg'
    );
    fs.writeFileSync(file, buffer);

    try {
      run(file);
    } finally {
      fs.rmSync(path.dirname(file), { recursive: true, force: true });
    }
  }

  it('читает размеры из обычного JPEG', () => {
    withTempFile(buildJpeg({ width: 1040, height: 680 }), file => {
      expect(readJpegSize(file)).toEqual({ width: 1040, height: 680 });
    });
  });

  it('не сбивается на байтах-заполнителях 0xFF перед маркером', () => {
    // `FF FF C0` — валидная последовательность: лишние 0xFF просто пропускаются.
    // Наивный разбор принимает второй 0xFF за маркер и читает мусорную длину.
    withTempFile(buildJpeg({ width: 800, height: 600, fillBytes: 3 }), file => {
      expect(readJpegSize(file)).toEqual({ width: 800, height: 600 });
    });
  });

  it('отвергает файл без SOI-маркера', () => {
    withTempFile(Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x00, 0x00]), file => {
      expect(() => readJpegSize(file)).toThrow(/SOI/);
    });
  });

  it('отвергает сегмент с длиной за границей файла', () => {
    const broken = Buffer.from([0xff, 0xd8, 0xff, 0xe0, 0x7f, 0xff, 0x00]);
    withTempFile(broken, file => {
      expect(() => readJpegSize(file)).toThrow(/сегмент/i);
    });
  });

  it('отвергает сегмент с длиной меньше двух байт', () => {
    const broken = Buffer.from([0xff, 0xd8, 0xff, 0xe0, 0x00, 0x01, 0x00, 0x00]);
    withTempFile(broken, file => {
      expect(() => readJpegSize(file)).toThrow(/сегмент/i);
    });
  });

  it('сообщает об отсутствии SOF, а не возвращает мусор', () => {
    const noSof = Buffer.from([0xff, 0xd8, 0xff, 0xe0, 0x00, 0x04, 0x4a, 0x46, 0xff, 0xd9]);
    withTempFile(noSof, file => {
      expect(() => readJpegSize(file)).toThrow(/SOF/);
    });
  });
});
