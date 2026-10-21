/**
 * E2E Tests - Address Management
 * Story 16.3: Управление адресами доставки (AC: 1, 2, 3)
 */

import { test, expect } from '@playwright/test';

// Test data
const testAddress = {
  full_name: 'Тест Пользователь',
  phone: '+79001234567',
  city: 'Москва',
  street: 'Тестовая улица',
  building: '1',
  apartment: '10',
  postal_code: '123456',
};

test.describe('Address Management', () => {
  // Skip if not authenticated
  test.beforeEach(async ({ page }) => {
    // Navigate to addresses page (middleware will redirect to login if not authenticated)
    await page.goto('/profile/addresses');

    // Check if redirected to login
    if (page.url().includes('/login')) {
      test.skip(true, 'User not authenticated');
    }
  });

  test('displays addresses page with title', async ({ page }) => {
    // ASSERT
    await expect(page.locator('h1')).toContainText('Адреса доставки');
  });

  test('shows empty state when no addresses exist', async ({ page }) => {
    // This test assumes no addresses exist for test user
    // ASSERT - check for empty state OR existing addresses
    const emptyState = page.locator('text=Нет сохранённых адресов');
    const addressCards = page.locator('[data-testid="address-card"]');

    // One of these should be visible
    await expect(emptyState.or(addressCards.first())).toBeVisible();
  });

  test('opens modal when "Добавить адрес" button is clicked (AC: 1)', async ({ page }) => {
    // ARRANGE
    const addButton = page.locator('button:has-text("Добавить адрес")');

    // ACT
    await addButton.click();

    // ASSERT
    await expect(page.locator('[role="dialog"]')).toBeVisible();
    await expect(page.locator('text=Новый адрес')).toBeVisible();
  });

  test('validates form fields in address modal', async ({ page }) => {
    // ARRANGE
    const addButton = page.locator('button:has-text("Добавить адрес")');
    await addButton.click();

    // ACT - try to submit empty form
    const submitButton = page.locator('[role="dialog"] button:has-text("Добавить")');
    await submitButton.click();

    // ASSERT - validation errors should appear
    await expect(page.locator('text=Имя должно содержать минимум 2 символа')).toBeVisible();
  });

  test('creates new address with valid data (AC: 1)', async ({ page }) => {
    // ARRANGE
    const addButton = page.locator('button:has-text("Добавить адрес")');
    await addButton.click();

    // ACT - fill form
    await page.fill('[name="full_name"]', testAddress.full_name);
    await page.fill('[name="phone"]', testAddress.phone);
    await page.fill('[name="city"]', testAddress.city);
    await page.fill('[name="street"]', testAddress.street);
    await page.fill('[name="building"]', testAddress.building);
    await page.fill('[name="apartment"]', testAddress.apartment);
    await page.fill('[name="postal_code"]', testAddress.postal_code);

    // Submit
    const submitButton = page.locator('[role="dialog"] button:has-text("Добавить")');
    await submitButton.click();

    // ASSERT
    // Modal should close and address should appear in list
    await expect(page.locator('[role="dialog"]')).not.toBeVisible({ timeout: 5000 });
    await expect(
      page.locator('[data-testid="address-card"]').filter({ hasText: testAddress.full_name })
    ).toBeVisible();
  });

  test('edits existing address (AC: 2)', async ({ page }) => {
    // ARRANGE - need at least one address
    const addressCard = page.locator('[data-testid="address-card"]').first();

    // Skip if no addresses
    if (!(await addressCard.isVisible())) {
      test.skip(true, 'No addresses to edit');
    }

    // ACT
    await addressCard.locator('button:has-text("Редактировать")').click();

    // ASSERT - modal opens in edit mode
    await expect(page.locator('[role="dialog"]')).toBeVisible();
    await expect(page.locator('text=Редактировать адрес')).toBeVisible();

    // Change city
    await page.fill('[name="city"]', 'Екатеринбург');
    await page.locator('[role="dialog"] button:has-text("Сохранить")').click();

    // Modal should close
    await expect(page.locator('[role="dialog"]')).not.toBeVisible({ timeout: 5000 });
  });

  test('deletes address with confirmation (AC: 3)', async ({ page }) => {
    // ARRANGE - need at least one address
    const addressCard = page.locator('[data-testid="address-card"]').first();

    // Skip if no addresses
    if (!(await addressCard.isVisible())) {
      test.skip(true, 'No addresses to delete');
    }

    const initialCount = await page.locator('[data-testid="address-card"]').count();

    // ACT
    await addressCard.locator('button:has-text("Удалить")').click();

    // Confirmation dialog should appear
    await expect(page.locator('text=Удалить адрес?')).toBeVisible();

    // Confirm deletion
    await page.locator('button:has-text("Удалить")').last().click();

    // ASSERT - address should be removed
    await expect(page.locator('[data-testid="address-card"]')).toHaveCount(initialCount - 1);
  });

  test('closes modal on cancel', async ({ page }) => {
    // ARRANGE
    const addButton = page.locator('button:has-text("Добавить адрес")');
    await addButton.click();

    // ACT
    await page.locator('[role="dialog"] button:has-text("Отмена")').click();

    // ASSERT
    await expect(page.locator('[role="dialog"]')).not.toBeVisible();
  });

  test('closes modal on ESC key', async ({ page }) => {
    // ARRANGE
    const addButton = page.locator('button:has-text("Добавить адрес")');
    await addButton.click();
    await expect(page.locator('[role="dialog"]')).toBeVisible();

    // ACT
    await page.keyboard.press('Escape');

    // ASSERT
    await expect(page.locator('[role="dialog"]')).not.toBeVisible();
  });
});
