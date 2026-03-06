/**
 * MSW API Handlers для Story 11.2
 * Mock handlers для тестирования динамических блоков контента
 */

import { http, HttpResponse } from 'msw';
import type { Product, Category, NewsItem } from '@/types/api';
import {
  MOCK_PRODUCT_DETAIL_API,
  MOCK_OUT_OF_STOCK_PRODUCT,
  MOCK_UNAVAILABLE_PRODUCT,
  MOCK_PRODUCT_WITH_VARIANTS,
} from '../productDetail';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8001/api/v1';

/**
 * Mock данные для хитов продаж (AC 1)
 */
const mockHitsProducts: Product[] = [
  {
    id: 1,
    name: 'Футбольный мяч Nike Strike',
    slug: 'nike-strike-ball',
    description: 'Профессиональный футбольный мяч',
    retail_price: 2500,
    is_in_stock: true,
    category: { id: 1, name: 'Футбол', slug: 'football' },
    images: [{ id: 1, image: '/images/nike-strike.jpg', is_primary: true }],
    // Story 11.0: Маркетинговые флаги
    is_hit: true,
    is_new: false,
    is_sale: true, // Приоритет 1: показываем sale бейдж
    is_promo: false,
    is_premium: false,
    discount_percent: 20,
  },
  {
    id: 2,
    name: 'Кроссовки Adidas Ultraboost',
    slug: 'adidas-ultraboost',
    description: 'Беговые кроссовки премиум класса',
    retail_price: 15000,
    is_in_stock: true,
    category: { id: 2, name: 'Бег', slug: 'running' },
    images: [{ id: 2, image: '/images/ultraboost.jpg', is_primary: true }],
    // Story 11.0: Только hit флаг
    is_hit: true,
    is_new: false,
    is_sale: false,
    is_promo: false,
    is_premium: false,
    discount_percent: null,
  },
  {
    id: 3,
    name: 'Ракетка Wilson Pro Staff',
    slug: 'wilson-pro-staff',
    description: 'Профессиональная теннисная ракетка',
    retail_price: 18000,
    is_in_stock: true,
    category: { id: 3, name: 'Теннис', slug: 'tennis' },
    images: [{ id: 3, image: '/images/wilson-racket.jpg', is_primary: true }],
    is_hit: true,
    is_new: false,
    is_sale: false,
    is_promo: true, // Приоритет 2
    is_premium: false,
    discount_percent: null,
  },
  {
    id: 4,
    name: 'Велосипед Trek Marlin 7',
    slug: 'trek-marlin-7',
    description: 'Горный велосипед для профессионалов',
    retail_price: 65000,
    is_in_stock: true,
    category: { id: 4, name: 'Велоспорт', slug: 'cycling' },
    images: [{ id: 4, image: '/images/trek-marlin.jpg', is_primary: true }],
    is_hit: true,
    is_new: false,
    is_sale: false,
    is_promo: false,
    is_premium: true, // Приоритет 5
    discount_percent: null,
  },
  {
    id: 5,
    name: 'Перчатки вратарские Uhlsport',
    slug: 'uhlsport-gloves',
    description: 'Профессиональные вратарские перчатки',
    retail_price: 4500,
    is_in_stock: true,
    category: { id: 1, name: 'Футбол', slug: 'football' },
    images: [],
    is_hit: true,
    is_new: false,
    is_sale: false,
    is_promo: false,
    is_premium: false,
    discount_percent: null,
  },
  {
    id: 6,
    name: 'Куртка Columbia OutDry',
    slug: 'columbia-outdry',
    description: 'Водонепроницаемая куртка для активного отдыха',
    retail_price: 12000,
    is_in_stock: true,
    category: { id: 5, name: 'Outdoor', slug: 'outdoor' },
    images: [{ id: 6, image: '/images/columbia-jacket.jpg', is_primary: true }],
    is_hit: true,
    is_new: false,
    is_sale: false,
    is_promo: false,
    is_premium: false,
    discount_percent: null,
  },
  {
    id: 7,
    name: 'Мяч баскетбольный Spalding NBA',
    slug: 'spalding-nba',
    description: 'Официальный мяч NBA',
    retail_price: 5500,
    is_in_stock: true,
    category: { id: 6, name: 'Баскетбол', slug: 'basketball' },
    images: [{ id: 7, image: '/images/spalding-nba.jpg', is_primary: true }],
    is_hit: true,
    is_new: false,
    is_sale: false,
    is_promo: false,
    is_premium: false,
    discount_percent: null,
  },
  {
    id: 8,
    name: 'Коньки хоккейные Bauer Vapor',
    slug: 'bauer-vapor',
    description: 'Профессиональные хоккейные коньки',
    retail_price: 22000,
    is_in_stock: true,
    category: { id: 7, name: 'Хоккей', slug: 'hockey' },
    images: [{ id: 8, image: '/images/bauer-vapor.jpg', is_primary: true }],
    is_hit: true,
    is_new: false,
    is_sale: false,
    is_promo: false,
    is_premium: false,
    discount_percent: null,
  },
];

