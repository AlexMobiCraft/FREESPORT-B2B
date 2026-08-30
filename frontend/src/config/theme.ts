/**
 * Theme Configuration for FREESPORT
 *
 * This module provides feature flags for theme switching between:
 * - 'classic' - Current blue light theme
 * - 'electric-orange' - New dark theme with orange accents
 *
 * Usage:
 * import { THEME, isElectricOrange } from '@/config/theme';
 *
 * if (isElectricOrange()) {
 *   // Apply Electric Orange styles
 * }
 */

export type ThemeName = 'classic' | 'electric-orange';

/**
 * Theme configuration object
 */
export const THEME = {
  /**
   * Current active theme.
   * Controlled by NEXT_PUBLIC_THEME environment variable.
   * Default: 'classic'
   */
  current: (process.env.NEXT_PUBLIC_THEME as ThemeName) || 'classic',

  /**
   * Available themes
   */
  themes: {
    classic: {
      name: 'Classic Blue',
      description: 'Original light theme with blue accents',
      cssFile: 'globals.css',
    },
    'electric-orange': {
      name: 'Electric Orange',
      description: 'Dark theme with Digital Brutalism aesthetic',
      cssFile: 'globals-electric-orange.css',
    },
  },
} as const;

/**
 * Check if Electric Orange theme is active
 */
export function isElectricOrange(): boolean {
  return THEME.current === 'electric-orange';
}

/**
 * Check if Classic theme is active
 */
export function isClassic(): boolean {
  return THEME.current === 'classic';
}

/**
 * Get current theme configuration
 */
export function getCurrentTheme() {
  return THEME.themes[THEME.current];
}

/**
 * Theme-specific class names helper
 * Returns the appropriate class based on current theme
 *
 * @example
 * const bgClass = themeClass({
 *   classic: 'bg-white',
 *   'electric-orange': 'bg-[#0F0F0F]'
 * });
 */
export function themeClass(classes: Record<ThemeName, string>): string {
  return classes[THEME.current] || classes.classic;
}

/**
 * Theme-specific value helper
 * Returns the appropriate value based on current theme
 *
 * @example
 * const primaryColor = themeValue({
 *   classic: '#0060FF',
 *   'electric-orange': '#FF6B00'
 * });
 */
export function themeValue<T>(values: Record<ThemeName, T>): T {
  return values[THEME.current] ?? values.classic;
}

/**
 * Theme CSS variables
 * These are the key design tokens for each theme
 */
export const THEME_TOKENS = {
  classic: {
    primary: '#FF6600',
    primaryHover: '#E65C00',
    bgBody: '#FFFFFF',
    bgCard: '#FFFFFF',
    textPrimary: '#1F2A44',
    textSecondary: '#4B5C7A',
    border: '#E3E8F2',
  },
  'electric-orange': {
    primary: '#FF6B00',
    primaryHover: '#FF8533',
    bgBody: '#0F0F0F',
    bgCard: '#1A1A1A',
    textPrimary: '#FFFFFF',
    textSecondary: '#A0A0A0',
    border: '#333333',
  },
} as const;

/**
 * Get current theme tokens
 */
export function getThemeTokens() {
  return THEME_TOKENS[THEME.current];
}
