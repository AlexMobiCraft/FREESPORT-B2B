'use client';

/**
 * Design Comparison Page
 * Страница для визуального сравнения текущей и новой цветовой схемы
 */

import React, { useState } from 'react';
import { Check, ShoppingCart, Heart, Star, Info, AlertTriangle, X } from 'lucide-react';

// Текущая цветовая схема (Синяя - Предыдущая)
const currentScheme = {
  name: 'Синяя (Предыдущая)',
  primary: {
    default: '#0060FF',
    hover: '#0047CC',
    active: '#0037A6',
    subtle: '#E7F3FF',
  },
  secondary: {
    default: '#00B7FF',
    hover: '#0095D6',
    active: '#0078B3',
    subtle: '#E1F5FF',
  },
  accent: {
    success: '#00AA5B',
    warning: '#F5A623',
    danger: '#E53935',
    promo: '#FF2E93',
  },
  text: {
    primary: '#1F2A44',
    secondary: '#4B5C7A',
    muted: '#7F8CA8',
    inverse: '#FFFFFF',
  },
  neutral: {
    100: '#FFFFFF',
    200: '#F5F7FB',
    300: '#E3E8F2',
    400: '#B9C3D6',
    500: '#8F9BB3',
    600: '#6B7A99',
    700: '#4B5C7A',
    800: '#2D3A52',
    900: '#1F2A44',
  },
  badge: {
    new: { bg: '#E7F3FF', text: '#0060FF' },
    hit: { bg: '#E0F5E8', text: '#00AA5B' },
    sale: { bg: '#FFE1E8', text: '#E53935' },
    promo: { bg: '#FFF0F5', text: '#FF2E93' },
  },
  toast: {
    success: { bg: '#E0F5E8', border: '#00AA5B' },
    error: { bg: '#FFE1E8', border: '#E53935' },
    warning: { bg: '#FFF5E1', border: '#F5A623' },
    info: { bg: '#E7F3FF', border: '#0060FF' },
  },
};

// Новая цветовая схема (Оранжевая - Текущая)
const newScheme = {
  name: 'Новая (Оранжевая)',
  primary: {
    default: '#FF6B00',
    hover: '#E65000',
    active: '#CC4400',
    subtle: '#FFF5EB',
  },
  secondary: {
    default: '#00B7FF',
    hover: '#0095D6',
    active: '#0078B3',
    subtle: '#E1F5FF',
  },
  accent: {
    success: '#00AA5B',
    warning: '#F5A623',
    danger: '#E53935',
    promo: '#FF2E93',
  },
  text: {
    primary: '#1F2A44',
    secondary: '#4B5C7A',
    muted: '#7F8CA8',
    inverse: '#FFFFFF',
  },
  neutral: {
    100: '#FFFFFF',
    200: '#F8F9FA',
    300: '#E3E8F2',
    400: '#B9C3D6',
    500: '#8F9BB3',
    600: '#6B7A99',
    700: '#4B5C7A',
    800: '#2D3A52',
    900: '#1F2A44',
  },
  badge: {
    new: { bg: '#FFF5EB', text: '#FF6B00' },
    hit: { bg: '#E0F5E8', text: '#00AA5B' },
    sale: { bg: '#FFE1E8', text: '#E53935' },
    promo: { bg: '#FFF0F5', text: '#FF2E93' },
  },
  toast: {
    success: { bg: '#E0F5E8', border: '#00AA5B' },
    error: { bg: '#FFE1E8', border: '#E53935' },
    warning: { bg: '#FFF5E1', border: '#F5A623' },
    info: { bg: '#E1F5FF', border: '#00B7FF' },
  },
};

type ColorScheme = typeof currentScheme;

interface ColorSwatchProps {
  color: string;
  label: string;
  textColor?: string;
}

/**
 * Компонент отображения цветового образца
 */
