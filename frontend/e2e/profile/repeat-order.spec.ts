/**
 * E2E Test: Repeat Order Flow
 * Story 16.2 - AC: 7
 *
 * ВАЖНО: Тесты используют API mocking через route interception
 * для стабильных и детерминированных результатов
 */

import { test, expect, type Page, type Route } from '@playwright/test';

const BASE_URL = process.env.PLAYWRIGHT_BASE_URL || 'http://localhost:3000';

/**
 * Мок данные для заказов
 */
const MOCK_ORDER = {
  id: 1,
  order_number: 'ORD-2025-0001',
  user: 1,
  customer_display_name: 'Тестовый Пользователь',
  customer_name: 'Тестовый Пользователь',
  customer_email: 'test@example.com',
  customer_phone: '+7 999 123-45-67',
  status: 'delivered',
  total_amount: '5000.00',
  discount_amount: '0.00',
  delivery_cost: '500.00',
  delivery_address: 'г. Москва, ул. Тестовая, д. 1',
  delivery_method: 'courier',
  delivery_date: null,
  tracking_number: '',
  payment_method: 'card',
  payment_status: 'paid',
  payment_id: '',
  notes: '',
  created_at: '2025-01-15T10:00:00Z',
  updated_at: '2025-01-15T12:00:00Z',
  subtotal: '4500.00',
  total_items: 2,
  calculated_total: '5000.00',
  can_be_cancelled: false,
  items: [
    {
      id: 1,
      product: 101,
      variant: {
        id: 201,
        sku: 'SKU-001',
        color_name: 'Красный',
        size_value: 'XL',
        is_active: true,
      },
      product_name: 'Футболка спортивная',
      product_sku: 'SKU-001',
      variant_info: 'Размер: XL, Цвет: Красный',
      quantity: 2,
      unit_price: '1500.00',
      total_price: '3000.00',
    },
    {
      id: 2,
      product: 102,
      variant: { id: 202, sku: 'SKU-002', color_name: null, size_value: 'M', is_active: true },
      product_name: 'Шорты беговые',
      product_sku: 'SKU-002',
      variant_info: 'Размер: M',
      quantity: 1,
      unit_price: '1500.00',
      total_price: '1500.00',
    },
  ],
};

const MOCK_ORDERS_LIST = {
  count: 1,
  next: null,
  previous: null,
  results: [MOCK_ORDER],
};

const MOCK_CART_ITEM = {
  id: 1,
  variant_id: 201,
  product: { id: 101, name: 'Футболка спортивная', slug: 'futbolka', image: null },
  variant: { sku: 'SKU-001', color_name: 'Красный', size_value: 'XL' },
  quantity: 2,
  unit_price: '1500.00',
  total_price: '3000.00',
  added_at: new Date().toISOString(),
};

/**
 * Настройка API моков для стабильных тестов
 */
async function setupApiMocks(page: Page) {
  // Мок списка заказов
  await page.route('**/api/v1/orders/', async (route: Route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(MOCK_ORDERS_LIST),
    });
  });

  // Мок детального заказа
  await page.route('**/api/v1/orders/1/', async (route: Route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(MOCK_ORDER),
    });
  });

  // Мок добавления в корзину
  await page.route('**/api/v1/cart/items/', async (route: Route) => {
    if (route.request().method() === 'POST') {
      await route.fulfill({
        status: 201,
        contentType: 'application/json',
        body: JSON.stringify(MOCK_CART_ITEM),
      });
    } else {
      await route.continue();
    }
  });

  // Мок получения корзины
  await page.route('**/api/v1/cart/', async (route: Route) => {
    if (route.request().method() === 'GET') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ items: [MOCK_CART_ITEM] }),
      });
    } else {
      await route.continue();
    }
  });

  // Мок 404 для несуществующего заказа
  await page.route('**/api/v1/orders/999999/', async (route: Route) => {
    await route.fulfill({
      status: 404,
      contentType: 'application/json',
      body: JSON.stringify({ detail: 'Not found.' }),
    });
  });

  // Мок профиля пользователя
  await page.route('**/api/v1/users/me/', async (route: Route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        id: 1,
        email: 'test@example.com',
        first_name: 'Тест',
        last_name: 'Пользователь',
        role: 'retail',
        is_b2b_user: false,
      }),
    });
  });
}

/**
 * Хелпер для авторизации пользователя
 */
async function loginUser(page: Page) {
  await page.evaluate(() => {
    localStorage.setItem('refreshToken', 'mock-refresh-token');
  });

  await page.context().addCookies([
    {
      name: 'refreshToken',
      value: 'mock-refresh-token',
      domain: 'localhost',
      path: '/',
    },
  ]);
}

