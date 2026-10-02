/**
 * Метаданные страницы регистрации (стори 41.19, AC3).
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

import RegisterLayout, { metadata } from '../layout';
import { metadata as b2bRegisterMetadata } from '../../b2b-register/layout';
import { metadata as rootMetadata } from '@/app/layout';

// Корневой layout импортируется ради сверки с его title/description; шрифты
// next/font в тестовой среде не резолвятся, поэтому заменяются заглушкой.
vi.mock('next/font/google', () => ({
  Inter: () => ({ variable: '--font-inter' }),
  Roboto_Condensed: () => ({ variable: '--font-roboto-condensed' }),
}));

describe('Метаданные /register', () => {
  it('задаёт утверждённый title', () => {
    expect(metadata.title).toBe('Регистрация | OPTISPORT');
  });

  it('задаёт утверждённый description', () => {
    expect(metadata.description).toBe(
      'Заявка на аккаунт OPTISPORT для оптовых покупателей, тренеров, спортивных клубов и федераций. Доступ к ценам откроется после проверки заявки.'
    );
  });

  it('отличается от корневого layout и от /b2b-register', () => {
    expect(metadata.title).not.toBe(rootMetadata.title);
    expect(metadata.description).not.toBe(rootMetadata.description);
    expect(metadata.title).not.toBe(b2bRegisterMetadata.title);
    expect(metadata.description).not.toBe(b2bRegisterMetadata.description);
  });

  it('собран через buildMetadata: есть canonical и openGraph', () => {
    expect(metadata.alternates?.canonical).toBe('/register');
    expect(metadata.openGraph?.title).toBe(metadata.title);
    expect(metadata.openGraph?.url).toBe('/register');
  });

  it('не несёт meta robots — адрес закрыт Disallow (D4)', () => {
    expect(metadata.robots).toBeUndefined();
  });

  it('не задаёт keywords', () => {
    expect(metadata.keywords).toBeUndefined();
  });
});

describe('RegisterLayout', () => {
  it('рендерит children без собственной обёртки', () => {
    const { container } = render(<RegisterLayout>{<span data-testid="child" />}</RegisterLayout>);

    expect(container.firstElementChild?.tagName).toBe('SPAN');
    expect(container.childElementCount).toBe(1);
  });
});
