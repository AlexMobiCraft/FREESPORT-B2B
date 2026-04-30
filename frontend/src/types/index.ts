/**
 * Типы TypeScript для FREESPORT Platform
 * Интеграция с Django backend API
 */

// Типы пользователей и аутентификации
export interface User {
  id: number;
  email: string;
  firstName: string;
  lastName: string;
  role: UserRole;
  phone?: string;
  companyName?: string;
  taxId?: string;
  isVerified: boolean;
  createdAt: string;
  updatedAt: string;
}

export type UserRole =
  | 'retail'
  | 'wholesale_level1'
  | 'wholesale_level2'
  | 'wholesale_level3'
  | 'trainer'
  | 'federation_rep'
  | 'admin';

export interface AuthTokens {
  access: string;
  refresh: string;
}

export interface AuthResponse {
  user: User;
  tokens: AuthTokens;
}

// Типы API ответов
export interface ApiResponse<T = unknown> {
  success: boolean;
  data?: T;
  message?: string;
  errors?: Record<string, string[]>;
}

export interface PaginatedResponse<T> {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
}

// Типы для компонентов
export interface BaseComponentProps {
  className?: string;
  children?: React.ReactNode;
}

// Типы форм
export interface LoginFormData {
  email: string;
  password: string;
  rememberMe: boolean;
}

export interface RegisterFormData {
  email: string;
  password: string;
  confirmPassword: string;
  firstName: string;
  lastName: string;
  phone?: string;
  role: UserRole;
  companyName?: string;
  taxId?: string;
}

// Экспорт типов баннеров
export type { Banner } from './banners';
