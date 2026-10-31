/**
 * Quick Links Configuration
 *
 * Статические ссылки для секции быстрого доступа на главной странице.
 * Отображаются перед динамическими категориями.
 */

import React from 'react';
import { Sparkles, Flame, Percent } from 'lucide-react';

export interface QuickLink {
  label: string;
  link: string;
  variant: 'new' | 'hit' | 'promo';
  icon: React.ReactNode;
  /** Tailwind цвет фона кружка иконки */
  color: string;
}

export interface CategoryLink {
  id: number;
  label: string;
  link: string;
  slug: string;
}

export const STATIC_QUICK_LINKS: QuickLink[] = [
  {
    label: 'Акция',
    icon: <Percent className="w-5 h-5" />,
    link: '/catalog?is_promo=true',
    variant: 'promo',
    color: 'bg-emerald-500',
  },
  {
    label: 'Новинки',
    icon: <Sparkles className="w-5 h-5" />,
    link: '/catalog?is_new=true',
    variant: 'new',
    color: 'bg-blue-500',
  },
  {
    label: 'Лидеры продаж',
    icon: <Flame className="w-5 h-5" />,
    link: '/catalog?is_hit=true',
    variant: 'hit',
    color: 'bg-orange-500',
  },
];
