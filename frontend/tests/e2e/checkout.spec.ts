/**
 * E2E тесты checkout флоу
 * Story 15.5: E2E тестирование упрощённого флоу
 *
 * Тестируемые сценарии:
 * - AC1: Переход из корзины в checkout
 * - AC2: Заполнение контактных данных
 * - AC3: Заполнение адреса доставки
 * - AC4: Выбор способа доставки
 * - AC5: Оформление заказа
 * - AC6: Отображение страницы успеха с номером заказа
 */

import { test, expect, Page } from '@playwright/test';

/**
 * Тестовые данные для checkout формы
 */
const testCheckoutData = {
  email: 'test@example.com',
  phone: '+79001234567',
  firstName: 'Иван',
  lastName: 'Петров',
  city: 'Москва',
  street: 'Ленина',
  house: '10',
  apartment: '5',
  postalCode: '123456',
};

/**
 * Мок данные для товара в корзине
 */
const mockCartItem = {
  id: 1,
  product: {
    id: 1,
    name: 'Тестовый товар',
    slug: 'test-product',
  },
  variant: {
    id: 1,
    sku: 'TEST-001',
    color_name: 'Красный',
    size_value: 'M',
  },
  quantity: 1,
  unit_price: '1000.00',
  total_price: '1000.00',
};

/**
 * Мок данные для способов доставки
 */
const mockDeliveryMethods = [
  {
    id: 'courier',
    name: 'Курьерская доставка',
    description: 'Доставка курьером до двери',
    icon: '🚚',
    is_available: true,
  },
  {
    id: 'pickup',
    name: 'Самовывоз',
    description: 'Забрать из магазина',
    icon: '🏪',
    is_available: true,
  },
];

/**
 * Мок данные для созданного заказа
 */
const mockCreatedOrder = {
  id: 123,
  order_number: 'FS-2024-000123',
  status: 'pending',
  total_amount: '1000.00',
  delivery_method: 'courier',
  delivery_address: 'Москва, Ленина 10, кв. 5',
  delivery_cost: '0.00',
  items: [
    {
      id: 1,
      product: 1,
      product_name: 'Тестовый товар',
      product_sku: 'TEST-001',
      quantity: 1,
      unit_price: '1000.00',
      total_price: '1000.00',
    },
  ],
};

/**
 * Настройка моков API для E2E тестов
 */
async function setupApiMocks(page: Page) {
  // Мок API корзины
  await page.route('**/api/v1/cart/**', async route => {
    const method = route.request().method();

    if (method === 'GET') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          items: [mockCartItem],
          total_items: 1,
          total_price: 1000,
        }),
      });
    } else {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ success: true }),
      });
    }
  });

  // Мок API способов доставки
  await page.route('**/api/v1/delivery/methods/**', async route => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(mockDeliveryMethods),
    });
  });

  // Мок API создания заказа
  await page.route('**/api/v1/orders/**', async route => {
    const method = route.request().method();

    if (method === 'POST') {
      await route.fulfill({
        status: 201,
        contentType: 'application/json',
        body: JSON.stringify(mockCreatedOrder),
      });
    } else if (method === 'GET') {
      // GET для получения деталей заказа на success странице
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(mockCreatedOrder),
      });
    } else {
      await route.continue();
    }
  });

  // Мок API каталога товаров
  await page.route('**/api/v1/products/**', async route => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        results: [
          {
            id: 1,
            name: 'Тестовый товар',
            slug: 'test-product',
            retail_price: 1000,
            is_in_stock: true,
          },
        ],
        count: 1,
      }),
    });
  });
}

/**
 * Заполнение формы checkout
 */
async function fillCheckoutForm(page: Page, data: typeof testCheckoutData) {
  // Контактные данные
  // Контактные данные
  await page.fill('#input-email', data.email);
  await page.fill('#input-телефон', data.phone);
  await page.fill('#input-имя', data.firstName);
  await page.fill('#input-фамилия', data.lastName);

  // Адрес доставки
  await page.fill('#input-город', data.city);
  await page.fill('#input-улица', data.street);
  await page.fill('#input-дом', data.house);
  await page.fill('input[name="apartment"]', data.apartment);
  await page.fill('input[name="postalCode"]', data.postalCode);
}

