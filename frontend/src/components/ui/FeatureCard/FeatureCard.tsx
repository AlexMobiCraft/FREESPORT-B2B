/**
 * FeatureCard - Вертикальная карточка с иконкой для информационных страниц
 * Story 19.1 - AC 1, 5, 7
 */

import React from 'react';
import { LucideIcon } from 'lucide-react';
import styles from './FeatureCard.module.css';

export interface FeatureCardProps {
  /** Иконка из lucide-react */
  icon: LucideIcon;
  /** Заголовок карточки */
  title: string;
  /** Опциональное описание */
  description?: string;
  /** Вариант отображения */
  variant?: 'default' | 'horizontal' | 'compact';
  /** Дополнительные CSS классы */
  className?: string;
}

export const FeatureCard: React.FC<FeatureCardProps> = ({
  icon: Icon,
  title,
  description,
  variant = 'default',
  className = '',
}) => {
  return (
    <div
      className={`${styles.featureCard} ${styles[variant]} ${className}`}
      role="article"
      aria-label={title}
    >
      <div className={styles.iconWrapper} aria-hidden="true">
        <Icon className={styles.icon} size={48} strokeWidth={1.5} />
      </div>

      <div className={styles.content}>
        <h3 className={styles.title}>{title}</h3>
        {description && <p className={styles.description}>{description}</p>}
      </div>
    </div>
  );
};
