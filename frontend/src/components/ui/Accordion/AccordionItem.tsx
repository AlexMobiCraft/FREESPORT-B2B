/**
 * AccordionItem - Вложенный компонент для каждого элемента аккордеона
 * Story 19.1 - AC 4, 7
 */

'use client';

import React, { useRef, useEffect } from 'react';
import { ChevronDown } from 'lucide-react';
import styles from './Accordion.module.css';

export interface AccordionItemProps {
  /** Вопрос (заголовок) */
  question: string;
  /** Ответ (содержимое) */
  answer: string;
  /** ID элемента для ARIA */
  id: string;
  /** Открыт ли элемент */
  isOpen: boolean;
  /** Обработчик клика */
  onToggle: () => void;
}

export const AccordionItem: React.FC<AccordionItemProps> = ({
  question,
  answer,
  id,
  isOpen,
  onToggle,
}) => {
  const contentRef = useRef<HTMLDivElement>(null);
  const contentId = `${id}-content`;
  const buttonId = `${id}-button`;

  useEffect(() => {
    if (contentRef.current) {
      if (isOpen) {
        contentRef.current.style.maxHeight = `${contentRef.current.scrollHeight}px`;
      } else {
        contentRef.current.style.maxHeight = '0px';
      }
    }
  }, [isOpen]);

  const handleKeyDown = (event: React.KeyboardEvent) => {
    if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault();
      onToggle();
    }
  };

  return (
    <div className={styles.accordionItem}>
      <button
        id={buttonId}
        className={styles.trigger}
        onClick={onToggle}
        onKeyDown={handleKeyDown}
        aria-expanded={isOpen}
        aria-controls={contentId}
        type="button"
      >
        <span className={styles.question}>{question}</span>
        <ChevronDown
          className={`${styles.icon} ${isOpen ? styles.iconOpen : ''}`}
          size={20}
          aria-hidden="true"
        />
      </button>

      <div
        id={contentId}
        ref={contentRef}
        className={`${styles.content} ${isOpen ? styles.contentOpen : ''}`}
        aria-labelledby={buttonId}
        role="region"
      >
        <div className={styles.contentInner}>
          <p className={styles.answer}>{answer}</p>
        </div>
      </div>
    </div>
  );
};