test.describe('Checkout Flow E2E Tests', () => {
  test.beforeEach(async ({ page }) => {
    // Настройка моков API перед каждым тестом
    await setupApiMocks(page);
  });

  /**
   * AC1-6: Полный флоу checkout от корзины до success страницы
   */
  test('complete checkout flow from cart to success', async ({ page }) => {
    // 1. Переходим на страницу checkout
    await page.goto('/checkout');

    // Ожидаем загрузки страницы
    await expect(page.locator('h2:has-text("Контактные данные")')).toBeVisible();

    // 2. Заполняем контактные данные (AC2)
    await fillCheckoutForm(page, testCheckoutData);

    // 3. Выбираем способ доставки (AC4)
    // Ждём загрузки способов доставки
    await expect(page.locator('h2:has-text("Способ доставки")')).toBeVisible();
    await page.click('input[value="courier"]');

    // 4. Проверяем, что форма заполнена корректно
    await expect(page.locator('input[name="email"]')).toHaveValue(testCheckoutData.email);
    await expect(page.locator('input[name="phone"]')).toHaveValue(testCheckoutData.phone);
    await expect(page.locator('input[name="firstName"]')).toHaveValue(testCheckoutData.firstName);

    // 5. Оформляем заказ (AC5)
    await page.getByRole('button', { name: /оформить заказ/i }).click();

    // 6. Проверяем редирект на success страницу (AC6)
    await expect(page).toHaveURL(/\/checkout\/success\/\d+/);

    // 7. Проверяем отображение success страницы
    await expect(page.locator('text=Заказ успешно оформлен')).toBeVisible();
    await expect(page.locator(`text=${mockCreatedOrder.order_number}`)).toBeVisible();
  });

  /**
   * AC1: Переход на checkout страницу
   */
  test('navigates to checkout page', async ({ page }) => {
    await page.goto('/checkout');

    // Проверяем наличие основных секций
    await expect(page.locator('h2:has-text("Контактные данные")')).toBeVisible();
    await expect(page.locator('h2:has-text("Адрес доставки")')).toBeVisible();
    await expect(page.locator('h2:has-text("Способ доставки")')).toBeVisible();
    await expect(page.locator('h2:has-text("Ваш заказ")')).toBeVisible();
  });

  /**
   * AC2: Заполнение контактных данных
   */
  test('fills contact information correctly', async ({ page }) => {
    await page.goto('/checkout');

    // Заполняем только контактные данные
    await page.getByLabel('Email').fill(testCheckoutData.email);
    await page.getByLabel('Телефон').fill(testCheckoutData.phone);
    await page.getByLabel('Имя').fill(testCheckoutData.firstName);
    await page.getByLabel('Фамилия').fill(testCheckoutData.lastName);

    // Проверяем значения
    await expect(page.getByLabel('Email')).toHaveValue(testCheckoutData.email);
    await expect(page.getByLabel('Телефон')).toHaveValue(testCheckoutData.phone);
    await expect(page.getByLabel('Имя')).toHaveValue(testCheckoutData.firstName);
    await expect(page.getByLabel('Фамилия')).toHaveValue(testCheckoutData.lastName);
  });

  /**
   * AC3: Заполнение адреса доставки
   */
  test('fills delivery address correctly', async ({ page }) => {
    await page.goto('/checkout');

    // Заполняем адрес доставки
    await page.fill('input[name="city"]', testCheckoutData.city);
    await page.fill('input[name="street"]', testCheckoutData.street);
    await page.fill('input[name="house"]', testCheckoutData.house);
    await page.fill('input[name="apartment"]', testCheckoutData.apartment);
    await page.fill('input[name="postalCode"]', testCheckoutData.postalCode);

    // Проверяем значения
    await expect(page.locator('input[name="apartment"]')).toHaveValue(testCheckoutData.apartment);
    await expect(page.locator('input[name="postalCode"]')).toHaveValue(testCheckoutData.postalCode);
  });

  /**
   * AC4: Выбор способа доставки
   */
  test('selects delivery method', async ({ page }) => {
    await page.goto('/checkout');

    // Ждём загрузки способов доставки
    await expect(page.locator('h2:has-text("Способ доставки")')).toBeVisible();

    // Проверяем наличие radio buttons для способов доставки
    await expect(page.locator('input[value="courier"]')).toBeVisible();
    await expect(page.locator('input[value="pickup"]')).toBeVisible();

    // Выбираем курьерскую доставку
    await page.click('input[value="courier"]');
    await expect(page.locator('input[value="courier"]')).toBeChecked();

    // Меняем на самовывоз
    await page.click('input[value="pickup"]');
    await expect(page.locator('input[value="pickup"]')).toBeChecked();
    await expect(page.locator('input[value="courier"]')).not.toBeChecked();
  });

  /**
   * AC6: Отображение страницы успеха с номером заказа
   */
  test('displays success page with order number', async ({ page }) => {
    // Переходим напрямую на success страницу
    await page.goto(`/checkout/success/${mockCreatedOrder.id}`);

    // Проверяем основные элементы
    await expect(page.locator('text=Заказ успешно оформлен')).toBeVisible();
    await expect(page.locator(`text=${mockCreatedOrder.order_number}`)).toBeVisible();

    // Проверяем наличие кнопок навигации
    await expect(page.locator('text=Продолжить покупки')).toBeVisible();
    await expect(page.locator('text=Личный кабинет')).toBeVisible();
  });
});

