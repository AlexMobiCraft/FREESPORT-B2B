/**
 * AdDisclosure Component
 *
 * Маркировка рекламы на баннере по ФЗ «О рекламе»: вертикальная метка «РЕКЛАМА»
 * у края баннера, раскрывающая реквизиты рекламодателя и токен ERID.
 *
 * Раскрытие обязано работать не только по наведению, поэтому здесь три отдельных
 * механизма, каждый со своей ловушкой:
 *
 * - Мышь: pointerenter/pointerleave с проверкой pointerType. Без проверки тап на
 *   мобильном сначала получает синтезированный mouseenter (окно открывается), а следом
 *   click (окно закрывается) — первый тап визуально не делает ничего.
 * - Клавиатура: focus открывает, Escape закрывает и возвращает фокус на триггер.
 *   Панель отрисована ПОСЛЕ кнопки в DOM и спозиционирована влево через right-full:
 *   в обратном порядке кнопка копирования оказывается позади триггера в таб-порядке
 *   и прямым Tab до неё не добраться.
 * - Скринридер: реквизиты связаны с триггером через aria-describedby, иначе aria-label
 *   кнопки перекрывает содержимое и текст ИНН не зачитывается вовсе.
 *
 * @see _bmad-output/implementation-artifacts/spec-banner-ad-disclosure.md
 */

'use client';

import React, { useCallback, useEffect, useId, useRef, useState } from 'react';
import { cn } from '@/utils/cn';

export interface AdDisclosureProps {
  /** Наименование рекламодателя, например: ООО "Прайм Спорт Рус" */
  advertiserName: string;
  /** ИНН рекламодателя: 10 цифр (юрлицо) или 12 (ИП, физлицо) */
  advertiserInn: string;
  /** Токен ERID из ОРД. Пустая строка — кнопка копирования не показывается */
  erid?: string;
  /** Уведомление об открытии/закрытии окна — карусель ставит автопрокрутку на паузу */
  onOpenChange?: (isOpen: boolean) => void;
  /**
   * Убрать метку из таб-порядка и a11y-дерева.
   *
   * Embla держит все слайды карусели в DOM, поэтому без этого кнопки «Реклама»
   * невидимых баннеров остаются фокусируемыми и открывают окна за пределами вьюпорта.
   */
  inert?: boolean;
  /** Классы позиционирования обёртки относительно баннера */
  className?: string;
}

type CopyState = 'idle' | 'copied' | 'error';

/** Сколько держать подтверждение копирования перед возвратом к исходной надписи */
const COPY_FEEDBACK_DURATION = 2000;

const COPY_LABELS: Record<CopyState, string> = {
  idle: 'скопировать токен',
  copied: 'Скопировано',
  error: 'Не удалось скопировать',
};

