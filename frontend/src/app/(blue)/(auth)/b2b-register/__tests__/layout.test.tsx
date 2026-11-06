/**
 * Метаданные страницы регистрации компании (стори 41.19, AC3).
 *
 * Метаданные живут в layout, а не в `page.tsx`: страница — клиентский
 * компонент ('use client'), а Next собирает `metadata` только из серверных
 * модулей. Приём тот же, что у `/login` (стори 41.6).
 *
 * robots не ставится: адрес закрыт `Disallow` в robots.txt, а такие адреса
 * meta `noindex` не несут (решение D4, стори 41.18).
 */

import { describe, it, expect, vi } from 'vitest';
import { render } from '@testing-library/react';

import B2BRegisterLayout, { metadata } from '../layout';
import { metadata as registerMetadata } from '../../register/layout';
import { metadata as rootMetadata } from '@/app/layout';

// Корневой layout импортируется ради сверки с его title/description; шрифты
// next/font в тестовой среде не резолвятся, поэтому заменяются заглушкой.
vi.mock('next/font/google', () => ({
  Inter: () => ({ variable: '--font-inter' }),
  Roboto_Condensed: () => ({ variable: '--font-roboto-condensed' }),
}));

describe('Метаданные /b2b-register', () => {
  it('задаёт утверждённый title', () => {
    expect(metadata.title).toBe('Регистрация компании | OPTISPORT');
  });

  it('задаёт утверждённый description', () => {
    expect(metadata.description).toBe(
      'Заявка на оптовый аккаунт OPTISPORT для организаций и ИП: контактное лицо и реквизиты компании. Оптовые цены откроются после проверки заявки.'
    );
  });

  it('отличается от корневого layout и от /register', () => {
    expect(metadata.title).not.toBe(rootMetadata.title);
    expect(metadata.description).not.toBe(rootMetadata.description);
    expect(metadata.title).not.toBe(registerMetadata.title);
    expect(metadata.description).not.toBe(registerMetadata.description);
  });

  it('собран через buildMetadata: есть canonical и openGraph', () => {
    expect(metadata.alternates?.canonical).toBe('/b2b-register');
    expect(metadata.openGraph?.title).toBe(metadata.title);
    expect(metadata.openGraph?.url).toBe('/b2b-register');
  });

  it('не несёт meta robots — адрес закрыт Disallow (D4)', () => {
    expect(metadata.robots).toBeUndefined();
  });

  it('не задаёт keywords', () => {
    expect(metadata.keywords).toBeUndefined();
  });
});

describe('B2BRegisterLayout', () => {
  it('рендерит children без собственной обёртки', () => {
    const { container } = render(
      <B2BRegisterLayout>{<span data-testid="child" />}</B2BRegisterLayout>
    );

    expect(container.firstElementChild?.tagName).toBe('SPAN');
    expect(container.childElementCount).toBe(1);
  });
});