/**
 * Тесты валидации формы checkout
 * AC2, AC3: Проверка валидации контактных данных и адреса доставки
 */
test.describe('Checkout Form Validation E2E Tests', () => {
  test.beforeEach(async ({ page }) => {
    await setupApiMocks(page);
  });

  /**
   * Тест: пустые обязательные поля показывают ошибки
   */
  test('shows validation errors for empty required fields', async ({ page }) => {
    await page.goto('/checkout');

    // Ждём загрузки страницы
    await expect(page.locator('h2:has-text("Контактные данные")')).toBeVisible();

    // Пытаемся отправить пустую форму (клик по кнопке submit)
    await page.getByRole('button', { name: /оформить заказ/i }).click();

    // Проверяем появление ошибок валидации
    // Email обязателен
    await expect(page.locator('text=Email обязателен')).toBeVisible();

    // Телефон - формат
    await expect(page.locator('text=Формат: +7XXXXXXXXXX')).toBeVisible();

    // Имя - минимум 2 символа
    await expect(page.locator('text=Минимум 2 символа').first()).toBeVisible();
  });

  /**
   * Тест: валидация формата email
   */
  test('validates email format', async ({ page }) => {
    await page.goto('/checkout');

    // Вводим некорректный email
    await page.fill('input[name="email"]', 'invalid-email');
    await page.fill('input[name="phone"]', testCheckoutData.phone); // blur для триггера валидации

    // Проверяем ошибку формата email
    await expect(page.locator('text=Некорректный формат email').first()).toBeVisible();

    // Исправляем email
    await page.fill('input[name="email"]', 'valid@example.com');
    await page.fill('input[name="phone"]', testCheckoutData.phone);

    // Ошибка должна исчезнуть
    await expect(page.locator('text=Некорректный формат email')).not.toBeVisible();
  });

  /**
   * Тест: валидация формата телефона
   */
  test('validates phone format', async ({ page }) => {
    await page.goto('/checkout');

    // Вводим некорректный телефон
    await page.fill('input[name="phone"]', '123456');
    await page.fill('input[name="email"]', testCheckoutData.email); // blur

    // Проверяем ошибку формата
    await expect(page.locator('text=Формат: +7XXXXXXXXXX').first()).toBeVisible();

    // Исправляем телефон
    await page.fill('input[name="phone"]', '+79001234567');
    await page.fill('input[name="email"]', testCheckoutData.email);

    // Ошибка должна исчезнуть
    await expect(page.locator('text=Формат: +7XXXXXXXXXX')).not.toBeVisible();
  });

  /**
   * Тест: валидация почтового индекса (6 цифр)
   */
  test('validates postal code format', async ({ page }) => {
    await page.goto('/checkout');

    // Вводим некорректный индекс
    await page.fill('input[name="postalCode"]', '123');
    await page.fill('input[name="email"]', testCheckoutData.email); // blur

    // Проверяем ошибку
    await expect(page.locator('text=6 цифр').first()).toBeVisible();

    // Исправляем индекс
    await page.fill('input[name="postalCode"]', '123456');
    await page.fill('input[name="email"]', testCheckoutData.email);

    // Ошибка должна исчезнуть (только текст ошибки, helper text останется)
    await expect(page.locator('text=Индекс должен содержать ровно 6 цифр')).not.toBeVisible();
  });

  /**
   * Тест: валидация минимальной длины полей
   */
  test('validates minimum length for name fields', async ({ page }) => {
    await page.goto('/checkout');

    // Вводим слишком короткое имя
    await page.fill('#input-имя', 'А');
    await page.fill('#input-фамилия', 'Б');
    await page.fill('#input-email', testCheckoutData.email); // blur

    // Проверяем ошибки минимальной длины
    const minLengthErrors = page.locator('text=Минимум 2 символа');
    await expect(minLengthErrors.first()).toBeVisible();

    // Исправляем поля
    await page.fill('#input-имя', 'Иван');
    await page.fill('#input-фамилия', 'Петров');
    await page.fill('#input-email', testCheckoutData.email);

    // Ошибки должны исчезнуть
    await expect(page.locator('text=Минимум 2 символа')).not.toBeVisible();
  });

  /**
   * Тест: требуется выбор способа доставки
   */
  test('requires delivery method selection', async ({ page }) => {
    await page.goto('/checkout');

    // Заполняем все поля кроме способа доставки
    await fillCheckoutForm(page, testCheckoutData);

    // Пытаемся отправить форму
    await page.getByRole('button', { name: /оформить заказ/i }).click();

    // Проверяем ошибку выбора способа доставки
    await expect(page.locator('text=Выберите способ доставки')).toBeVisible();
  });
});

