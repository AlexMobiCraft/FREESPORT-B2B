/**
 * Тест-страж: текст чекбокса согласия в форме обязан дословно совпадать с
 * текущей ревизией реестра `backend/apps/common/consent_texts.json` (стори 41.9).
 *
 * Зачем это здесь, а не в pytest. Бэкенд физически не может прочитать формы:
 * контекст сборки backend-образа — `../backend`, в тестовый контейнер смонтирован
 * только он (`docker/docker-compose.test.yml`). Vitest может: `frontend-ci.yml`
 * делает полный `actions/checkout`, соседний `backend/` лежит рядом на диске.
 *
 * Почему страж обязан падать, а не пропускаться. Каждая запись `UserConsent`
 * хранит версию формулировки, вычисленную из текста реестра. Если текст в форме
 * поехал, а реестр не обновили, журнал согласий начнёт утверждать, что человек
 * подтвердил формулировку, которой не видел, — то есть перестанет быть
 * доказательством по ФЗ-152 ст. 9. Молча пропущенный страж охраняет ровно ничего
 * (находка ревью стори 41.6), поэтому отсутствие или порча файла реестра — это
 * падение с указанием ожидаемого пути.
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, cleanup } from '@testing-library/react';
import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import { fileURLToPath } from 'node:url';

import { SubscribeForm } from '@/components/home/SubscribeForm';
import { ElectricSubscribeForm } from '@/components/home/ElectricSubscribeForm';
import { RegisterForm } from '@/components/auth/RegisterForm';
import { B2BRegisterForm } from '@/components/auth/B2BRegisterForm';
import { CONSENT_TEXT_VERSIONS } from '@/constants/consentTexts';

const REGISTRY_PATH = path.resolve(
  path.dirname(fileURLToPath(import.meta.url)),
  '..',
  '..',
  '..',
  'backend',
  'apps',
  'common',
  'consent_texts.json'
);

interface ConsentRevision {
  label: string;
  text: string;
}

interface ConsentRegistry {
  surfaces: Record<string, { revisions: ConsentRevision[] }>;
  bindings: Record<string, string>;
  known_versions: string[];
}

/**
 * Читает реестр и падает с внятным сообщением, называющим ожидаемый путь.
 * Пропуск (`skipIf`, ранний `return`) здесь запрещён: страж, который молчит
 * при ненайденном файле, не охраняет ничего.
 */
function readRegistry(): ConsentRegistry {
  let raw: string;
  try {
    raw = fs.readFileSync(REGISTRY_PATH, 'utf-8');
  } catch (error) {
    throw new Error(
      `Реестр текстов согласий не читается: ${REGISTRY_PATH}. ` +
        `Он обязан существовать — по нему вычисляется UserConsent.consent_text_version. ` +
        `Исходная ошибка: ${(error as Error).message}`
    );
  }

  let parsed: unknown;
  try {
    parsed = JSON.parse(raw);
  } catch (error) {
    throw new Error(
      `Реестр текстов согласий ${REGISTRY_PATH} не разбирается как JSON: ${(error as Error).message}`
    );
  }

  const registry = parsed as ConsentRegistry;
  if (!registry?.surfaces || !registry?.bindings) {
    throw new Error(
      `Реестр текстов согласий ${REGISTRY_PATH} не содержит разделов surfaces и bindings`
    );
  }
  return registry;
}

const registry = readRegistry();

/** Действующая формулировка поверхности — последняя ревизия: история дополняется, а не переписывается. */
function currentText(surface: string): string {
  const revisions = registry.surfaces[surface]?.revisions;
  if (!revisions?.length) {
    throw new Error(
      `В реестре ${REGISTRY_PATH} нет поверхности '${surface}' или у неё пустой список ревизий`
    );
  }
  return revisions[revisions.length - 1].text;
}

/**
 * Длина хеша в версии — `VERSION_DIGEST_HEX_LENGTH` из
 * `backend/apps/common/consent_texts.py`: 32 hex, то есть 128 бит (шестой круг
 * ревью стори 41.9; при прежних 8 hex коллизия подбиралась перебором).
 */
const VERSION_DIGEST_HEX_LENGTH = 32;

/**
 * Версия ревизии — та же формула, что и в `backend/apps/common/consent_texts.py`:
 * метка плюс первые 32 hex sha256 текста. Считается здесь заново, а не берётся
 * из реестра готовой строкой: иначе страж сверял бы литерал с литералом и
 * остался бы зелёным при разъехавшемся тексте (урок ревью стори 41.6).
 */
function currentVersion(surface: string): string {
  const revisions = registry.surfaces[surface]?.revisions;
  if (!revisions?.length) {
    throw new Error(`В реестре ${REGISTRY_PATH} нет поверхности '${surface}'`);
  }
  const revision = revisions[revisions.length - 1];
  const digest = crypto
    .createHash('sha256')
    .update(revision.text, 'utf-8')
    .digest('hex')
    .slice(0, VERSION_DIGEST_HEX_LENGTH);
  return `${revision.label}-${digest}`;
}

