/**
 * Тесты страницы «Реквизиты» (/requisites)
 * Story 41.7 — Task 4 (AC1, AC5)
 *
 * Страница до этой стори не была покрыта ни одним тестом (deferred-work.md:796):
 * правка вёрстки могла потерять строку с ОГРНИП при зелёном CI. Поэтому здесь
 * проверяются не только новые номера реестра ПДн, но и ИНН/ОГРНИП обеих организаций.
 *
 * Каждая проверка привязана к своему блоку через `dl[aria-labelledby]`, а не к странице
 * целиком: иначе тест не отличит правильную страницу от страницы, где номера операторов
 * переставлены местами.
 */

import { render, within } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import RequisitesPage from '../page';

/** Блок организации по её порядковому номеру: 0 — владелец сайта, 1 — пользователь сайта. */
function organizationBlock(container: HTMLElement, orgIndex: 0 | 1): HTMLElement {
  const dl = container.querySelector(`dl[aria-labelledby="requisites-org-${orgIndex}"]`);
  if (!dl) throw new Error(`Блок организации ${orgIndex} не найден`);
  return dl as HTMLElement;
}

/** Значение реквизита по метке внутри конкретного блока. */
function requisiteValue(block: HTMLElement, label: string): string {
  const dt = within(block)
    .getAllByText(label, { selector: 'dt' })
    .at(0);
  if (!dt) throw new Error(`Метка «${label}» не найдена в блоке`);
  const dd = dt.parentElement?.querySelector('dd');
  if (!dd) throw new Error(`У метки «${label}» нет значения`);
  return dd.textContent ?? '';
}

/** Полный список меток блока в порядке отображения. */
function labels(block: HTMLElement): string[] {
  return Array.from(block.querySelectorAll('dt')).map((el) => el.textContent ?? '');
}

const REGISTRY_LABEL = 'Номер в реестре операторов ПДн';
const OWNER_REGISTRY_NUMBER = '26-22-004188';
const USER_REGISTRY_NUMBER = '26-22-003980';

describe('RequisitesPage', () => {
  it('отображает заголовок и две карточки организаций', () => {
    const { container } = render(<RequisitesPage />);

    expect(within(container).getByRole('heading', { level: 1, name: 'Реквизиты' })).toBeInTheDocument();

    const headings = within(container).getAllByRole('heading', { level: 2 });
    expect(headings).toHaveLength(2);
    expect(headings[0]).toHaveTextContent('Владелец сайта');
    expect(headings[0]).toHaveTextContent('Терещенко Людмила Викторовна');
    expect(headings[1]).toHaveTextContent('Пользователь сайта');
    expect(headings[1]).toHaveTextContent('Семерюк Дмитрий Владимирович');
  });

  it('блок «Владелец сайта»: ИНН, ОГРНИП и номер в реестре операторов ПДн', () => {
    const { container } = render(<RequisitesPage />);
    const block = organizationBlock(container, 0);

    expect(requisiteValue(block, 'ИНН')).toBe('263622926082');
    expect(requisiteValue(block, 'ОГРНИП')).toBe('321265100078260');
    expect(requisiteValue(block, REGISTRY_LABEL)).toBe(OWNER_REGISTRY_NUMBER);
  });

  it('блок «Пользователь сайта»: ИНН, ОГРНИП и номер в реестре операторов ПДн', () => {
    const { container } = render(<RequisitesPage />);
    const block = organizationBlock(container, 1);

    expect(requisiteValue(block, 'ИНН')).toBe('263511809023');
    expect(requisiteValue(block, 'ОГРНИП')).toBe('321265100084165');
    expect(requisiteValue(block, REGISTRY_LABEL)).toBe(USER_REGISTRY_NUMBER);
  });

  it('номера реестра не переставлены местами и не продублированы', () => {
    const { container } = render(<RequisitesPage />);
    const owner = organizationBlock(container, 0);
    const user = organizationBlock(container, 1);

    expect(within(owner).queryByText(USER_REGISTRY_NUMBER)).toBeNull();
    expect(within(user).queryByText(OWNER_REGISTRY_NUMBER)).toBeNull();

    expect(within(container).getAllByText(OWNER_REGISTRY_NUMBER)).toHaveLength(1);
    expect(within(container).getAllByText(USER_REGISTRY_NUMBER)).toHaveLength(1);
  });

  it('порядок реквизитов владельца сайта не изменён, номер реестра стоит после ОГРНИП', () => {
    const { container } = render(<RequisitesPage />);

    expect(labels(organizationBlock(container, 0))).toEqual([
      'Юридический адрес',
      'Телефон',
      'ИНН',
      'ОГРНИП',
      REGISTRY_LABEL,
      'Расчётный счёт',
      'Корреспондентский счёт',
      'БИК банка',
      'Банк',
      'Почта',
    ]);
  });

  it('порядок реквизитов пользователя сайта не изменён, номер реестра стоит после ОГРНИП', () => {
    const { container } = render(<RequisitesPage />);

    expect(labels(organizationBlock(container, 1))).toEqual([
      'Юридический адрес',
      'Почтовый адрес',
      'Телефон',
      'ИНН',
      'ОГРНИП',
      REGISTRY_LABEL,
      'Расчётный счёт',
      'Корреспондентский счёт',
      'БИК банка',
      'Банк',
      'Почта',
      'Номер GLN',
    ]);
  });
});