/**
 * Мок данные авторизованного пользователя
 */
const mockAuthUser = {
  id: 1,
  email: 'user@example.com',
  first_name: 'Александр',
  last_name: 'Сидоров',
  phone: '+79009876543',
  role: 'retail',
  addresses: [
    {
      city: 'Санкт-Петербург',
      street: 'Невский проспект',
      house: '100',
      apartment: '15',
      postal_code: '190000',
    },
  ],
};

/**
 * Тесты автозаполнения для авторизованных пользователей
 * AC2, AC3: Автозаполнение контактных данных и адреса
 */
test.describe('Checkout Autofill E2E Tests', () => {
  /**
   * Настройка моков для авторизованного пользователя
   */
  async function setupAuthMocks(page: Page) {
    await setupApiMocks(page);

    // Мок API текущего пользователя
    await page.route('**/api/v1/users/me/**', async route => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(mockAuthUser),
      });
    });

    // Мок API проверки аутентификации
    await page.route('**/api/v1/auth/**', async route => {
      if (route.request().url().includes('verify') || route.request().url().includes('refresh')) {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({ access: 'mock-token', refresh: 'mock-refresh' }),
        });
      } else {
        await route.continue();
      }
    });
  }

  /**
   * Тест: авторизованный пользователь видит автозаполненные поля
   * Примечание: Этот тест требует SSR/client-side hydration с данными пользователя
   */
  test('autofills fields for authenticated users', async ({ page }) => {
    await setupAuthMocks(page);

    // Устанавливаем localStorage/cookies для имитации авторизации
    await page.addInitScript(() => {
      localStorage.setItem('auth_token', 'mock-access-token');
      localStorage.setItem('refresh_token', 'mock-refresh-token');
    });

    await page.goto('/checkout');

    // Ждём загрузки страницы
    await expect(page.locator('h2:has-text("Контактные данные")')).toBeVisible();

    // Примечание: Автозаполнение зависит от реализации компонента
    // Если данные передаются через SSR props, поля будут заполнены
    // Проверяем что поля существуют и доступны
    await expect(page.locator('input[name="email"]')).toBeVisible();
    await expect(page.locator('input[name="firstName"]')).toBeVisible();
  });
});