const ColorSwatch: React.FC<ColorSwatchProps> = ({ color, label, textColor = '#1F1F1F' }) => (
  <div className="flex items-center gap-3">
    <div
      className="w-12 h-12 rounded-lg shadow-sm border border-gray-200"
      style={{ backgroundColor: color }}
    />
    <div>
      <div className="text-sm font-medium" style={{ color: textColor }}>
        {label}
      </div>
      <div className="text-xs text-gray-500 font-mono">{color}</div>
    </div>
  </div>
);

interface ButtonDemoProps {
  scheme: ColorScheme;
}

/**
 * Демонстрация кнопок
 */
const ButtonDemo: React.FC<ButtonDemoProps> = ({ scheme }) => (
  <div className="space-y-4">
    <h4 className="font-semibold text-gray-900">Кнопки</h4>
    <div className="flex flex-wrap gap-3">
      <button
        className="px-6 py-2.5 rounded-md font-medium transition-colors"
        style={{
          backgroundColor: scheme.primary.default,
          color: scheme.text.inverse,
        }}
      >
        Primary
      </button>
      <button
        className="px-6 py-2.5 rounded-md font-medium border-2 transition-colors"
        style={{
          borderColor: scheme.primary.default,
          color: scheme.primary.default,
          backgroundColor: 'transparent',
        }}
      >
        Secondary
      </button>
      <button
        className="px-6 py-2.5 rounded-md font-medium transition-colors"
        style={{
          backgroundColor: scheme.primary.subtle,
          color: scheme.primary.default,
        }}
      >
        Subtle
      </button>
    </div>
  </div>
);

interface CheckboxDemoProps {
  scheme: ColorScheme;
}

/**
 * Демонстрация чекбоксов
 */
const CheckboxDemo: React.FC<CheckboxDemoProps> = ({ scheme }) => (
  <div className="space-y-4">
    <h4 className="font-semibold text-gray-900">Чекбоксы</h4>
    <div className="flex items-center gap-6">
      <label className="flex items-center gap-3 cursor-pointer">
        <div
          className="w-5 h-5 rounded flex items-center justify-center"
          style={{
            backgroundColor: scheme.primary.default,
            border: `1.5px solid ${scheme.primary.default}`,
          }}
        >
          <Check className="w-4 h-4 text-white" strokeWidth={3} />
        </div>
        <span style={{ color: scheme.text.primary }}>Выбрано</span>
      </label>
      <label className="flex items-center gap-3 cursor-pointer">
        <div
          className="w-5 h-5 rounded"
          style={{
            backgroundColor: 'transparent',
            border: `1.5px solid ${scheme.neutral[400]}`,
          }}
        />
        <span style={{ color: scheme.text.primary }}>Не выбрано</span>
      </label>
    </div>
  </div>
);

interface BadgeDemoProps {
  scheme: ColorScheme;
}

/**
 * Демонстрация бейджей
 */
const BadgeDemo: React.FC<BadgeDemoProps> = ({ scheme }) => (
  <div className="space-y-4">
    <h4 className="font-semibold text-gray-900">Бейджи</h4>
    <div className="flex flex-wrap gap-3">
      {Object.entries(scheme.badge).map(([key, value]) => (
        <span
          key={key}
          className="px-3 py-1 rounded-full text-xs font-medium"
          style={{
            backgroundColor: value.bg,
            color: value.text,
          }}
        >
          {key.toUpperCase()}
        </span>
      ))}
    </div>
  </div>
);

interface ToastDemoProps {
  scheme: ColorScheme;
}

/**
 * Демонстрация уведомлений
 */
