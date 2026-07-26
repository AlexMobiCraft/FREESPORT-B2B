/**
 * Mock данные для детальной страницы товара (Story 12.1)
 */

import type { ProductDetail } from '@/types/api';

/**
 * Backend API format - то что возвращает Django REST API
 * Используется в MSW handlers
 */
export const MOCK_PRODUCT_DETAIL_API = {
  id: 101,
  slug: 'asics-gel-blast-ff',
  name: 'ASICS Gel-Blast FF',
  sku: 'AS-GB-FF-2025',
  brand: { name: 'ASICS' },
  description: 'Профессиональные кроссовки для интенсивных тренировок',
  full_description:
    'ASICS Gel-Blast FF - это кроссовки нового поколения для игры в зале. Технология FlyteFoam обеспечивает превосходную амортизацию при минимальном весе. Гелевая прокладка в пятке гарантирует комфорт при приземлении.',
  retail_price: 12990,
  opt1_price: 11890,
  opt2_price: 11290,
  opt3_price: 10790,
  trainer_price: 10990,
  federation_price: 9990,
  stock_quantity: 34,
  images: [
    {
      id: 1,
      url: 'https://cdn.freesport.ru/products/asics-gel-blast-ff/main.jpg',
      alt_text: 'ASICS Gel-Blast FF front',
      is_main: true,
    },
    {
      id: 2,
      url: 'https://cdn.freesport.ru/products/asics-gel-blast-ff/side.jpg',
      alt_text: 'ASICS Gel-Blast FF side',
      is_main: false,
    },
    {
      id: 3,
      url: 'https://cdn.freesport.ru/products/asics-gel-blast-ff/back.jpg',
      alt_text: 'ASICS Gel-Blast FF back',
      is_main: false,
    },
  ],
  rating: 4.7,
  reviews_count: 38,
  specifications: {
    Материал: 'Полиамид + сетка',
    Вес: '310 г',
    Цвета: 'black, lime',
    Размеры: '36-46',
    'Страна производства': 'Вьетнам',
    Назначение: 'Зальный гандбол, волейбол',
    Технологии: 'FlyteFoam, Gel, Trusstic System',
  },
  category: {
    id: 1,
    name: 'Обувь',
    slug: 'obuv',
  },
  category_breadcrumbs: [
    { id: 1, name: 'Главная', slug: '/' },
    { id: 2, name: 'Обувь', slug: '/catalog/obuv' },
    { id: 3, name: 'Зал', slug: '/catalog/zal' },
    { id: 4, name: 'ASICS', slug: '/catalog/asics' },
  ],
  is_in_stock: true,
  can_be_ordered: true,
  is_hit: false,
  is_new: false,
  is_sale: false,
  is_promo: false,
  is_premium: false,
  discount_percent: null,
};

/**
 * Frontend format - то что используют React компоненты
 */
export const MOCK_PRODUCT_DETAIL: ProductDetail = {
  id: 101,
  slug: 'asics-gel-blast-ff',
  name: 'ASICS Gel-Blast FF',
  sku: 'AS-GB-FF-2025',
  brand: 'ASICS',
  description: 'Профессиональные кроссовки для интенсивных тренировок',
  full_description:
    'ASICS Gel-Blast FF - это кроссовки нового поколения для игры в зале. Технология FlyteFoam обеспечивает превосходную амортизацию при минимальном весе. Гелевая прокладка в пятке гарантирует комфорт при приземлении.',
  price: {
    retail: 12990,
    wholesale: {
      level1: 11890,
      level2: 11290,
      level3: 10790,
    },
    trainer: 10990,
    federation: 9990,
    currency: 'RUB',
  },
  stock_quantity: 34,
  images: [
    {
      id: 1,
      image: 'https://cdn.freesport.ru/products/asics-gel-blast-ff/main.jpg',
      alt_text: 'ASICS Gel-Blast FF front',
      is_primary: true,
    },
    {
      id: 2,
      image: 'https://cdn.freesport.ru/products/asics-gel-blast-ff/side.jpg',
      alt_text: 'ASICS Gel-Blast FF side',
      is_primary: false,
    },
    {
      id: 3,
      image: 'https://cdn.freesport.ru/products/asics-gel-blast-ff/back.jpg',
      alt_text: 'ASICS Gel-Blast FF back',
      is_primary: false,
    },
  ],
  rating: 4.7,
  reviews_count: 38,
  specifications: {
    Материал: 'Полиамид + сетка',
    Вес: '310 г',
    Цвета: 'black, lime',
    Размеры: '36-46',
    'Страна производства': 'Вьетнам',
    Назначение: 'Зальный гандбол, волейбол',
    Технологии: 'FlyteFoam, Gel, Trusstic System',
  },
  category: {
    id: 1,
    name: 'Обувь',
    slug: 'obuv',
    breadcrumbs: [
      { id: 1, name: 'Главная', slug: '/' },
      { id: 2, name: 'Обувь', slug: '/catalog/obuv' },
      { id: 3, name: 'Зал', slug: '/catalog/zal' },
      { id: 4, name: 'ASICS', slug: '/catalog/asics' },
    ],
  },
  is_in_stock: true,
  can_be_ordered: true,
  variants: [],
};

