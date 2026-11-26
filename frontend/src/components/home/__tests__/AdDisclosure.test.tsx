/**
 * Unit тесты для AdDisclosure
 *
 * Покрывают строки I/O-матрицы спеки:
 * - Рекламный баннер, наведение
 * - ERID не заполнен
 * - Копирование токена (успех и отказ Clipboard API)
 * - Клавиатура (focus открывает, Escape закрывает)
 *
 * @see _bmad-output/implementation-artifacts/spec-banner-ad-disclosure.md
 */

import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { render, screen, fireEvent, waitFor, act } from '@testing-library/react';
import { AdDisclosure } from '../AdDisclosure';

const REQUISITES = {
  advertiserName: 'ООО "Прайм Спорт Рус"',
  advertiserInn: '7718933790',
  erid: '2VfnxwTestToken',
};

/** Подменяет navigator.clipboard, возвращая функцию восстановления */
const stubClipboard = (writeText: unknown) => {
  const original = Object.getOwnPropertyDescriptor(navigator, 'clipboard');
  Object.defineProperty(navigator, 'clipboard', {
    value: writeText === undefined ? undefined : { writeText },
    configurable: true,
    writable: true,
  });
  return () => {
    if (original) {
      Object.defineProperty(navigator, 'clipboard', original);
    } else {
      delete (navigator as { clipboard?: unknown }).clipboard;
    }
  };
};

