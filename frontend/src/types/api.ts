/**
 * API Types для FREESPORT Frontend
 *
 * Кастомные TypeScript типы для работы с API
 * Дополняют auto-generated типы из api.generated.ts
 */

export interface User {
  id: number;
  email: string;
  first_name: string;
  last_name: string;
  phone: string;
  role:
  | 'retail'
  | 'wholesale_level1'
  | 'wholesale_level2'
  | 'wholesale_level3'
  | 'trainer'
  | 'federation_rep'
  | 'admin';
  company_name?: string;
  tax_id?: string;
  is_verified?: boolean;
}

export interface Brand {
  id: number;
  name: string;
  slug: string;
  image?: string | null;
  description?: string | null;
  website?: string | null;
  is_featured: boolean;
}

export interface Product {
  id: number;
  name: string;
  slug: string;
  description?: string;
  short_description?: string;
  retail_price: number;
  old_price?: number;
  opt1_price?: number;
  opt2_price?: number;
  opt3_price?: number;
  is_in_stock: boolean;
  stock_quantity?: number;
  /** Основное изображение, возвращаемое списочным API */
  main_image?: string | null;
  /** Совместимость с ранними моками */
  image?: string | null;
  category: {
    id: number;
    name: string;
    slug: string;
  };
  category_id?: number;
  brand?: Brand | null;
  images?: Array<{
    id: number;
    image: string;
    is_primary: boolean;
  }>;
  /** Признак доступности к заказу (backend field) */
  can_be_ordered?: boolean;

  // Story 11.0: Маркетинговые флаги для бейджей
  is_hit: boolean;
  is_new: boolean;
  is_sale: boolean;
  is_promo: boolean;
  is_premium: boolean;
  discount_percent: number | null;
  rrp?: number;
  msrp?: number;
  rating?: number;
  reviews_count?: number;
  created_at?: string;
  updated_at?: string;
}

export interface CartItem {
  id: number;
  product: {
    id: number;
    name: string;
    slug: string;
    retail_price: number;
    opt1_price?: number;
    is_in_stock: boolean;
  };
  quantity: number;
  price: number;
}

export interface Cart {
  id: number;
  items: CartItem[];
  total_amount: number;
  promo_code?: string;
  discount_amount?: number;
}

export interface Order {
  id: number;
  order_number: string;
  status: 'pending' | 'confirmed' | 'processing' | 'shipped' | 'delivered' | 'cancelled';
  items: Array<{
    id: number;
    product_snapshot: {
      name: string;
      price: number;
    };
    quantity: number;
    price: number;
  }>;
  total_amount: number;
  created_at: string;
  updated_at: string;
}

export interface Category {
  id: number;
  name: string;
  slug: string;
  parent_id: number | null;
  level: number;
  icon: string | null;
  image?: string | null;
  products_count: number;
  description?: string;
}

export interface CategoryTree extends Category {
  children?: CategoryTree[];
}

export interface PaginatedResponse<T> {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
}

export interface LoginRequest {
  email: string;
  password: string;
}

export interface LoginResponse {
  access: string;
  refresh: string;
  user: User;
}

export interface RegisterRequest {
  email: string;
  password: string;
  password_confirm: string;
  first_name: string;
  last_name: string;
  phone: string;
  role?: string;
  company_name?: string;
  tax_id?: string;
}

export interface RegisterResponse {
  user: User;
  access: string;
  refresh: string;
}

export interface RefreshTokenRequest {
  refresh: string;
}

export interface RefreshTokenResponse {
  access: string;
}

// Logout Types (Story 31.2)
export interface LogoutRequest {
  refresh: string;
}

// Password Reset Types (Story 28.3)
export interface PasswordResetRequest {
  email: string;
}

export interface PasswordResetResponse {
  detail: string;
}

export interface ValidateTokenRequest {
  uid: string;
  token: string;
}

export interface ValidateTokenResponse {
  valid: boolean;
}

export interface PasswordResetConfirmRequest {
  uid: string;
  token: string;
  new_password: string;
}

export interface PasswordResetConfirmResponse {
  detail: string;
}

export interface ApiError {
  detail?: string;
  message?: string;
  errors?: Record<string, string[]>;
}

// Newsletter Subscription Types
export interface SubscribeRequest {
  email: string;
}

export interface SubscribeResponse {
  message: string;
  email: string;
}

export interface SubscribeError {
  error: string;
  field?: string;
  email?: string;
}

// News Types
export interface NewsItem {
  id: number;
  title: string;
  slug: string;
  excerpt: string;
  content?: string;
  image: string | null;
  published_at: string;
  created_at: string;
  updated_at: string;
  author?: string;
  category?: string;
}

export interface NewsList {
  count: number;
  next: string | null;
  previous: string | null;
  results: NewsItem[];
}

// Blog Types
export interface BlogItem {
  id: number;
  title: string;
  slug: string;
  subtitle?: string;
  excerpt: string;
  content?: string;
  image: string | null;
  author?: string;
  category?: string;
  published_at: string;
  created_at: string;
  updated_at: string;
  meta_title?: string;
  meta_description?: string;
}

export interface BlogList {
  count: number;
  next: string | null;
  previous: string | null;
  results: BlogItem[];
}

// Product Detail Types (Story 12.1)
export interface ProductImage {
  id?: number;
  image: string;
  alt_text?: string;
  is_primary: boolean;
}

export interface ProductPrice {
  retail: number;
  wholesale?: {
    level1?: number;
    level2?: number;
    level3?: number;
  };
  trainer?: number;
  federation?: number;
  currency: string;
}

export interface CategoryBreadcrumb {
  id: number;
  name: string;
  slug: string;
}

export interface ProductCategory {
  id: number;
  name: string;
  slug: string;
  breadcrumbs: CategoryBreadcrumb[];
}

/**
 * ProductVariant интерфейс (Story 13.x)
 * Представляет вариант товара с конкретными характеристиками
 */
export interface ProductVariant {
  id: number;
  sku: string;
  color_name?: string | null;
  size_value?: string | null;
  current_price: string; // Decimal as string
  color_hex?: string | null;
  stock_quantity: number;
  is_in_stock: boolean;
  available_quantity: number;
  stock_range?: string;
  rrp?: string;
  msrp?: string;
  main_image?: string | null;
  gallery_images?: string[];
}

export interface ProductDetail {
  id: number;
  slug: string;
  name: string;
  sku: string;
  brand: string;
  description: string;
  full_description?: string;
  price: ProductPrice;
  stock_quantity: number;
  images: ProductImage[];
  rating?: number;
  reviews_count?: number;
  specifications?: Record<string, string>;
  category: ProductCategory;
  is_in_stock: boolean;
  can_be_ordered: boolean;
  /** Варианты товара (Story 13.x) */
  variants?: ProductVariant[];
}