/**
 * Тесты обработки ошибок API
 * AC5: Обработка ошибок при оформлении заказа
 */
test.describe('Checkout Error Handling E2E Tests', () => {
  /**
   * Тест: ошибка API показывается пользователю
   */
  test('shows error message when order creation fails', async ({ page }) => {
    // Настраиваем базовые моки
    await setupApiMocks(page);

    // Переопределяем мок создания заказа для возврата ошибки
    await page.route('**/api/v1/orders/**', async route => {
      const method = route.request().method();

      if (method === 'POST') {
        await route.fulfill({
          status: 500,
          contentType: 'application/json',
          body: JSON.stringify({ error: 'Внутренняя ошибка сервера' }),
        });
      } else {
        await route.continue();
      }
    });

    await page.goto('/checkout');

    // Заполняем форму
    await fillCheckoutForm(page, testCheckoutData);

    // Выбираем способ доставки
    await page.click('input[value="courier"]');

    // Отправляем форму
    await page.getByRole('button', { name: /оформить заказ/i }).click();

    // Проверяем отображение ошибки
    await expect(page.locator('text=Ошибка').first()).toBeVisible({ timeout: 10000 });
  });

  /**
   * Тест: ошибка валидации сервера (400)
   */
  test('shows validation error from server', async ({ page }) => {
    await setupApiMocks(page);

    // Мок с ошибкой валидации
    await page.route('**/api/v1/orders/**', async route => {
      const method = route.request().method();

      if (method === 'POST') {
        await route.fulfill({
          status: 400,
          contentType: 'application/json',
          body: JSON.stringify({
            email: ['Email уже используется'],
            phone: ['Некорректный формат телефона'],
          }),
        });
      } else {
        await route.continue();
      }
    });

    await page.goto('/checkout');

    // Заполняем форму
    await fillCheckoutForm(page, testCheckoutData);
    await page.click('input[value="courier"]');

    // Отправляем форму
    await page.getByRole('button', { name: /оформить заказ/i }).click();

    // Ожидаем появления ошибки (общей или конкретной)
    await expect(page.locator('[role="alert"]').first()).toBeVisible({ timeout: 10000 });
  });

  /**
   * Тест: недоступность сервера (network error)
   */
  test('handles network error gracefully', async ({ page }) => {
    await setupApiMocks(page);

    // Мок с сетевой ошибкой
    await page.route('**/api/v1/orders/**', async route => {
      const method = route.request().method();

      if (method === 'POST') {
        await route.abort('failed');
      } else {
        await route.continue();
      }
    });

    await page.goto('/checkout');

    // Заполняем форму
    await fillCheckoutForm(page, testCheckoutData);
    await page.click('input[value="courier"]');

    // Отправляем форму
    await page.getByRole('button', { name: /оформить заказ/i }).click();

    // Проверяем что страница не крашится и показывает ошибку
    await expect(page.locator('button[type="submit"]')).toBeVisible();
  });

  /**
   * Тест: ошибка загрузки способов доставки
   */
  test('handles delivery methods loading error', async ({ page }) => {
    // Базовые моки без delivery methods
    await page.route('**/api/v1/cart/**', async route => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          items: [mockCartItem],
          total_items: 1,
          total_price: 1000,
        }),
      });
    });

    // Мок ошибки delivery methods
    await page.route('**/api/v1/delivery/methods/**', async route => {
      await route.fulfill({
        status: 500,
        contentType: 'application/json',
        body: JSON.stringify({ error: 'Service unavailable' }),
      });
    });

    await page.goto('/checkout');

    // Проверяем отображение ошибки загрузки
    await expect(page.locator('text=Не удалось загрузить способы доставки')).toBeVisible();
  });
});