export function AdDisclosure({
  advertiserName,
  advertiserInn,
  erid = '',
  onOpenChange,
  inert = false,
  className,
}: AdDisclosureProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [copyState, setCopyState] = useState<CopyState>('idle');
  const containerRef = useRef<HTMLDivElement | null>(null);
  const triggerRef = useRef<HTMLButtonElement | null>(null);
  const copyTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const panelId = useId();

  // Реквизиты неполны только при рассинхроне с бэкендом (bulk_update в обход full_clean).
  // Показывать «ИНН , » хуже, чем не показывать метку вовсе.
  const hasRequisites = Boolean(advertiserInn || advertiserName);

  const close = useCallback(() => {
    setIsOpen(false);
    setCopyState('idle');
  }, []);

  // Возврат фокуса обязателен: закрытие размонтирует кнопку копирования, и если фокус
  // был на ней, он улетает на body — клавиатурная навигация начинается с начала страницы
  const closeAndRestoreFocus = useCallback(() => {
    const focusWasInside = containerRef.current?.contains(document.activeElement);
    close();
    if (focusWasInside) triggerRef.current?.focus();
  }, [close]);

  useEffect(() => {
    onOpenChange?.(isOpen);
  }, [isOpen, onOpenChange]);

  useEffect(() => {
    if (!isOpen) return;

    const handlePointerDown = (event: MouseEvent | TouchEvent) => {
      const target = event.target as Node | null;
      if (target && containerRef.current && !containerRef.current.contains(target)) {
        close();
      }
    };

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') closeAndRestoreFocus();
    };

    document.addEventListener('mousedown', handlePointerDown);
    document.addEventListener('touchstart', handlePointerDown);
    document.addEventListener('keydown', handleKeyDown);

    return () => {
      document.removeEventListener('mousedown', handlePointerDown);
      document.removeEventListener('touchstart', handlePointerDown);
      document.removeEventListener('keydown', handleKeyDown);
    };
  }, [isOpen, close, closeAndRestoreFocus]);

  useEffect(
    () => () => {
      if (copyTimeoutRef.current) clearTimeout(copyTimeoutRef.current);
    },
    []
  );

  const scheduleCopyReset = useCallback(() => {
    if (copyTimeoutRef.current) clearTimeout(copyTimeoutRef.current);
    copyTimeoutRef.current = setTimeout(() => setCopyState('idle'), COPY_FEEDBACK_DURATION);
  }, []);

  const handleCopy = useCallback(async () => {
    try {
      if (!navigator.clipboard?.writeText) {
        throw new Error('Clipboard API недоступен');
      }
      await navigator.clipboard.writeText(erid);
      setCopyState('copied');
    } catch {
      // Отказ Clipboard API (небезопасный контекст, запрет разрешения) — не роняем окно,
      // пользователь всё ещё видит токен и может выделить его вручную
      setCopyState('error');
    }
    scheduleCopyReset();
  }, [erid, scheduleCopyReset]);

  // Наведение открывает окно только настоящей мышью: на тач-экране браузер синтезирует
  // pointerenter перед click, и без этой проверки тап открывал бы и тут же закрывал окно
  const handlePointerEnter = useCallback((event: React.PointerEvent<HTMLDivElement>) => {
    if (event.pointerType === 'mouse') setIsOpen(true);
  }, []);

  const handlePointerLeave = useCallback(
    (event: React.PointerEvent<HTMLDivElement>) => {
      if (event.pointerType === 'mouse') close();
    },
    [close]
  );

  // Уход фокуса внутрь блока (например, на кнопку копирования) окно не закрывает
  const handleBlur = useCallback(
    (event: React.FocusEvent<HTMLDivElement>) => {
      const nextTarget = event.relatedTarget as Node | null;
      if (nextTarget && containerRef.current?.contains(nextTarget)) return;
      close();
    },
    [close]
  );

  if (!hasRequisites) return null;

  const requisitesText = [advertiserInn && `ИНН ${advertiserInn}`, advertiserName]
    .filter(Boolean)
    .join(', ');

  return (
    <div
      ref={containerRef}
      /* role="group" здесь не косметика: обработчики на элементе без роли ловит
         jsx-a11y/no-static-element-interactions, а lint запущен с --max-warnings=0 */
      role="group"
      aria-label="Маркировка рекламы"
      inert={inert}
      className={cn('flex items-center', className)}
      onPointerEnter={handlePointerEnter}
      onPointerLeave={handlePointerLeave}
      onFocus={() => setIsOpen(true)}
      onBlur={handleBlur}
      data-testid="ad-disclosure"
    >
      {/* Метка лежит поверх произвольной картинки рекламодателя, поэтому у неё
          собственная подложка — иначе различимость зависит от того, что загрузил менеджер,
          а закон требует пометку «чётко и хорошо различимо». min-h/min-w держат
          тап-таргет не меньше 24×24 CSS-px (WCAG 2.5.8). */}
      <button
        ref={triggerRef}
        type="button"
        onClick={() => (isOpen ? close() : setIsOpen(true))}
        aria-expanded={isOpen}
        aria-controls={isOpen ? panelId : undefined}
        aria-describedby={isOpen ? panelId : undefined}
        aria-label="Реклама. Реквизиты рекламодателя"
        className={cn(
          'flex min-h-[44px] min-w-[24px] items-center justify-center',
          'rounded-l-md bg-white/85 px-1 py-2 backdrop-blur-sm',
          'select-none text-[10px] uppercase tracking-widest text-gray-700',
          'shadow-sm transition-colors hover:bg-white hover:text-gray-900',
          'focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2',
          'focus-visible:outline-cyan-600'
        )}
        style={{ writingMode: 'vertical-rl' }}
        data-testid="ad-disclosure-trigger"
      >
        {/* Разворот на span, а не на кнопке: rotate на триггере утащил бы за собой
            и скругление rounded-l-md, которым метка прижата к краю баннера */}
        <span className="rotate-180" data-testid="ad-disclosure-label">
          Реклама
        </span>
      </button>

      {/* Панель идёт после кнопки в DOM (иначе кнопка копирования недостижима прямым Tab)
          и раскрывается влево через right-full, чтобы не выйти за край карусели */}
      {isOpen && (
        <div
          id={panelId}
          className={cn(
            'absolute right-full top-1/2 mr-1 -translate-y-1/2',
            'max-h-[80%] w-max max-w-[min(20rem,60vw)] overflow-y-auto overscroll-contain',
            // Подложка полупрозрачная, но с backdrop-blur: реквизиты лежат поверх
            // произвольной картинки рекламодателя, и без размытия фона контраст текста
            // зависел бы от того, что загрузил менеджер, — закон требует «чётко и
            // хорошо различимо»
            'rounded-lg bg-gray-900/60 px-3 py-2 text-left shadow-lg backdrop-blur-sm',
            'text-xs leading-snug text-white'
          )}
          data-testid="ad-disclosure-panel"
        >
          <p className="font-semibold">Реклама</p>
          <p className="mt-0.5 text-gray-200">{requisitesText}</p>
          {erid && (
            <>
              <button
                type="button"
                onClick={handleCopy}
                className={cn(
                  'mt-1 rounded underline underline-offset-2 transition-colors',
                  'focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2',
                  'focus-visible:outline-white',
                  copyState === 'error'
                    ? 'text-amber-300 hover:text-amber-200'
                    : 'text-red-400 hover:text-red-300'
                )}
                data-testid="ad-disclosure-copy"
              >
                {COPY_LABELS[copyState]}
              </button>
              {/* Результат копирования нужно объявить отдельно: смена надписи на кнопке,
                  которая уже озвучена, скринридером сама по себе не анонсируется */}
              <span aria-live="polite" className="sr-only">
                {copyState === 'copied' ? 'Токен скопирован' : ''}
                {copyState === 'error' ? 'Не удалось скопировать токен' : ''}
              </span>
              {/* Токен доступен для ручного выделения даже при отказе Clipboard API */}
              <p className="mt-0.5 break-all text-[10px] text-gray-400">erid: {erid}</p>
            </>
          )}
        </div>
      )}
    </div>
  );
}

AdDisclosure.displayName = 'AdDisclosure';

export default AdDisclosure;