/**
 * Mock данные для новинок (AC 2)
 */
const mockNewProducts: Product[] = [
  {
    id: 10,
    name: 'Новая модель ракетки Wilson Blade',
    slug: 'wilson-blade-new',
    description: 'Новинка 2025 года',
    retail_price: 19000,
    is_in_stock: true,
    category: { id: 3, name: 'Теннис', slug: 'tennis' },
    images: [{ id: 10, image: '/images/wilson-blade.jpg', is_primary: true }],
    // Story 11.0: Новинка с акцией
    is_hit: false,
    is_new: true,
    is_sale: false,
    is_promo: true, // Приоритет 2 (выше чем new)
    is_premium: false,
    discount_percent: null,
  },
  {
    id: 11,
    name: 'Новые кроссовки Nike Air Zoom',
    slug: 'nike-air-zoom-new',
    description: 'Последняя модель беговых кроссовок',
    retail_price: 13500,
    is_in_stock: true,
    category: { id: 2, name: 'Бег', slug: 'running' },
    images: [{ id: 11, image: '/images/nike-air-zoom.jpg', is_primary: true }],
    is_hit: false,
    is_new: true,
    is_sale: false,
    is_promo: false,
    is_premium: false,
    discount_percent: null,
  },
  {
    id: 12,
    name: 'Тренажер домашний NordicTrack',
    slug: 'nordictrack-home',
    description: 'Инновационный домашний тренажер',
    retail_price: 85000,
    is_in_stock: true,
    category: { id: 8, name: 'Фитнес', slug: 'fitness' },
    images: [{ id: 12, image: '/images/nordictrack.jpg', is_primary: true }],
    is_hit: false,
    is_new: true,
    is_sale: false,
    is_promo: false,
    is_premium: true,
    discount_percent: null,
  },
  {
    id: 13,
    name: 'Скейтборд Element Complete',
    slug: 'element-complete',
    description: 'Профессиональный скейтборд',
    retail_price: 7500,
    is_in_stock: true,
    category: { id: 9, name: 'Экстрим', slug: 'extreme' },
    images: [{ id: 13, image: '/images/element-skateboard.jpg', is_primary: true }],
    is_hit: false,
    is_new: true,
    is_sale: false,
    is_promo: false,
    is_premium: false,
    discount_percent: null,
  },
  {
    id: 14,
    name: 'Гантели регулируемые Bowflex',
    slug: 'bowflex-dumbbells',
    description: 'Регулируемые гантели для дома',
    retail_price: 35000,
    is_in_stock: true,
    category: { id: 8, name: 'Фитнес', slug: 'fitness' },
    images: [],
    is_hit: false,
    is_new: true,
    is_sale: false,
    is_promo: false,
    is_premium: false,
    discount_percent: null,
  },
  {
    id: 15,
    name: 'Лыжи горные Rossignol Experience',
    slug: 'rossignol-experience',
    description: 'Горные лыжи нового поколения',
    retail_price: 42000,
    is_in_stock: true,
    category: { id: 10, name: 'Зимние виды спорта', slug: 'winter' },
    images: [{ id: 15, image: '/images/rossignol.jpg', is_primary: true }],
    is_hit: false,
    is_new: true,
    is_sale: false,
    is_promo: false,
    is_premium: false,
    discount_percent: null,
  },
  {
    id: 16,
    name: 'Сноуборд Burton Custom',
    slug: 'burton-custom',
    description: 'Профессиональный сноуборд',
    retail_price: 38000,
    is_in_stock: true,
    category: { id: 10, name: 'Зимние виды спорта', slug: 'winter' },
    images: [{ id: 16, image: '/images/burton-custom.jpg', is_primary: true }],
    is_hit: false,
    is_new: true,
    is_sale: false,
    is_promo: false,
    is_premium: false,
    discount_percent: null,
  },
  {
    id: 17,
    name: 'Палатка туристическая MSR Hubba',
    slug: 'msr-hubba',
    description: 'Легкая туристическая палатка',
    retail_price: 28000,
    is_in_stock: true,
    category: { id: 5, name: 'Outdoor', slug: 'outdoor' },
    images: [{ id: 17, image: '/images/msr-hubba.jpg', is_primary: true }],
    is_hit: false,
    is_new: true,
    is_sale: false,
    is_promo: false,
    is_premium: false,
    discount_percent: null,
  },
];

