/**
 * Разметка schema.org уровня сайта (стори 41.6, AC6).
 *
 * Здесь закрепляются три вещи, которые легко потерять при правках:
 *  1. блок ровно один — вторая копия `@graph` на странице даёт роботу два
 *     конкурирующих описания одной организации;
 *  2. `WebSite.publisher` ссылается на `Organization` по `@id` — иначе узлы
 *     лежат рядом, но не связаны;
 *  3. `potentialAction`/`SearchAction` отсутствует — `/search` перечислен в
 *     `Disallow` robots.txt, и объявлять действие, ведущее в закрытый раздел,
 *     значит противоречить самим себе.
 */

import { describe, it, expect, vi, afterEach } from 'vitest';
import { render } from '@testing-library/react';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

import { SiteJsonLd } from '../SiteJsonLd';
import { SUPPORT_EMAIL, SUPPORT_PHONE_DISPLAY } from '@/config/contacts';
import { ORGANIZATION_ID, WEBSITE_ID } from '@/config/organization';
import { SITE_NAME, SITE_URL } from '@/utils/seo';

const FRONTEND_DIR = path.resolve(
  path.dirname(fileURLToPath(import.meta.url)),
  '..',
  '..',
  '..',
  '..'
);
const LOGO_FILE = path.join(FRONTEND_DIR, 'public', 'LOGO_OPTIsport.png');

/**
 * Разбирает габариты PNG по чанку IHDR: подпись(8) + длина(4) + тип(4) +
 * ширина(4) + высота(4). Файл читается напрямую, чтобы страж сверял разметку с
 * самим логотипом, а не с копией тех же литералов рядом.
 *
 * Как и JPEG-страж соцпревью, при непонятном файле обязан падать с внятным
 * сообщением: молча разобранный мусор хуже упавшего теста.
 */
function readPngSize(file: string): { width: number; height: number } {
  const data = fs.readFileSync(file);
  const signature = Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]);

  if (data.length < 24 || !data.subarray(0, 8).equals(signature)) {
    throw new Error(`Файл ${file} не начинается с подписи PNG`);
  }

  if (data.subarray(12, 16).toString('ascii') !== 'IHDR') {
    throw new Error(`В файле ${file} первый чанк не IHDR — заголовок PNG повреждён`);
  }

  return { width: data.readUInt32BE(16), height: data.readUInt32BE(20) };
}

/** Разбирает единственный ld+json-блок компонента */
function renderGraph() {
  const { container } = render(<SiteJsonLd />);
  const scripts = container.querySelectorAll('script[type="application/ld+json"]');

  expect(scripts).toHaveLength(1);

  const parsed = JSON.parse(scripts[0].textContent ?? '');
  const graph = parsed['@graph'] as Array<Record<string, unknown>>;

  return {
    parsed,
    graph,
    organization: graph.find(node => node['@type'] === 'Organization')!,
    website: graph.find(node => node['@type'] === 'WebSite')!,
  };
}

describe('SiteJsonLd', () => {
  it('отдаёт ровно один блок ld+json с корневым @graph', () => {
    const { parsed, graph } = renderGraph();

    expect(parsed['@context']).toBe('https://schema.org');
    expect(graph).toHaveLength(2);
  });

  it('содержит узлы Organization и WebSite', () => {
    const { organization, website } = renderGraph();

    expect(organization).toBeDefined();
    expect(website).toBeDefined();
  });
});