export const MOCK_OUT_OF_STOCK_PRODUCT: ProductDetail = {
  ...MOCK_PRODUCT_DETAIL,
  id: 102,
  slug: 'out-of-stock-product',
  stock_quantity: 0,
  is_in_stock: false,
  can_be_ordered: true,
};

export const MOCK_UNAVAILABLE_PRODUCT: ProductDetail = {
  ...MOCK_PRODUCT_DETAIL,
  id: 103,
  slug: 'unavailable-product',
  stock_quantity: 0,
  is_in_stock: false,
  can_be_ordered: false,
};

/**
 * Story 13.5a: Mock данные для товара с вариантами (размеры и цвета)
 * Используется для тестирования ProductOptions компонента
 */
export interface ProductVariant {
  id: number;
  sku: string;
  color_name?: string;
  color_hex?: string | null;
  size_value?: string;
  current_price: string;
  stock_quantity: number;
  is_in_stock: boolean;
  available_quantity: number;
}

export interface ProductDetailWithVariants extends ProductDetail {
  variants: ProductVariant[];
}

export const MOCK_PRODUCT_VARIANTS: ProductVariant[] = [
  {
    id: 1,
    sku: 'NIKE-AM-RED-42',
    color_name: 'Красный',
    color_hex: '#FF0000',
    size_value: '42',
    current_price: '5990.00',
    stock_quantity: 15,
    is_in_stock: true,
    available_quantity: 15,
  },
  {
    id: 2,
    sku: 'NIKE-AM-RED-43',
    color_name: 'Красный',
    color_hex: '#FF0000',
    size_value: '43',
    current_price: '5990.00',
    stock_quantity: 0,
    is_in_stock: false,
    available_quantity: 0,
  },
  {
    id: 3,
    sku: 'NIKE-AM-RED-44',
    color_name: 'Красный',
    color_hex: '#FF0000',
    size_value: '44',
    current_price: '5990.00',
    stock_quantity: 8,
    is_in_stock: true,
    available_quantity: 8,
  },
  {
    id: 4,
    sku: 'NIKE-AM-BLUE-42',
    color_name: 'Синий',
    color_hex: '#0000FF',
    size_value: '42',
    current_price: '5990.00',
    stock_quantity: 10,
    is_in_stock: true,
    available_quantity: 10,
  },
  {
    id: 5,
    sku: 'NIKE-AM-BLUE-43',
    color_name: 'Синий',
    color_hex: '#0000FF',
    size_value: '43',
    current_price: '5990.00',
    stock_quantity: 5,
    is_in_stock: true,
    available_quantity: 5,
  },
  {
    id: 6,
    sku: 'NIKE-AM-BLUE-44',
    color_name: 'Синий',
    color_hex: '#0000FF',
    size_value: '44',
    current_price: '5990.00',
    stock_quantity: 0,
    is_in_stock: false,
    available_quantity: 0,
  },
  {
    id: 7,
    sku: 'NIKE-AM-BLACK-42',
    color_name: 'Черный',
    color_hex: '#000000',
    size_value: '42',
    current_price: '6490.00',
    stock_quantity: 20,
    is_in_stock: true,
    available_quantity: 20,
  },
  {
    id: 8,
    sku: 'NIKE-AM-BLACK-43',
    color_name: 'Черный',
    color_hex: '#000000',
    size_value: '43',
    current_price: '6490.00',
    stock_quantity: 12,
    is_in_stock: true,
    available_quantity: 12,
  },
];

export const MOCK_PRODUCT_WITH_VARIANTS: ProductDetailWithVariants = {
  id: 201,
  slug: 'nike-air-max',
  name: 'Кроссовки Nike Air Max',
  sku: 'NIKE-AM-2025',
  brand: 'Nike',
  description: 'Легендарные кроссовки Nike Air Max с технологией воздушной подушки',
  full_description:
    'Nike Air Max - это культовая модель кроссовок, которая сочетает в себе стиль и комфорт. Технология Air Max обеспечивает превосходную амортизацию при каждом шаге.',
  price: {
    retail: 5990,
    wholesale: {
      level1: 5490,
      level2: 5190,
      level3: 4890,
    },
    trainer: 4990,
    federation: 4490,
    currency: 'RUB',
  },
  stock_quantity: 70,
  images: [
    {
      id: 1,
      image: 'https://cdn.freesport.ru/products/nike-air-max/main.jpg',
      alt_text: 'Nike Air Max front',
      is_primary: true,
    },
    {
      id: 2,
      image: 'https://cdn.freesport.ru/products/nike-air-max/side.jpg',
      alt_text: 'Nike Air Max side',
      is_primary: false,
    },
  ],
  rating: 4.8,
  reviews_count: 156,
  specifications: {
    Материал: 'Кожа + текстиль',
    Вес: '320 г',
    Технологии: 'Air Max, Cushlon',
    'Страна производства': 'Вьетнам',
    Назначение: 'Повседневная носка, бег',
  },
  category: {
    id: 2,
    name: 'Обувь',
    slug: 'obuv',
    breadcrumbs: [
      { id: 1, name: 'Главная', slug: '/' },
      { id: 2, name: 'Обувь', slug: '/catalog/obuv' },
      { id: 5, name: 'Кроссовки', slug: '/catalog/sneakers' },
      { id: 6, name: 'Nike', slug: '/catalog/nike' },
    ],
  },
  is_in_stock: true,
  can_be_ordered: true,
  variants: MOCK_PRODUCT_VARIANTS,
};