/**
 * Mock данные для новостей (Story 11.3)
 */
const mockNews: NewsItem[] = [
  {
    id: 1,
    title: 'Новая коллекция 2025',
    slug: 'new-collection-2025',
    excerpt: 'Представляем новую коллекцию спортивной одежды и экипировки на 2025 год.',
    image: '/images/news/collection-2025.jpg',
    published_at: new Date().toISOString(),
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
  },
  {
    id: 2,
    title: 'Скидки на зимнюю экипировку',
    slug: 'winter-sale',
    excerpt: 'До конца месяца скидки до 30% на зимнюю экипировку для всех видов спорта.',
    image: '/images/news/winter-sale.jpg',
    published_at: new Date().toISOString(),
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
  },
  {
    id: 3,
    title: 'Открытие нового склада',
    slug: 'new-warehouse',
    excerpt: 'Мы рады сообщить об открытии нового склада в Москве для более быстрой доставки.',
    image: '/images/news/warehouse.jpg',
    published_at: new Date().toISOString(),
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
  },
];

/**
 * Mock данные для категорий (AC 3)
 */
const mockCategories: Category[] = [
  {
    id: 1,
    name: 'Футбол',
    slug: 'football',
    parent_id: null,
    level: 1,
    icon: 'http://localhost/media/categories/icons/football.svg',
    image: '/media/categories/football.jpg',
    products_count: 150,
    description: 'Товары для футбола',
  },
  {
    id: 2,
    name: 'Бег',
    slug: 'running',
    parent_id: null,
    level: 1,
    icon: 'http://localhost/media/categories/icons/running.svg',
    image: '/media/categories/running.jpg',
    products_count: 230,
    description: 'Беговая экипировка',
  },
  {
    id: 3,
    name: 'Теннис',
    slug: 'tennis',
    parent_id: null,
    level: 1,
    icon: null,
    image: null,
    products_count: 95,
    description: 'Теннисное оборудование',
  },
  {
    id: 4,
    name: 'Велоспорт',
    slug: 'cycling',
    parent_id: null,
    level: 1,
    icon: 'http://localhost/media/categories/icons/cycling.svg',
    image: '/media/categories/cycling.jpg',
    products_count: 180,
    description: 'Велосипеды и аксессуары',
  },
  {
    id: 5,
    name: 'Outdoor',
    slug: 'outdoor',
    parent_id: null,
    level: 1,
    icon: 'http://localhost/media/categories/icons/outdoor.svg',
    image: '/media/categories/outdoor.jpg',
    products_count: 320,
    description: 'Товары для активного отдыха',
  },
  {
    id: 6,
    name: 'Баскетбол',
    slug: 'basketball',
    parent_id: null,
    level: 1,
    icon: null,
    image: null,
    products_count: 85,
    description: 'Баскетбольное оборудование',
  },
];

/**
 * Auth Handlers - Story 28.1, 31.2
 * Mock handlers для тестирования аутентификации
 */