const ToastDemo: React.FC<ToastDemoProps> = ({ scheme }) => {
  const icons = {
    success: Check,
    error: X,
    warning: AlertTriangle,
    info: Info,
  };

  return (
    <div className="space-y-4">
      <h4 className="font-semibold text-gray-900">Уведомления</h4>
      <div className="space-y-3">
        {Object.entries(scheme.toast).map(([key, value]) => {
          const Icon = icons[key as keyof typeof icons];
          return (
            <div
              key={key}
              className="flex items-center gap-3 px-4 py-3 rounded-lg"
              style={{
                backgroundColor: value.bg,
                borderLeft: `4px solid ${value.border}`,
              }}
            >
              <Icon className="w-5 h-5" style={{ color: value.border }} />
              <span className="text-sm font-medium" style={{ color: scheme.text.primary }}>
                {key.charAt(0).toUpperCase() + key.slice(1)} уведомление
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
};

interface PaginationDemoProps {
  scheme: ColorScheme;
}

/**
 * Демонстрация пагинации
 */
const PaginationDemo: React.FC<PaginationDemoProps> = ({ scheme }) => (
  <div className="space-y-4">
    <h4 className="font-semibold text-gray-900">Пагинация</h4>
    <div className="flex items-center gap-2">
      <button
        className="w-10 h-10 rounded-full border flex items-center justify-center"
        style={{ borderColor: scheme.neutral[300], color: scheme.text.muted }}
      >
        ←
      </button>
      {[1, 2, 3, 4, 5].map(num => (
        <button
          key={num}
          className="w-10 h-10 rounded-full flex items-center justify-center font-medium"
          style={
            num === 3
              ? { backgroundColor: scheme.primary.default, color: scheme.text.inverse }
              : { border: `1px solid ${scheme.neutral[300]}`, color: scheme.text.secondary }
          }
        >
          {num}
        </button>
      ))}
      <button
        className="w-10 h-10 rounded-full border flex items-center justify-center"
        style={{ borderColor: scheme.neutral[300], color: scheme.text.muted }}
      >
        →
      </button>
    </div>
  </div>
);

interface ProductCardDemoProps {
  scheme: ColorScheme;
}

/**
 * Демонстрация карточки товара
 */
const ProductCardDemo: React.FC<ProductCardDemoProps> = ({ scheme }) => (
  <div className="space-y-4">
    <h4 className="font-semibold text-gray-900">Карточка товара</h4>
    <div
      className="w-64 rounded-2xl overflow-hidden shadow-lg"
      style={{ backgroundColor: scheme.neutral[100] }}
    >
      <div className="relative">
        <div
          className="h-48 flex items-center justify-center"
          style={{ backgroundColor: scheme.neutral[200] }}
        >
          <ShoppingCart className="w-16 h-16" style={{ color: scheme.neutral[400] }} />
        </div>
        <span
          className="absolute top-3 left-3 px-2 py-1 rounded-full text-xs font-medium"
          style={{ backgroundColor: scheme.badge.new.bg, color: scheme.badge.new.text }}
        >
          NEW
        </span>
        <button
          className="absolute top-3 right-3 w-8 h-8 rounded-full flex items-center justify-center"
          style={{ backgroundColor: scheme.neutral[100] }}
        >
          <Heart className="w-4 h-4" style={{ color: scheme.accent.danger }} />
        </button>
      </div>
      <div className="p-4 space-y-3">
        <h5 className="font-semibold" style={{ color: scheme.text.primary }}>
          Название товара
        </h5>
        <div className="flex items-center gap-1">
          {[1, 2, 3, 4, 5].map(i => (
            <Star
              key={i}
              className="w-4 h-4"
              fill={i <= 4 ? '#FFB800' : 'none'}
              stroke={i <= 4 ? '#FFB800' : scheme.neutral[400]}
            />
          ))}
          <span className="text-xs ml-1" style={{ color: scheme.text.muted }}>
            (128)
          </span>
        </div>
        <div className="flex items-baseline gap-2">
          <span className="text-xl font-bold" style={{ color: scheme.text.primary }}>
            12 990 ₽
          </span>
          <span className="text-sm line-through" style={{ color: scheme.text.muted }}>
            15 990 ₽
          </span>
        </div>
        <button
          className="w-full py-2.5 rounded-xl font-medium transition-colors"
          style={{ backgroundColor: scheme.primary.default, color: scheme.text.inverse }}
        >
          В корзину
        </button>
      </div>
    </div>
  </div>
);

interface SchemeSectionProps {
  scheme: ColorScheme;
  title: string;
}

/**
 * Секция с демонстрацией цветовой схемы
 */
const SchemeSection: React.FC<SchemeSectionProps> = ({ scheme, title }) => (
  <div className="space-y-8 p-6 rounded-2xl bg-white shadow-lg">
    <h3 className="text-xl font-bold text-gray-900 border-b pb-4">{title}</h3>

    {/* Основные цвета */}
    <div className="space-y-4">
      <h4 className="font-semibold text-gray-900">Primary</h4>
      <div className="grid grid-cols-2 gap-4">
        <ColorSwatch color={scheme.primary.default} label="Default" />
        <ColorSwatch color={scheme.primary.hover} label="Hover" />
        <ColorSwatch color={scheme.primary.active} label="Active" />
        <ColorSwatch color={scheme.primary.subtle} label="Subtle" />
      </div>
    </div>

    <div className="space-y-4">
      <h4 className="font-semibold text-gray-900">Secondary</h4>
      <div className="grid grid-cols-2 gap-4">
        <ColorSwatch color={scheme.secondary.default} label="Default" />
        <ColorSwatch color={scheme.secondary.hover} label="Hover" />
      </div>
    </div>

    <div className="space-y-4">
      <h4 className="font-semibold text-gray-900">Accent</h4>
      <div className="grid grid-cols-2 gap-4">
        <ColorSwatch color={scheme.accent.success} label="Success" />
        <ColorSwatch color={scheme.accent.warning} label="Warning" />
        <ColorSwatch color={scheme.accent.danger} label="Danger" />
        <ColorSwatch color={scheme.accent.promo} label="Promo" />
      </div>
    </div>

    <div className="space-y-4">
      <h4 className="font-semibold text-gray-900">Text</h4>
      <div className="grid grid-cols-2 gap-4">
        <ColorSwatch color={scheme.text.primary} label="Primary" />
        <ColorSwatch color={scheme.text.secondary} label="Secondary" />
        <ColorSwatch color={scheme.text.muted} label="Muted" />
      </div>
    </div>

    <hr className="border-gray-200" />

    {/* Компоненты */}
    <ButtonDemo scheme={scheme} />
    <CheckboxDemo scheme={scheme} />
    <BadgeDemo scheme={scheme} />
    <ToastDemo scheme={scheme} />
    <PaginationDemo scheme={scheme} />
    <ProductCardDemo scheme={scheme} />
  </div>
);

/**
 * Главная страница сравнения дизайн-схем
 */
export default function DesignComparisonPage() {
  const [viewMode, setViewMode] = useState<'side-by-side' | 'toggle'>('side-by-side');
  const [activeScheme, setActiveScheme] = useState<'current' | 'new'>('current');

  return (
    <div className="min-h-screen bg-[#F5F7FB]">
      <div className="max-w-7xl mx-auto px-4 py-10">
        {/* Header */}
        <div className="text-center mb-10">
          <h1 className="text-4xl font-bold text-gray-900 mb-4">
            Сравнение цветовых схем FREESPORT
          </h1>
          <p className="text-lg text-gray-600 max-w-2xl mx-auto">
            Визуальное сравнение предыдущей синей схемы и новой оранжевой палитры для принятия
            решения о миграции
          </p>
        </div>

        {/* View Mode Toggle */}
        <div className="flex justify-center mb-8">
          <div className="inline-flex rounded-full bg-white p-1 shadow-sm">
            <button
              onClick={() => setViewMode('side-by-side')}
              className={`px-6 py-2 rounded-full text-sm font-medium transition-colors ${viewMode === 'side-by-side'
                  ? 'bg-primary text-white'
                  : 'text-gray-600 hover:text-gray-900'
                }`}
            >
              Рядом
            </button>
            <button
              onClick={() => setViewMode('toggle')}
              className={`px-6 py-2 rounded-full text-sm font-medium transition-colors ${viewMode === 'toggle'
                  ? 'bg-primary text-white'
                  : 'text-gray-600 hover:text-gray-900'
                }`}
            >
              Переключение
            </button>
          </div>
        </div>

        {/* Toggle Mode Selector */}
        {viewMode === 'toggle' && (
          <div className="flex justify-center mb-8">
            <div className="inline-flex rounded-full bg-white p-1 shadow-sm">
              <button
                onClick={() => setActiveScheme('current')}
                className={`px-6 py-2 rounded-full text-sm font-medium transition-colors ${activeScheme === 'current'
                    ? 'bg-gray-800 text-white'
                    : 'text-gray-600 hover:text-gray-900'
                  }`}
              >
                Текущая (Синяя)
              </button>
              <button
                onClick={() => setActiveScheme('new')}
                className={`px-6 py-2 rounded-full text-sm font-medium transition-colors ${activeScheme === 'new'
                    ? 'bg-primary text-white'
                    : 'text-gray-600 hover:text-gray-900'
                  }`}
              >
                Новая (Оранжевая)
              </button>
            </div>
          </div>
        )}

        {/* Content */}
        {viewMode === 'side-by-side' ? (
          <div className="grid lg:grid-cols-2 gap-8">
            <SchemeSection scheme={currentScheme} title={currentScheme.name} />
            <SchemeSection scheme={newScheme} title={newScheme.name} />
          </div>
        ) : (
          <div className="max-w-2xl mx-auto">
            <SchemeSection
              scheme={activeScheme === 'current' ? currentScheme : newScheme}
              title={activeScheme === 'current' ? currentScheme.name : newScheme.name}
            />
          </div>
        )}

        {/* Summary */}
        <div className="mt-12 bg-white rounded-2xl shadow-lg p-8">
          <h2 className="text-2xl font-bold text-gray-900 mb-6">Ключевые изменения</h2>
          <div className="grid md:grid-cols-2 gap-8">
            <div>
              <h3 className="font-semibold text-gray-900 mb-3">Преимущества новой схемы</h3>
              <ul className="space-y-2 text-gray-600">
                <li className="flex items-start gap-2">
                  <Check className="w-5 h-5 text-green-500 mt-0.5 flex-shrink-0" />
                  <span>Более яркий и запоминающийся бренд</span>
                </li>
                <li className="flex items-start gap-2">
                  <Check className="w-5 h-5 text-green-500 mt-0.5 flex-shrink-0" />
                  <span>Улучшенная визуальная иерархия</span>
                </li>
                <li className="flex items-start gap-2">
                  <Check className="w-5 h-5 text-green-500 mt-0.5 flex-shrink-0" />
                  <span>Повышенная конверсия CTA-элементов</span>
                </li>
                <li className="flex items-start gap-2">
                  <Check className="w-5 h-5 text-green-500 mt-0.5 flex-shrink-0" />
                  <span>Соответствие трендам e-commerce (OZON, Wildberries)</span>
                </li>
              </ul>
            </div>
            <div>
              <h3 className="font-semibold text-gray-900 mb-3">Что нужно обновить</h3>
              <ul className="space-y-2 text-gray-600">
                <li className="flex items-start gap-2">
                  <Info className="w-5 h-5 text-blue-500 mt-0.5 flex-shrink-0" />
                  <span>design-system.json — токены цветов</span>
                </li>
                <li className="flex items-start gap-2">
                  <Info className="w-5 h-5 text-blue-500 mt-0.5 flex-shrink-0" />
                  <span>globals.css — CSS-переменные</span>
                </li>
                <li className="flex items-start gap-2">
                  <Info className="w-5 h-5 text-blue-500 mt-0.5 flex-shrink-0" />
                  <span>Компоненты с хардкодом цветов</span>
                </li>
                <li className="flex items-start gap-2">
                  <Info className="w-5 h-5 text-blue-500 mt-0.5 flex-shrink-0" />
                  <span>Пагинация в каталоге</span>
                </li>
              </ul>
            </div>
          </div>
        </div>

        {/* Documentation Link */}
        <div className="mt-8 text-center">
          <p className="text-gray-600">
            Подробная документация:{' '}
            <code className="bg-gray-100 px-2 py-1 rounded text-sm">
              docs/frontend/color-scheme-migration.md
            </code>
          </p>
        </div>
      </div>
    </div>
  );
}
