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
    variant: 'new' | 'hit' | 'sale';
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
        label: 'Новинки',
        icon: <Sparkles className="w-5 h-5" />,
        link: '/catalog?is_new=true',
        variant: 'new',
        color: 'bg-blue-500',
    },
    {
        label: 'Хиты продаж',
        icon: <Flame className="w-5 h-5" />,
        link: '/catalog?is_hit=true',
        variant: 'hit',
        color: 'bg-orange-500',
    },
    {
        label: 'Скидки',
        icon: <Percent className="w-5 h-5" />,
        link: '/catalog?is_sale=true',
        variant: 'sale',
        color: 'bg-emerald-500',
    },
];
