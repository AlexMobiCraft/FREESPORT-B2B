/**
 * Accordion - FAQ секция с ARIA
 * Story 19.1 - AC 4, 5, 7
 */

'use client';

import React, { useState, useCallback } from 'react';
import { AccordionItem } from './AccordionItem';
import styles from './Accordion.module.css';

export interface AccordionItemData {
  /** Вопрос (заголовок) */
  question: string;
  /** Ответ (содержимое) */
  answer: string;
  /** Опциональный ID для ARIA */
  id?: string;
}

export interface AccordionProps {
  /** Массив элементов аккордеона */
  items: AccordionItemData[];
  /** Разрешить открывать несколько элементов одновременно */
  allowMultiple?: boolean;
  /** Индекс элемента, открытого по умолчанию */
  defaultOpenIndex?: number;
  /** Дополнительные CSS классы */
  className?: string;
}

export const Accordion: React.FC<AccordionProps> = ({
  items,
  allowMultiple = false,
  defaultOpenIndex,
  className = '',
}) => {
  // Состояние открытых элементов
  const [openIndexes, setOpenIndexes] = useState<Set<number>>(() => {
    const initial = new Set<number>();
    if (
      defaultOpenIndex !== undefined &&
      defaultOpenIndex >= 0 &&
      defaultOpenIndex < items.length
    ) {
      initial.add(defaultOpenIndex);
    }
    return initial;
  });

  const handleToggle = useCallback(
    (index: number) => {
      setOpenIndexes(prev => {
        const newSet = new Set(prev);

        if (newSet.has(index)) {
          // Закрываем элемент
          newSet.delete(index);
        } else {
          // Открываем элемент
          if (!allowMultiple) {
            // Если не разрешено открывать несколько, закрываем все остальные
            newSet.clear();
          }
          newSet.add(index);
        }

        return newSet;
      });
    },
    [allowMultiple]
  );

  const handleKeyNavigation = useCallback(
    (event: React.KeyboardEvent, currentIndex: number) => {
      if (event.key === 'ArrowDown') {
        event.preventDefault();
        const nextIndex = currentIndex < items.length - 1 ? currentIndex + 1 : 0;
        const nextButton = document.getElementById(`accordion-item-${nextIndex}-button`);
        nextButton?.focus();
      } else if (event.key === 'ArrowUp') {
        event.preventDefault();
        const prevIndex = currentIndex > 0 ? currentIndex - 1 : items.length - 1;
        const prevButton = document.getElementById(`accordion-item-${prevIndex}-button`);
        prevButton?.focus();
      }
    },
    [items.length]
  );

  return (
    <div
      className={`${styles.accordion} ${className}`}
      role="region"
      aria-label="Часто задаваемые вопросы"
      onKeyDown={e => {
        const target = e.target as HTMLElement;
        const buttonId = target.id;
        if (buttonId && buttonId.includes('accordion-item-')) {
          const index = parseInt(buttonId.split('-')[2], 10);
          handleKeyNavigation(e, index);
        }
      }}
    >
      {items.map((item, index) => (
        <AccordionItem
          key={item.id || `accordion-item-${index}`}
          id={item.id || `accordion-item-${index}`}
          question={item.question}
          answer={item.answer}
          isOpen={openIndexes.has(index)}
          onToggle={() => handleToggle(index)}
        />
      ))}
    </div>
  );
};
