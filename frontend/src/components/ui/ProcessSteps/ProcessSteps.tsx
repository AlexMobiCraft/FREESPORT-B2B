/**
 * ProcessSteps - Шаги процесса «Как начать сотрудничество»
 * Story 19.1 - AC 3, 5, 7
 */

import React from 'react';
import styles from './ProcessSteps.module.css';

export interface ProcessStep {
  /** Номер шага (1, 2, 3...) */
  number: number;
  /** Заголовок шага */
  title: string;
  /** Описание шага */
  description: string;
}

export interface ProcessStepsProps {
  /** Массив шагов процесса */
  steps: ProcessStep[];
  /** Вариант отображения */
  variant?: 'numbered' | 'timeline';
  /** Дополнительные CSS классы */
  className?: string;
}

export const ProcessSteps: React.FC<ProcessStepsProps> = ({
  steps,
  variant = 'numbered',
  className = '',
}) => {
  return (
    <div
      className={`${styles.processSteps} ${styles[variant]} ${className}`}
      role="list"
      aria-label="Шаги процесса"
    >
      {steps.map((step, index) => (
        <React.Fragment key={step.number}>
          <div className={styles.step} role="listitem">
            <div className={styles.numberWrapper} aria-hidden="true">
              <span className={styles.number}>{step.number}</span>
            </div>

            <div className={styles.content}>
              <h3 className={styles.title}>{step.title}</h3>
              <p className={styles.description}>{step.description}</p>
            </div>
          </div>

          {/* Разделитель между шагами (не показываем после последнего) */}
          {index < steps.length - 1 && (
            <div className={styles.separator} aria-hidden="true">
              {variant === 'numbered' ? (
                <svg
                  className={styles.arrow}
                  width="24"
                  height="24"
                  viewBox="0 0 24 24"
                  fill="none"
                  xmlns="http://www.w3.org/2000/svg"
                >
                  <path
                    d="M5 12H19M19 12L12 5M19 12L12 19"
                    stroke="currentColor"
                    strokeWidth="2"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  />
                </svg>
              ) : (
                <div className={styles.line} />
              )}
            </div>
          )}
        </React.Fragment>
      ))}
    </div>
  );
};
