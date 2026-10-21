/**
 * E2E Tests - Favorites Management
 * Story 16.3: Управление избранными товарами (AC: 4, 5, 6, 7)
 */

import { test, expect } from '@playwright/test';

test.describe('Favorites Management', () => {
  // Skip if not authenticated
  test.beforeEach(async ({ page }) => {
    // Navigate to favorites page
    await page.goto('/profile/favorites');

    // Check if redirected to login
    if (page.url().includes('/login')) {
      test.skip(true, 'User not authenticated');
    }
  });

  test('displays favorites page with title (AC: 4)', async ({ page }) => {
    // ASSERT
    await expect(page.locator('h1')).toContainText('Избранное');
  });

  test('shows empty state when no favorites exist', async ({ page }) => {
    // ASSERT - check for empty state OR existing favorites
    const emptyState = page.locator('text=Избранное пусто');
    const favoriteCards = page.locator('[data-testid="favorite-card"]');

    // One of these should be visible
    await expect(emptyState.or(favoriteCards.first())).toBeVisible();
  });

  test('displays product information in favorite card (AC: 4)', async ({ page }) => {
    const favoriteCard = page.locator('[data-testid="favorite-card"]').first();

    // Skip if no favorites
    if (!(await favoriteCard.isVisible())) {
      test.skip(true, 'No favorites to display');
    }

    // ASSERT - card should have product info
    await expect(favoriteCard.locator('h3')).toBeVisible(); // Product name
    await expect(favoriteCard.locator('text=Артикул:')).toBeVisible(); // SKU
  });

  test('shows "В корзину" button for available products (AC: 5)', async ({ page }) => {
    const favoriteCard = page.locator('[data-testid="favorite-card"]').first();

    // Skip if no favorites
    if (!(await favoriteCard.isVisible())) {
      test.skip(true, 'No favorites');
    }

    // Check if product is available (no out-of-stock badge)
    const outOfStockBadge = favoriteCard.locator('[data-testid="out-of-stock-badge"]');

    if (!(await outOfStockBadge.isVisible())) {
      // Product is available - should have "В корзину" button
      await expect(favoriteCard.locator('button:has-text("В корзину")')).toBeVisible();
    }
  });

  test('adds product to cart when "В корзину" is clicked (AC: 5)', async ({ page }) => {
    const favoriteCard = page.locator('[data-testid="favorite-card"]').first();

    // Skip if no favorites
    if (!(await favoriteCard.isVisible())) {
      test.skip(true, 'No favorites');
    }

    // Skip if product is out of stock
    const outOfStockBadge = favoriteCard.locator('[data-testid="out-of-stock-badge"]');
    if (await outOfStockBadge.isVisible()) {
      test.skip(true, 'Product out of stock');
    }

    // ACT
    await favoriteCard.locator('button:has-text("В корзину")').click();

    // ASSERT - toast notification should appear
    await expect(page.locator('text=Товар добавлен в корзину')).toBeVisible({ timeout: 5000 });
  });

  test('removes product from favorites (AC: 6)', async ({ page }) => {
    const favoriteCard = page.locator('[data-testid="favorite-card"]').first();

    // Skip if no favorites
    if (!(await favoriteCard.isVisible())) {
      test.skip(true, 'No favorites to remove');
    }

    const initialCount = await page.locator('[data-testid="favorite-card"]').count();

    // ACT - click heart button to remove
    await favoriteCard.locator('button[aria-label="Удалить из избранного"]').click();

    // ASSERT - favorite should be removed
    await expect(page.locator('[data-testid="favorite-card"]')).toHaveCount(initialCount - 1);
    await expect(page.locator('text=Удалено из избранного')).toBeVisible({ timeout: 5000 });
  });

  test('shows out of stock badge for unavailable products (AC: 7)', async ({ page }) => {
    // This test checks if badge is displayed correctly when product is unavailable
    const outOfStockBadge = page.locator('[data-testid="out-of-stock-badge"]').first();

    // If there's at least one out-of-stock product
    if (await outOfStockBadge.isVisible()) {
      // ASSERT
      await expect(outOfStockBadge).toContainText('Нет в наличии');

      // The card with this badge should have disabled add to cart
      const parentCard = page.locator('[data-testid="favorite-card"]').filter({
        has: outOfStockBadge,
      });

      const notifyButton = parentCard.locator('button:has-text("Сообщить о поступлении")');
      if (await notifyButton.isVisible()) {
        await expect(notifyButton).toBeDisabled();
      }
    }
  });

  test('navigates to product page when clicking on product', async ({ page }) => {
    const favoriteCard = page.locator('[data-testid="favorite-card"]').first();

    // Skip if no favorites
    if (!(await favoriteCard.isVisible())) {
      test.skip(true, 'No favorites');
    }

    // ACT - click on product name/image link
    const productLink = favoriteCard.locator('a').first();
    const href = await productLink.getAttribute('href');
    await productLink.click();

    // ASSERT - should navigate to product page
    await expect(page).toHaveURL(new RegExp(href || '/product/'));
  });

  test('shows catalog link in empty state', async ({ page }) => {
    const emptyState = page.locator('text=Избранное пусто');

    // If empty state is visible
    if (await emptyState.isVisible()) {
      // ASSERT
      await expect(page.locator('a:has-text("Перейти в каталог")')).toBeVisible();
    }
  });
});