describe('SiteJsonLd: узел Organization', () => {
  it('описывает организацию обязательными полями', () => {
    const { organization } = renderGraph();

    expect(organization['@id']).toBe(ORGANIZATION_ID);
    expect(organization.name).toBe(SITE_NAME);
    expect(organization.url).toBe(SITE_URL);
    expect(organization.sameAs).toEqual(expect.arrayContaining([expect.any(String)]));
  });

  it('объявляет логотип с фактическими размерами файла', () => {
    // Размеры берутся из самого `public/LOGO_OPTIsport.png`: сверка двух копий
    // одних и тех же литералов ничего не доказывает — при замене логотипа она
    // осталась бы зелёной, а разметка врала бы роботу.
    const { width, height } = readPngSize(LOGO_FILE);
    const { organization } = renderGraph();

    expect(organization.logo).toEqual({
      '@type': 'ImageObject',
      url: `${SITE_URL}/LOGO_OPTIsport.png`,
      width,
      height,
    });
  });

  it('файл логотипа лежит по объявленному в разметке пути', () => {
    const { organization } = renderGraph();
    const logoUrl = (organization.logo as { url: string }).url;

    expect(logoUrl.startsWith(SITE_URL)).toBe(true);
    expect(path.join(FRONTEND_DIR, 'public', logoUrl.slice(SITE_URL.length))).toBe(LOGO_FILE);
    expect(fs.existsSync(LOGO_FILE)).toBe(true);
  });

  it('берёт телефон и почту из config/contacts, а не из своей копии', () => {
    const { organization } = renderGraph();

    expect(organization.telephone).toBe(SUPPORT_PHONE_DISPLAY);
    expect(organization.email).toBe(SUPPORT_EMAIL);
  });

  it('содержит почтовый адрес со страной RU', () => {
    const { organization } = renderGraph();

    expect(organization.address).toMatchObject({
      '@type': 'PostalAddress',
      addressCountry: 'RU',
    });
  });
});

describe('SiteJsonLd: узел WebSite', () => {
  it('связан с организацией через publisher → @id', () => {
    const { website, organization } = renderGraph();

    expect(website['@id']).toBe(WEBSITE_ID);
    expect(website.publisher).toEqual({ '@id': organization['@id'] });
  });

  it('объявляет язык и адрес сайта', () => {
    const { website } = renderGraph();

    expect(website.name).toBe(SITE_NAME);
    expect(website.url).toBe(SITE_URL);
    expect(website.inLanguage).toBe('ru-RU');
  });

  it('не объявляет potentialAction — /search закрыт в robots.txt', () => {
    const { website } = renderGraph();

    expect(website.potentialAction).toBeUndefined();
  });
});

describe('SiteJsonLd: абсолютные URL', () => {
  it('строит все ссылки из SITE_URL, а не из захардкоженного домена', () => {
    const { container } = render(<SiteJsonLd />);
    const json = container.querySelector('script')?.textContent ?? '';

    for (const url of [ORGANIZATION_ID, WEBSITE_ID]) {
      expect(url.startsWith(SITE_URL)).toBe(true);
    }
    // Домен появляется в разметке только как часть SITE_URL
    const hardcoded = json.match(/https:\/\/optisport\.ru/g) ?? [];
    const fromSiteUrl = SITE_URL.startsWith('https://optisport.ru')
      ? (json.match(new RegExp(SITE_URL.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'), 'g')) ?? []).length
      : 0;
    expect(hardcoded.length).toBe(fromSiteUrl);
  });
});

describe('SiteJsonLd: экранирование при сериализации', () => {
  // Очистка вынесена в afterEach, а не в конец теста: подмена окружения,
  // снятая после assertions, при первом же падении переживает свой тест —
  // подменённый NEXT_PUBLIC_APP_URL и кеш модулей утекают дальше и прячут
  // первопричину за каскадом чужих ошибок.
  afterEach(() => {
    vi.unstubAllEnvs();
    vi.resetModules();
  });

  it('не выпускает в разметку литеральный `<`, пришедший из окружения', async () => {
    // `SITE_URL` берётся из `NEXT_PUBLIC_APP_URL` — это значение окружения, а не
    // литеральная константа модуля. Литеральный `</script>` внутри инлайн-скрипта
    // закрывает тег, поэтому `<` уходит в разметку только как `\\u003c`.
    vi.resetModules();
    vi.stubEnv('NEXT_PUBLIC_APP_URL', 'https://x.test/</script><img src=x>');

    const { SiteJsonLd: Reloaded } = await import('../SiteJsonLd');
    const { container } = render(<Reloaded />);
    const script = container.querySelector('script[type="application/ld+json"]')!;
    const html = script.innerHTML;

    expect(html).not.toContain('<');
    expect(html).toContain('\\u003c');
    // Экранирование не должно ломать разбор: робот обязан прочитать тот же граф
    expect(JSON.parse(script.textContent ?? '')['@graph']).toHaveLength(2);
  });

  it('оставляет разметку валидным JSON при обычных данных', () => {
    const { container } = render(<SiteJsonLd />);
    const script = container.querySelector('script[type="application/ld+json"]')!;

    expect(script.innerHTML).not.toContain('<');
    expect(() => JSON.parse(script.textContent ?? '')).not.toThrow();
  });
});