export const authHandlers = [
  // Story 31.2: Logout endpoint
  http.post(`${API_BASE_URL}/auth/logout/`, async ({ request }) => {
    const body = (await request.json()) as { refresh?: string };

    // AC 2: Проверка наличия refresh token
    if (!body.refresh) {
      return HttpResponse.json({ error: 'Refresh token is required' }, { status: 400 });
    }

    // Mock: "invalid-refresh-token" считается невалидным
    if (body.refresh === 'invalid-refresh-token') {
      return HttpResponse.json({ error: 'Invalid or expired token' }, { status: 400 });
    }

    if (body.refresh === 'missing-auth') {
      return HttpResponse.json(
        { detail: 'Authentication credentials were not provided.' },
        { status: 401 }
      );
    }

    // AC 3: Успешный logout - 204 No Content
    return new HttpResponse(null, { status: 204 });
  }),

  // Successful login
  http.post(`${API_BASE_URL}/auth/login/`, async ({ request }) => {
    const body = (await request.json()) as { email: string; password: string };

    // Simulate 401 for specific test credentials
    if (body.email === 'wrong@example.com' || body.password === 'WrongPassword') {
      return HttpResponse.json({ detail: 'Invalid credentials' }, { status: 401 });
    }

    return HttpResponse.json({
      access: 'mock-access-token',
      refresh: 'mock-refresh-token',
      user: {
        id: 1,
        email: body.email,
        first_name: 'Test',
        last_name: 'User',
        phone: '',
        role: 'retail' as const,
        is_verified: true,
      },
    });
  }),

  // Successful registration
  http.post(`${API_BASE_URL}/auth/register/`, async ({ request }) => {
    const body = (await request.json()) as { email: string; password: string; first_name: string };

    // Simulate 409 conflict for existing email
    if (body.email === 'existing@example.com') {
      return HttpResponse.json({ email: ['User with this email already exists'] }, { status: 409 });
    }

    // Simulate 400 for weak password
    if (body.password === 'weak') {
      return HttpResponse.json({ password: ['Password is too weak'] }, { status: 400 });
    }

    return HttpResponse.json(
      {
        access: 'mock-access-token',
        refresh: 'mock-refresh-token',
        user: {
          id: 2,
          email: body.email,
          first_name: body.first_name,
          last_name: '',
          phone: '',
          role: 'retail' as const,
          is_verified: false,
        },
      },
      { status: 201 }
    );
  }),

  // Password Reset
  http.post(`${API_BASE_URL}/auth/password-reset/`, async () => {
    return HttpResponse.json({ detail: 'Password reset e-mail has been sent.' });
  }),

  http.post(`${API_BASE_URL}/auth/password-reset/confirm/`, async ({ request }) => {
    const body = (await request.json()) as { token: string; new_password1?: string };
    if (body.token === 'invalid-token') {
      return HttpResponse.json({ detail: 'Invalid token' }, { status: 404 });
    }
    if (body.token === 'expired-token') {
      return HttpResponse.json({ detail: 'Token expired' }, { status: 410 });
    }
    if (body.new_password1 === 'weak') {
      return HttpResponse.json({ new_password: ['Password too weak'] }, { status: 400 });
    }
    return HttpResponse.json({ detail: 'Password has been reset.' });
  }),

  // Token Refresh
  http.post(`${API_BASE_URL}/auth/refresh/`, async ({ request }) => {
    const body = (await request.json()) as { refresh: string };
    if (body.refresh === 'expired-token') {
      return HttpResponse.json({ detail: 'Token expired' }, { status: 401 });
    }
    return HttpResponse.json({ access: 'new-access-token', refresh: 'new-refresh-token' });
  }),
];

// Import handlers from separate files
import { ordersHandlers } from '../handlers/ordersHandlers';
import { deliveryHandlers } from '../handlers/deliveryHandlers';
import { profileHandlers } from '../handlers/profileHandlers';

/**
 * Banners Handlers
 * Story 17.3: Frontend интеграция с API баннеров
 */
const bannersHandlersLocal = [
  // GET /banners/ - Get active banners
  http.get(`${API_BASE_URL}/banners/`, () => {
    return HttpResponse.json([
      {
        id: 1,
        type: 'hero',
        title: 'FREESPORT - Спортивные товары для профессионалов и любителей',
        subtitle: '5 брендов. 1000+ товаров. Доставка по всей России.',
        image_url: '/test-banner.jpg',
        image_alt: 'FREESPORT баннер',
        cta_text: 'Начать покупки',
        cta_link: '/catalog',
      },
    ]);
  }),
];

/**
 * MSW Handlers
 */