test.describe('Repeat Order Flow', () => {
  test.beforeEach(async ({ page }) => {
    await setupApiMocks(page);
    await page.goto(BASE_URL);
    await loginUser(page);
  });

  test('should navigate to orders page and display orders list', async ({ page }) => {
    await page.goto(`${BASE_URL}/profile/orders`);
    await expect(page.getByRole('heading', { name: /мои заказы/i })).toBeVisible();
    // Строгая проверка: должен отображаться хотя бы один заказ
    await expect(page.getByText('ORD-2025-0001')).toBeVisible();
  });

  test('should filter orders by status', async ({ page }) => {
    await page.goto(`${BASE_URL}/profile/orders`);
    const filterButton = page.getByRole('button', { name: /доставлен/i });
    await expect(filterButton).toBeVisible();
    await filterButton.click();
    await expect(page).toHaveURL(/status=delivered/);
  });

  test('should navigate to order detail page from list', async ({ page }) => {
    await page.goto(`${BASE_URL}/profile/orders`);

    // Строгая проверка: карточка заказа должна быть видима
    const orderCard = page.locator('a[href="/profile/orders/1"]');
    await expect(orderCard).toBeVisible();

    await orderCard.click();

    // Строгие проверки на странице детального просмотра
    await expect(page.getByText(/заказ.*ORD-2025-0001/i)).toBeVisible();
    await expect(page.getByRole('button', { name: /повторить заказ/i })).toBeVisible();
  });

  test('should show repeat order button on order detail page', async ({ page }) => {
    await page.goto(`${BASE_URL}/profile/orders/1`);

    const repeatButton = page.getByRole('button', { name: /повторить заказ/i });
    await expect(repeatButton).toBeVisible();
    await expect(repeatButton).toBeEnabled();
  });

  test('should add items to cart when repeat order is clicked and show toast', async ({ page }) => {
    await page.goto(`${BASE_URL}/profile/orders/1`);

    // Ждём загрузки страницы
    await expect(page.getByText('Футболка спортивная')).toBeVisible();

    // Кликаем "Повторить заказ"
    const repeatButton = page.getByRole('button', { name: /повторить заказ/i });
    await repeatButton.click();

    // Строгая проверка: toast должен появиться с сообщением об успехе
    const toast = page.locator('[role="status"], [aria-live="polite"], [data-sonner-toast]');
    await expect(toast.first()).toBeVisible({ timeout: 5000 });

    // Проверяем текст toast (успех или частичный успех)
    await expect(page.getByText(/добавлен|в корзину|товар/i).first()).toBeVisible({
      timeout: 5000,
    });
  });

  test('should display order items with variant info in detail view', async ({ page }) => {
    await page.goto(`${BASE_URL}/profile/orders/1`);

    // Строгие проверки наличия товаров
    await expect(page.getByText('Футболка спортивная')).toBeVisible();
    await expect(page.getByText('Шорты беговые')).toBeVisible();

    // Проверка информации о варианте
    await expect(page.getByText(/Размер.*XL/i)).toBeVisible();
  });

  test('should show correct order status badge', async ({ page }) => {
    await page.goto(`${BASE_URL}/profile/orders/1`);

    // Строгая проверка статуса (заказ delivered)
    const statusBadge = page.getByText(/доставлен/i);
    await expect(statusBadge).toBeVisible();
  });

  test('should display order total amount', async ({ page }) => {
    await page.goto(`${BASE_URL}/profile/orders/1`);

    // Проверка суммы заказа
    await expect(page.getByText(/5.*000/)).toBeVisible();
  });
});

test.describe('Repeat Order - Edge Cases', () => {
  test.beforeEach(async ({ page }) => {
    await setupApiMocks(page);
    await page.goto(BASE_URL);
    await loginUser(page);
  });

  test('should handle order not found (404)', async ({ page }) => {
    await page.goto(`${BASE_URL}/profile/orders/999999`);

    // Строгая проверка: должно быть сообщение об ошибке
    const errorMessage = page.getByText(/не найден|ошибка|not found/i);
    await expect(errorMessage).toBeVisible({ timeout: 5000 });
  });

  test('should navigate back to orders list from detail page', async ({ page }) => {
    await page.goto(`${BASE_URL}/profile/orders/1`);

    // Ждём загрузки страницы
    await expect(page.getByText('ORD-2025-0001')).toBeVisible();

    // Находим ссылку для возврата
    const backLink = page.getByRole('link', { name: /вернуться|назад|список/i });
    await expect(backLink).toBeVisible();
    await backLink.click();

    await expect(page).toHaveURL(`${BASE_URL}/profile/orders`);
  });
});