describe('AdDisclosure', () => {
  let restoreClipboard: (() => void) | null = null;

  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    restoreClipboard?.();
    restoreClipboard = null;
  });

  describe('метка и раскрытие', () => {
    it('рендерит метку «Реклама» и держит окно закрытым по умолчанию', () => {
      render(<AdDisclosure {...REQUISITES} />);

      expect(screen.getByTestId('ad-disclosure-trigger')).toHaveTextContent('Реклама');
      expect(screen.queryByTestId('ad-disclosure-panel')).not.toBeInTheDocument();
    });

    // Направление чтения — требование к маркировке, а не оформление: без этой проверки
    // разворот молча переживёт любой рефакторинг разметки кнопки (jsdom не считает
    // Tailwind-стили, поэтому фиксируем сам класс)
    it('разворачивает надпись на 180° — метка читается снизу вверх', () => {
      render(<AdDisclosure {...REQUISITES} />);

      const label = screen.getByTestId('ad-disclosure-label');
      expect(label).toHaveClass('rotate-180');
      expect(screen.getByTestId('ad-disclosure-trigger')).toContainElement(label);
    });

    it('показывает реквизиты при наведении мышью', () => {
      render(<AdDisclosure {...REQUISITES} />);

      fireEvent.pointerEnter(screen.getByTestId('ad-disclosure'), { pointerType: 'mouse' });

      const panel = screen.getByTestId('ad-disclosure-panel');
      expect(panel).toHaveTextContent('Реклама');
      expect(panel).toHaveTextContent('ИНН 7718933790, ООО "Прайм Спорт Рус"');
    });

    it('скрывает окно при уходе курсора мыши', () => {
      render(<AdDisclosure {...REQUISITES} />);
      const container = screen.getByTestId('ad-disclosure');

      fireEvent.pointerEnter(container, { pointerType: 'mouse' });
      expect(screen.getByTestId('ad-disclosure-panel')).toBeInTheDocument();

      fireEvent.pointerLeave(container, { pointerType: 'mouse' });
      expect(screen.queryByTestId('ad-disclosure-panel')).not.toBeInTheDocument();
    });

    it('переключает окно кликом — путь для тач-устройств', () => {
      render(<AdDisclosure {...REQUISITES} />);
      const trigger = screen.getByTestId('ad-disclosure-trigger');

      fireEvent.click(trigger);
      expect(screen.getByTestId('ad-disclosure-panel')).toBeInTheDocument();

      fireEvent.click(trigger);
      expect(screen.queryByTestId('ad-disclosure-panel')).not.toBeInTheDocument();
    });

    it('закрывает окно при клике вне блока', () => {
      render(<AdDisclosure {...REQUISITES} />);

      fireEvent.click(screen.getByTestId('ad-disclosure-trigger'));
      expect(screen.getByTestId('ad-disclosure-panel')).toBeInTheDocument();

      fireEvent.mouseDown(document.body);
      expect(screen.queryByTestId('ad-disclosure-panel')).not.toBeInTheDocument();
    });

    it('проставляет aria-expanded на триггере', () => {
      render(<AdDisclosure {...REQUISITES} />);
      const trigger = screen.getByTestId('ad-disclosure-trigger');

      expect(trigger).toHaveAttribute('aria-expanded', 'false');
      fireEvent.click(trigger);
      expect(trigger).toHaveAttribute('aria-expanded', 'true');
    });
  });

  describe('клавиатура', () => {
    it('открывает окно по фокусу и закрывает по Escape', () => {
      render(<AdDisclosure {...REQUISITES} />);
      const container = screen.getByTestId('ad-disclosure');
      const trigger = screen.getByTestId('ad-disclosure-trigger');

      // Нужны оба вызова: .focus() двигает document.activeElement (без этого проверка
      // возврата фокуса бессмысленна), fireEvent.focus дёргает React-обработчик
      trigger.focus();
      fireEvent.focus(trigger);
      expect(screen.getByTestId('ad-disclosure-panel')).toBeInTheDocument();

      fireEvent.keyDown(container, { key: 'Escape' });
      expect(screen.queryByTestId('ad-disclosure-panel')).not.toBeInTheDocument();
      // Без возврата фокуса он улетает на body и навигация начинается с начала страницы
      expect(trigger).toHaveFocus();
    });

    it('не закрывает окно, когда фокус уходит на кнопку копирования внутри блока', () => {
      render(<AdDisclosure {...REQUISITES} />);
      const trigger = screen.getByTestId('ad-disclosure-trigger');

      fireEvent.focus(trigger);
      const copyButton = screen.getByTestId('ad-disclosure-copy');

      fireEvent.blur(trigger, { relatedTarget: copyButton });
      expect(screen.getByTestId('ad-disclosure-panel')).toBeInTheDocument();
    });

    it('закрывает окно, когда фокус уходит наружу', () => {
      render(
        <>
          <AdDisclosure {...REQUISITES} />
          <button type="button" data-testid="outside">
            вне
          </button>
        </>
      );
      const trigger = screen.getByTestId('ad-disclosure-trigger');

      fireEvent.focus(trigger);
      fireEvent.blur(trigger, { relatedTarget: screen.getByTestId('outside') });

      expect(screen.queryByTestId('ad-disclosure-panel')).not.toBeInTheDocument();
    });
  });

  describe('ERID', () => {
    it('не показывает кнопку копирования, когда токен не заполнен', () => {
      render(<AdDisclosure {...REQUISITES} erid="" />);

      fireEvent.click(screen.getByTestId('ad-disclosure-trigger'));

      expect(screen.getByTestId('ad-disclosure-panel')).toHaveTextContent('ИНН 7718933790');
      expect(screen.queryByTestId('ad-disclosure-copy')).not.toBeInTheDocument();
    });

    it('копирует токен в буфер и подтверждает результат', async () => {
      const writeText = vi.fn().mockResolvedValue(undefined);
      restoreClipboard = stubClipboard(writeText);

      render(<AdDisclosure {...REQUISITES} />);
      fireEvent.click(screen.getByTestId('ad-disclosure-trigger'));

      await act(async () => {
        fireEvent.click(screen.getByTestId('ad-disclosure-copy'));
      });

      expect(writeText).toHaveBeenCalledWith('2VfnxwTestToken');
      await waitFor(() =>
        expect(screen.getByTestId('ad-disclosure-copy')).toHaveTextContent('Скопировано')
      );
    });

    it('сообщает об ошибке, когда Clipboard API отклоняет запрос', async () => {
      const writeText = vi.fn().mockRejectedValue(new Error('denied'));
      restoreClipboard = stubClipboard(writeText);

      render(<AdDisclosure {...REQUISITES} />);
      fireEvent.click(screen.getByTestId('ad-disclosure-trigger'));

      await act(async () => {
        fireEvent.click(screen.getByTestId('ad-disclosure-copy'));
      });

      await waitFor(() =>
        expect(screen.getByTestId('ad-disclosure-copy')).toHaveTextContent(
          'Не удалось скопировать'
        )
      );
      // Окно остаётся открытым — токен всё ещё можно выделить вручную
      expect(screen.getByTestId('ad-disclosure-panel')).toBeInTheDocument();
    });

    it('сообщает об ошибке, когда Clipboard API недоступен', async () => {
      restoreClipboard = stubClipboard(undefined);

      render(<AdDisclosure {...REQUISITES} />);
      fireEvent.click(screen.getByTestId('ad-disclosure-trigger'));

      await act(async () => {
        fireEvent.click(screen.getByTestId('ad-disclosure-copy'));
      });

      await waitFor(() =>
        expect(screen.getByTestId('ad-disclosure-copy')).toHaveTextContent(
          'Не удалось скопировать'
        )
      );
    });
  });

  describe('тач-устройства', () => {
    it('раскрывает окно с первого тапа, несмотря на синтезированный pointerenter', () => {
      render(<AdDisclosure {...REQUISITES} />);
      const container = screen.getByTestId('ad-disclosure');
      const trigger = screen.getByTestId('ad-disclosure-trigger');

      // Браузер шлёт pointerenter(touch) перед click — раньше это открывало окно,
      // а следующий click тут же его закрывал
      fireEvent.pointerEnter(container, { pointerType: 'touch' });
      expect(screen.queryByTestId('ad-disclosure-panel')).not.toBeInTheDocument();

      fireEvent.click(trigger);
      expect(screen.getByTestId('ad-disclosure-panel')).toBeInTheDocument();
    });

    it('не закрывает окно по pointerleave тачем', () => {
      render(<AdDisclosure {...REQUISITES} />);
      const container = screen.getByTestId('ad-disclosure');

      fireEvent.click(screen.getByTestId('ad-disclosure-trigger'));
      fireEvent.pointerLeave(container, { pointerType: 'touch' });

      expect(screen.getByTestId('ad-disclosure-panel')).toBeInTheDocument();
    });
  });

  describe('порядок DOM и доступность', () => {
    it('размещает панель после триггера, чтобы кнопка копирования была достижима Tab', () => {
      render(<AdDisclosure {...REQUISITES} />);
      fireEvent.click(screen.getByTestId('ad-disclosure-trigger'));

      const trigger = screen.getByTestId('ad-disclosure-trigger');
      const panel = screen.getByTestId('ad-disclosure-panel');

      // Node.DOCUMENT_POSITION_FOLLOWING === 4
      expect(trigger.compareDocumentPosition(panel) & 4).toBeTruthy();
    });

    it('связывает реквизиты с триггером через aria-describedby', () => {
      render(<AdDisclosure {...REQUISITES} />);
      fireEvent.click(screen.getByTestId('ad-disclosure-trigger'));

      const trigger = screen.getByTestId('ad-disclosure-trigger');
      const panel = screen.getByTestId('ad-disclosure-panel');

      expect(trigger).toHaveAttribute('aria-describedby', panel.id);
    });

    it('не рендерит ничего при пустых реквизитах вместо «ИНН , »', () => {
      render(<AdDisclosure advertiserName="" advertiserInn="" erid="" />);

      expect(screen.queryByTestId('ad-disclosure')).not.toBeInTheDocument();
    });
  });

  describe('onOpenChange', () => {
    it('сообщает об открытии и закрытии окна', () => {
      const onOpenChange = vi.fn();
      render(<AdDisclosure {...REQUISITES} onOpenChange={onOpenChange} />);
      const trigger = screen.getByTestId('ad-disclosure-trigger');

      onOpenChange.mockClear();
      fireEvent.click(trigger);
      expect(onOpenChange).toHaveBeenCalledWith(true);

      fireEvent.click(trigger);
      expect(onOpenChange).toHaveBeenLastCalledWith(false);
    });
  });
});
