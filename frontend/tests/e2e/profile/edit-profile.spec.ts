/**
 * E2E Tests for Profile Page
 * Story 16.1 - AC: 2, 3, 4, 5
 *
 * Тестирует критический флоу:
 * - Авторизация → переход в профиль → редактирование → сохранение
 */

import { test, expect } from '@playwright/test';

/**
 * Тестовые данные пользователя
 */
const TEST_USER = {
  email: 'test@example.com',
  password: 'testpassword123',
  firstName: 'Test',
  lastName: 'User',
  phone: '+79001234567',
};

const TEST_B2B_USER = {
  email: 'b2b@example.com',
  password: 'testpassword123',
  firstName: 'B2B',
  lastName: 'User',
  phone: '+79009876543',
  companyName: 'Test Company LLC',
  taxId: '1234567890',
};

test.describe('Profile Page - Edit Profile Flow', () => {
  test.describe('Authentication & Access', () => {
    test('redirects unauthenticated users to login page', async ({ page }) => {
      // ACT
      await page.goto('/profile');

      // ASSERT
      const url = new URL(page.url());
      expect(url.pathname).toBe('/login');
      expect(url.searchParams.get('next')).toBe('/profile');
    });

    test('allows authenticated users to access profile page', async ({ page }) => {
      // ARRANGE - установим cookie для имитации авторизации
      await page.context().addCookies([
        {
          name: 'refreshToken',
          value: 'mock-refresh-token',
          domain: 'localhost',
          path: '/',
        },
      ]);

      // ACT
      await page.goto('/profile');

      // ASSERT
      await expect(page).toHaveURL(/\/profile/);
      await expect(page.locator('h1')).toContainText('Профиль');
    });
  });

  test.describe('Profile Form Display', () => {
    test.beforeEach(async ({ page }) => {
      // Установка auth cookies
      await page.context().addCookies([
        {
          name: 'refreshToken',
          value: 'mock-refresh-token',
          domain: 'localhost',
          path: '/',
        },
      ]);

      // Mock API для получения профиля
      await page.route('**/api/v1/users/profile/', async route => {
        if (route.request().method() === 'GET') {
          await route.fulfill({
            status: 200,
            contentType: 'application/json',
            body: JSON.stringify({
              id: 1,
              email: TEST_USER.email,
              first_name: TEST_USER.firstName,
              last_name: TEST_USER.lastName,
              phone: TEST_USER.phone,
              role: 'retail',
              is_verified: true,
              company_name: null,
              tax_id: null,
            }),
          });
        }
      });
    });

    test('displays current user data in form fields', async ({ page }) => {
      // ACT
      await page.goto('/profile');

      // ASSERT - ожидаем загрузки данных
      await expect(page.locator('input[id="email"]')).toHaveValue(TEST_USER.email);
      await expect(page.locator('input[id="first_name"]')).toHaveValue(TEST_USER.firstName);
      await expect(page.locator('input[id="last_name"]')).toHaveValue(TEST_USER.lastName);
      await expect(page.locator('input[id="phone"]')).toHaveValue(TEST_USER.phone);
    });

    test('email field is readonly', async ({ page }) => {
      // ACT
      await page.goto('/profile');

      // ASSERT
      await expect(page.locator('input[id="email"]')).toBeDisabled();
    });
  });

  test.describe('Profile Form Editing', () => {
    test.beforeEach(async ({ page }) => {
      await page.context().addCookies([
        {
          name: 'refreshToken',
          value: 'mock-refresh-token',
          domain: 'localhost',
          path: '/',
        },
      ]);

      // Mock GET profile
      await page.route('**/api/v1/users/profile/', async route => {
        if (route.request().method() === 'GET') {
          await route.fulfill({
            status: 200,
            contentType: 'application/json',
            body: JSON.stringify({
              id: 1,
              email: TEST_USER.email,
              first_name: TEST_USER.firstName,
              last_name: TEST_USER.lastName,
              phone: TEST_USER.phone,
              role: 'retail',
              is_verified: true,
            }),
          });
        } else if (route.request().method() === 'PUT') {
          const body = route.request().postDataJSON();
          await route.fulfill({
            status: 200,
            contentType: 'application/json',
            body: JSON.stringify({
              id: 1,
              email: TEST_USER.email,
              first_name: body.first_name || TEST_USER.firstName,
              last_name: body.last_name || TEST_USER.lastName,
              phone: body.phone || TEST_USER.phone,
              role: 'retail',
              is_verified: true,
            }),
          });
        }
      });
    });

    test('successfully updates profile and shows toast notification', async ({ page }) => {
      // ARRANGE
      await page.goto('/profile');
      await expect(page.locator('input[id="first_name"]')).toHaveValue(TEST_USER.firstName);

      // ACT - изменяем имя
      await page.locator('input[id="first_name"]').fill('UpdatedName');
      await page.click('button[type="submit"]');

      // ASSERT - проверяем toast уведомление
      await expect(page.locator('text=Профиль успешно обновлён')).toBeVisible();
    });

    test('shows validation error for invalid phone format', async ({ page }) => {
      // ARRANGE
      await page.goto('/profile');

      // ACT - вводим невалидный телефон
      await page.locator('input[id="phone"]').fill('123');
      await page.click('button[type="submit"]');

      // ASSERT
      await expect(page.locator('text=Телефон должен быть в формате')).toBeVisible();
    });
  });

  test.describe('B2B User Fields', () => {
    test('displays B2B fields for wholesale users', async ({ page }) => {
      // ARRANGE
      await page.context().addCookies([
        {
          name: 'refreshToken',
          value: 'mock-refresh-token',
          domain: 'localhost',
          path: '/',
        },
      ]);

      // Mock B2B user profile
      await page.route('**/api/v1/users/profile/', async route => {
        if (route.request().method() === 'GET') {
          await route.fulfill({
            status: 200,
            contentType: 'application/json',
            body: JSON.stringify({
              id: 1,
              email: TEST_B2B_USER.email,
              first_name: TEST_B2B_USER.firstName,
              last_name: TEST_B2B_USER.lastName,
              phone: TEST_B2B_USER.phone,
              role: 'wholesale_level1',
              is_verified: true,
              company_name: TEST_B2B_USER.companyName,
              tax_id: TEST_B2B_USER.taxId,
            }),
          });
        }
      });

      // ACT
      await page.goto('/profile');

      // ASSERT - B2B поля должны быть видимы
      await expect(page.locator('text=Данные компании')).toBeVisible();
      await expect(page.locator('input[id="company_name"]')).toHaveValue(TEST_B2B_USER.companyName);
      await expect(page.locator('input[id="tax_id"]')).toHaveValue(TEST_B2B_USER.taxId);
    });

    test('shows verification badge for B2B users', async ({ page }) => {
      // ARRANGE
      await page.context().addCookies([
        {
          name: 'refreshToken',
          value: 'mock-refresh-token',
          domain: 'localhost',
          path: '/',
        },
      ]);

      await page.route('**/api/v1/users/profile/', async route => {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            id: 1,
            email: TEST_B2B_USER.email,
            first_name: TEST_B2B_USER.firstName,
            last_name: TEST_B2B_USER.lastName,
            phone: TEST_B2B_USER.phone,
            role: 'wholesale_level1',
            is_verified: true,
            company_name: TEST_B2B_USER.companyName,
            tax_id: TEST_B2B_USER.taxId,
          }),
        });
      });

      // ACT
      await page.goto('/profile');

      // ASSERT - должен быть бейдж верификации
      await expect(page.locator('text=Верифицирован')).toBeVisible();
    });
  });

  test.describe('Navigation', () => {
    test.beforeEach(async ({ page }) => {
      await page.context().addCookies([
        {
          name: 'refreshToken',
          value: 'mock-refresh-token',
          domain: 'localhost',
          path: '/',
        },
      ]);

      await page.route('**/api/v1/users/profile/', async route => {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            id: 1,
            email: TEST_USER.email,
            first_name: TEST_USER.firstName,
            last_name: TEST_USER.lastName,
            phone: TEST_USER.phone,
            role: 'retail',
            is_verified: true,
          }),
        });
      });
    });

    test('displays sidebar navigation on desktop', async ({ page }) => {
      // ARRANGE - установка viewport для desktop
      await page.setViewportSize({ width: 1440, height: 900 });

      // ACT
      await page.goto('/profile');

      // ASSERT
      await expect(page.locator('text=Личный кабинет')).toBeVisible();
      await expect(page.locator('aside a[href="/profile"]')).toBeVisible();
      await expect(page.locator('aside a[href="/profile/orders"]')).toBeVisible();
      await expect(page.locator('aside a[href="/profile/addresses"]')).toBeVisible();
      await expect(page.locator('aside a[href="/profile/favorites"]')).toBeVisible();
    });

    test('displays tab navigation on mobile', async ({ page }) => {
      // ARRANGE - установка viewport для mobile
      await page.setViewportSize({ width: 375, height: 667 });

      // ACT
      await page.goto('/profile');

      // ASSERT - навигационные табы должны быть видимы (на mobile используются табы вместо sidebar)
      // Проверяем наличие ссылок профиля в любой навигации
      await expect(page.locator('a[href="/profile"]').first()).toBeVisible();
    });
  });
});
