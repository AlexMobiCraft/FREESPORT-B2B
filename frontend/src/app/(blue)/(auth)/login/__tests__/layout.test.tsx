/**
 * Метаданные страницы входа (стори 41.6, AC2).
 *
 * Метаданные живут в layout, а не в `page.tsx`: сама страница входа —
 * клиентский компонент ('use client', нужны useSearchParams/useRouter/Zustand),
 * а Next собирает `metadata` только из серверных модулей. Тот же приём уже
 * применён в `(blue)/catalog/layout.tsx`.
 *
 * Отдельно закреплено, что layout не добавляет разметки: возврат `children`
 * без обёртки — условие, на которое рассчитывает `LayoutWrapper` темы blue.
 */

import { describe, it, expect, vi } from 'vitest';
import { render } from '@testing-library/react';

import LoginLayout, { metadata } from '../layout';
import { metadata as rootMetadata } from '@/app/layout';

// Корневой layout импортируется ради сверки с его title/description; шрифты
// next/font в тестовой среде не резолвятся, поэтому заменяются заглушкой.
vi.mock('next/font/google', () => ({
  Inter: () => ({ variable: '--font-inter' }),
  Roboto_Condensed: () => ({ variable: '--font-roboto-condensed' }),
}));

describe('Метаданные /login', () => {
  it('задаёт собственный title', () => {
    expect(metadata.title).toBe('Вход в личный кабинет | OPTISPORT');
  });

  it('задаёт собственный description', () => {
    expect(metadata.description).toBe(
      'Вход в личный кабинет OPTISPORT для оптовых клиентов: заказы, цены по вашей роли, история отгрузок и документы.'
    );
  });

  it('отличается от значений корневого layout', () => {
    expect(metadata.title).not.toBe(rootMetadata.title);
    expect(metadata.description).not.toBe(rootMetadata.description);
  });

  it('собран через buildMetadata: есть canonical и openGraph', () => {
    expect(metadata.alternates?.canonical).toBe('/login');
    expect(metadata.openGraph?.title).toBe(metadata.title);
    expect(metadata.openGraph?.url).toBe('/login');
  });

  it('закрывает страницу от индексации — как /cart и /checkout', () => {
    expect(metadata.robots).toEqual({ index: false, follow: false });
  });
});

describe('LoginLayout', () => {
  it('рендерит children без собственной обёртки', () => {
    const { container } = render(<LoginLayout>{<span data-testid="child" />}</LoginLayout>);

    expect(container.firstElementChild?.tagName).toBe('SPAN');
    expect(container.childElementCount).toBe(1);
  });
});