const NEWSLETTER_TEXT = currentText('newsletter_checkbox');
const REGISTRATION_PDP_TEXT = currentText('registration_pdp_checkbox');
const REGISTRATION_MARKETING_TEXT = currentText('registration_marketing_checkbox');

// Моки, без которых формы не отрисуются. Взяты из существующих тест-файлов форм.
const mockPush = vi.fn();
vi.mock('next/navigation', () => ({
  useRouter: () => ({
    push: mockPush,
  }),
}));

vi.mock('@/services/authService', () => ({
  default: {
    register: vi.fn(),
    registerB2B: vi.fn(),
    refreshToken: vi.fn(),
  },
}));

vi.mock('@/services/subscribeService', () => ({
  subscribeService: {
    subscribe: vi.fn(),
  },
}));

vi.mock('react-hot-toast', () => ({
  toast: {
    success: vi.fn(),
    error: vi.fn(),
  },
}));

describe('Реестр текстов согласий сверен с формами', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    cleanup();
  });

  it('реестр читается и содержит три поверхности с непустыми ревизиями', () => {
    expect(Object.keys(registry.surfaces).sort()).toEqual([
      'newsletter_checkbox',
      'registration_marketing_checkbox',
      'registration_pdp_checkbox',
    ]);
    expect(NEWSLETTER_TEXT.length).toBeGreaterThan(0);
    expect(REGISTRATION_PDP_TEXT.length).toBeGreaterThan(0);
    expect(REGISTRATION_MARKETING_TEXT.length).toBeGreaterThan(0);
  });

  it('каждая живая пара «источник.тип согласия» привязана к существующей поверхности', () => {
    // Пары обязаны совпадать с UserConsent.SOURCE_CHOICES без `unknown`
    // (он зарезервирован за строками до миграции 0019) на два типа согласия.
    expect(Object.keys(registry.bindings).sort()).toEqual([
      '1c_link.marketing_email',
      '1c_link.pdp_contract',
      'newsletter.marketing_email',
      'newsletter.pdp_contract',
      'registration.marketing_email',
      'registration.pdp_contract',
    ]);
    for (const [pair, surface] of Object.entries(registry.bindings)) {
      expect(registry.surfaces[surface], `привязка ${pair} ссылается на ${surface}`).toBeDefined();
    }
  });

  it('константы версий фронта совпадают с действующими ревизиями реестра', () => {
    // Версия уезжает в запрос вместе с согласием и решает, примет ли её сервер.
    // Разъехавшаяся константа означала бы отказ всех форм на проде — или, что
    // хуже, запись согласия на формулировку, которой человек не видел.
    expect(CONSENT_TEXT_VERSIONS.newsletter).toBe(currentVersion('newsletter_checkbox'));
    expect(CONSENT_TEXT_VERSIONS.registrationPdp).toBe(currentVersion('registration_pdp_checkbox'));
    expect(CONSENT_TEXT_VERSIONS.registrationMarketing).toBe(
      currentVersion('registration_marketing_checkbox')
    );
  });

  it('версии форм зафиксированы в known_versions реестра', () => {
    // `known_versions` — список версий всех когда-либо действовавших формулировок.
    // Загрузчик реестра сверяет его с ревизиями и ловит одностороннюю правку или
    // удаление исторической ревизии, на которую уже ссылаются записи журнала.
    expect(registry.known_versions).toEqual(expect.arrayContaining(Object.values(CONSENT_TEXT_VERSIONS)));
  });

  it('SubscribeForm показывает текст поверхности newsletter_checkbox', () => {
    render(<SubscribeForm />);
    expect(screen.getByRole('checkbox', { name: NEWSLETTER_TEXT })).toBeInTheDocument();
  });

  it('ElectricSubscribeForm показывает тот же текст newsletter_checkbox', () => {
    render(<ElectricSubscribeForm />);
    expect(screen.getByRole('checkbox', { name: NEWSLETTER_TEXT })).toBeInTheDocument();
  });

  it('RegisterForm показывает тексты registration_pdp_checkbox и registration_marketing_checkbox', () => {
    render(<RegisterForm />);
    expect(screen.getByRole('checkbox', { name: REGISTRATION_PDP_TEXT })).toBeInTheDocument();
    expect(screen.getByRole('checkbox', { name: REGISTRATION_MARKETING_TEXT })).toBeInTheDocument();
  });

  it('B2BRegisterForm показывает те же тексты, что и RegisterForm (унификация стори 41.9)', () => {
    render(<B2BRegisterForm />);
    expect(screen.getByRole('checkbox', { name: REGISTRATION_PDP_TEXT })).toBeInTheDocument();
    expect(screen.getByRole('checkbox', { name: REGISTRATION_MARKETING_TEXT })).toBeInTheDocument();
  });
});