export const handlers = [
  ...authHandlers,
  ...ordersHandlers,
  ...deliveryHandlers,
  ...profileHandlers,
  ...bannersHandlersLocal,
  // Хиты продаж (AC 1)
  http.get(`${API_BASE_URL}/products/`, ({ request }) => {
    const url = new URL(request.url);
    const isHit = url.searchParams.get('is_hit');
    const isNew = url.searchParams.get('is_new');
    const search = url.searchParams.get('search');

    // Запрос хитов продаж
    if (isHit === 'true') {
      return HttpResponse.json({
        count: mockHitsProducts.length,
        next: null,
        previous: null,
        results: mockHitsProducts,
      });
    }

    // Запрос новинок (AC 2)
    if (isNew === 'true') {
      return HttpResponse.json({
        count: mockNewProducts.length,
        next: null,
        previous: null,
        results: mockNewProducts,
      });
    }

    // Поисковый запрос
    if (search) {
      // Фильтруем товары по поисковому запросу
      const allProducts = [...mockHitsProducts, ...mockNewProducts];
      const filtered = allProducts.filter(p => p.name.toLowerCase().includes(search.toLowerCase()));
      return HttpResponse.json({
        count: filtered.length,
        next: null,
        previous: null,
        results: filtered,
      });
    }

    // Default: возвращаем тестовый набор для общих запросов
    // Это нужно для тестов, которые вызывают getAll() без параметров
    const defaultProduct = {
      id: 1,
      name: 'Test Product',
      slug: 'test-product',
      description: 'Test Product Description',
      retail_price: 2500,
      discount_percent: null,
    };

    return HttpResponse.json({
      count: 100,
      next: null,
      previous: null,
      results: [defaultProduct],
    });
  }),

  // Категории - корневые категории (AC 3)
  http.get(`${API_BASE_URL}/categories/`, ({ request }) => {
    const url = new URL(request.url);
    const parentIdNull = url.searchParams.get('parent_id__isnull');

    // Только корневые категории
    if (parentIdNull === 'true') {
      return HttpResponse.json({
        count: mockCategories.length,
        next: null,
        previous: null,
        results: mockCategories,
      });
    }

    // Default: все категории (также в формате pagination)
    return HttpResponse.json({
      count: mockCategories.length,
      next: null,
      previous: null,
      results: mockCategories,
    });
  }),

  // Story 11.3: Subscribe endpoint
  http.post(`${API_BASE_URL}/subscribe`, async ({ request }) => {
    const body = (await request.json()) as { email?: string };
    const email = body.email;

    // Simulate already subscribed
    if (email === 'existing@example.com') {
      return HttpResponse.json(
        {
          error: 'This email is already subscribed',
          email,
        },
        { status: 409 }
      );
    }

    // Simulate validation error
    if (!email || !email.includes('@')) {
      return HttpResponse.json(
        {
          error: 'Invalid email format',
          field: 'email',
        },
        { status: 400 }
      );
    }

    // Success
    return HttpResponse.json(
      {
        message: 'Successfully subscribed',
        email,
      },
      { status: 201 }
    );
  }),

  // Story 11.3: News endpoint
  http.get(`${API_BASE_URL}/news`, () => {
    return HttpResponse.json({
      count: mockNews.length,
      next: null,
      previous: null,
      results: mockNews,
    });
  }),

  // Story 12.1: Product Detail endpoint
  // ВАЖНО: Этот хендлер использует :slug параметр, но также обрабатывает numeric ID
  // Тесты могут переопределить через server.use() для специфичных случаев
  http.get(`${API_BASE_URL}/products/:slug/`, ({ params }) => {
    const { slug } = params;

    // Mock для разных состояний товара
    if (slug === 'asics-gel-blast-ff') {
      return HttpResponse.json(MOCK_PRODUCT_DETAIL_API);
    }

    if (slug === 'out-of-stock-product') {
      return HttpResponse.json(MOCK_OUT_OF_STOCK_PRODUCT);
    }

    if (slug === 'unavailable-product') {
      return HttpResponse.json(MOCK_UNAVAILABLE_PRODUCT);
    }

    // Story 13.5a: Product with variants
    if (slug === 'nike-air-max' || slug === 'product-with-variants') {
      return HttpResponse.json(MOCK_PRODUCT_WITH_VARIANTS);
    }

    // Специальный случай для теста 404
    if (slug === 'non-existent-product') {
      return HttpResponse.json({ detail: 'Product not found' }, { status: 404 });
    }

    // Default: возвращаем тестовый товар для любых других ID/slug
    // Это нужно для тестов, которые вызывают getById() с произвольными ID
    const defaultProductDetail = {
      id: typeof slug === 'string' && !isNaN(Number(slug)) ? Number(slug) : 1,
      name: 'Test Product',
      slug: 'test-product',
      description: 'Test Product Description',
      retail_price: 2500,
      is_in_stock: true,
      category: { id: 1, name: 'Test Category', slug: 'test-category' },
      images: [{ id: 1, image: '/test-product.jpg', is_primary: true }],
      is_hit: false,
      is_new: false,
      is_sale: false,
      is_promo: false,
      is_premium: false,
      discount_percent: null,
    };

    return HttpResponse.json(defaultProductDetail);
  }),

  // Story 12.3: Cart API endpoints
  http.get(`${API_BASE_URL}/cart/`, () => {
    return HttpResponse.json({
      id: 1,
      items: [],
      total_amount: 0,
      promo_code: null,
      discount_amount: 0,
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    });
  }),

  http.post(`${API_BASE_URL}/cart/items/`, async ({ request }) => {
    const body = (await request.json()) as { variant_id: number; quantity: number };
    return HttpResponse.json(
      {
        id: Date.now(),
        variant_id: body.variant_id,
        product: {
          id: 1,
          name: 'Test Product',
          slug: 'test-product',
          image: '/test.jpg',
        },
        variant: {
          sku: 'TEST-SKU-001',
          color_name: 'Красный',
          size_value: 'L',
        },
        quantity: body.quantity,
        unit_price: '2500.00',
        total_price: (2500 * body.quantity).toFixed(2),
        added_at: new Date().toISOString(),
      },
      { status: 201 }
    );
  }),

  http.patch(`${API_BASE_URL}/cart/items/:id/`, async ({ params, request }) => {
    const body = (await request.json()) as { quantity: number };
    return HttpResponse.json({
      id: Number(params.id),
      variant_id: 101,
      product: {
        id: 1,
        name: 'Test Product',
        slug: 'test-product',
        image: '/test.jpg',
      },
      variant: {
        sku: 'TEST-SKU-001',
        color_name: 'Красный',
        size_value: 'L',
      },
      quantity: body.quantity,
      unit_price: '2500.00',
      total_price: (2500 * body.quantity).toFixed(2),
      added_at: new Date().toISOString(),
    });
  }),

  http.delete(`${API_BASE_URL}/cart/items/:id/`, () => {
    return new HttpResponse(null, { status: 204 });
  }),

  http.delete(`${API_BASE_URL}/cart/clear/`, () => {
    return new HttpResponse(null, { status: 204 });
  }),

  /**
   * Story 26.4: Promo code handler
   * Тестовые промокоды: SAVE10, SAVE20, FLAT500, EXPIRED, INVALID
   */
  http.post(`${API_BASE_URL}/cart/apply-promo/`, async ({ request }) => {
    const { code, cartTotal } = (await request.json()) as { code: string; cartTotal?: number };

    // Конфигурация тестовых промокодов
    const promos: Record<
      string,
      {
        discount_type: 'percent' | 'fixed';
        discount_value: number;
        min_order?: number;
      }
    > = {
      SAVE10: { discount_type: 'percent', discount_value: 10 },
      SAVE20: { discount_type: 'percent', discount_value: 20, min_order: 5000 },
      FLAT500: { discount_type: 'fixed', discount_value: 500 },
    };

    // Проверка истёкшего промокода
    if (code.toUpperCase() === 'EXPIRED') {
      return HttpResponse.json(
        { success: false, error: 'Срок действия промокода истёк' },
        { status: 400 }
      );
    }

    // Поиск промокода
    const promo = promos[code.toUpperCase()];
    if (!promo) {
      return HttpResponse.json(
        { success: false, error: 'Промокод недействителен' },
        { status: 400 }
      );
    }

    // Проверка минимальной суммы заказа
    if (promo.min_order && cartTotal && cartTotal < promo.min_order) {
      return HttpResponse.json(
        {
          success: false,
          error: `Минимальная сумма заказа для этого промокода: ${promo.min_order}₽`,
        },
        { status: 400 }
      );
    }

    // Успешное применение промокода
    return HttpResponse.json({
      success: true,
      code: code.toUpperCase(),
      discount_type: promo.discount_type,
      discount_value: promo.discount_value,
    });
  }),

  // ============================================================
  // Addresses API (Story 16.3)
  // ============================================================

  // GET /users/addresses/ - список адресов
  http.get(`${API_BASE_URL}/users/addresses/`, () => {
    return HttpResponse.json([
      {
        id: 1,
        address_type: 'shipping',
        full_name: 'Иван Иванов',
        phone: '+79001234567',
        city: 'Москва',
        street: 'Тверская',
        building: '12',
        building_section: '',
        apartment: '45',
        postal_code: '123456',
        is_default: true,
        full_address: '123456, Москва, Тверская 12, кв. 45',
        created_at: '2025-01-01T00:00:00Z',
        updated_at: '2025-01-01T00:00:00Z',
      },
    ]);
  }),

  // POST /users/addresses/ - создать адрес
  http.post(`${API_BASE_URL}/users/addresses/`, async ({ request }) => {
    const body = (await request.json()) as Record<string, unknown>;
    return HttpResponse.json(
      {
        id: Date.now(),
        ...body,
        full_address: `${body.postal_code}, ${body.city}, ${body.street} ${body.building}${body.apartment ? `, кв. ${body.apartment}` : ''}`,
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      },
      { status: 201 }
    );
  }),

  // PATCH /users/addresses/:id/ - обновить адрес
  http.patch(`${API_BASE_URL}/users/addresses/:id/`, async ({ params, request }) => {
    const body = (await request.json()) as Record<string, unknown>;
    return HttpResponse.json({
      id: Number(params.id),
      ...body,
      updated_at: new Date().toISOString(),
    });
  }),

  // DELETE /users/addresses/:id/ - удалить адрес
  http.delete(`${API_BASE_URL}/users/addresses/:id/`, () => {
    return new HttpResponse(null, { status: 204 });
  }),

  // ============================================================
  // Favorites API (Story 16.3)
  // ============================================================

  // GET /users/favorites/ - список избранного
  http.get(`${API_BASE_URL}/users/favorites/`, () => {
    return HttpResponse.json([
      {
        id: 1,
        product: 10,
        product_name: 'Мяч футбольный Nike',
        product_price: '2500.00',
        product_image: '/images/ball.jpg',
        product_slug: 'myach-futbolny-nike',
        product_sku: 'BALL-001',
        created_at: '2025-01-01T00:00:00Z',
      },
    ]);
  }),

  // POST /users/favorites/ - добавить в избранное
  http.post(`${API_BASE_URL}/users/favorites/`, async ({ request }) => {
    const body = (await request.json()) as { product: number };
    return HttpResponse.json(
      {
        id: Date.now(),
        product: body.product,
        product_name: 'Test Product',
        product_price: '2500.00',
        product_image: '/test.jpg',
        product_slug: 'test-product',
        product_sku: 'TEST-001',
        created_at: new Date().toISOString(),
      },
      { status: 201 }
    );
  }),

  // DELETE /users/favorites/:id/ - удалить из избранного
  http.delete(`${API_BASE_URL}/users/favorites/:id/`, () => {
    return new HttpResponse(null, { status: 204 });
  }),

  // ============================================================
  // Auth API
  // ============================================================

  // POST /auth/refresh/ - обновить access token
  http.post(`${API_BASE_URL}/auth/refresh/`, async ({ request }) => {
    const body = (await request.json()) as { refresh: string };

    // Проверяем валидность refresh токена
    if (body.refresh === 'expired-token') {
      return HttpResponse.json({ detail: 'Invalid refresh token' }, { status: 401 });
    }

    // Возвращаем новый access токен
    return HttpResponse.json({
      access: 'new-access-token-' + Date.now(),
    });
  }),
];

/**
 * Error handlers для тестирования error states
 */
export const errorHandlers = [
  // 500 Server Error для хитов
  http.get(`${API_BASE_URL}/products/`, ({ request }) => {
    const url = new URL(request.url);
    const isHit = url.searchParams.get('is_hit');

    if (isHit === 'true') {
      return HttpResponse.json({ detail: 'Internal Server Error' }, { status: 500 });
    }

    return HttpResponse.json({
      count: 0,
      next: null,
      previous: null,
      results: [],
    });
  }),

  // 500 Server Error для категорий
  http.get(`${API_BASE_URL}/categories/`, () => {
    return HttpResponse.json({ detail: 'Internal Server Error' }, { status: 500 });
  }),
];

/**
 * Empty data handlers для тестирования graceful degradation
 */
export const emptyHandlers = [
  // Пустой ответ для хитов
  http.get(`${API_BASE_URL}/products/`, () => {
    return HttpResponse.json({
      count: 0,
      next: null,
      previous: null,
      results: [],
    });
  }),

  // Пустой ответ для категорий
  http.get(`${API_BASE_URL}/categories/`, () => {
    return HttpResponse.json({
      count: 0,
      next: null,
      previous: null,
      results: [],
    });
  }),
];
