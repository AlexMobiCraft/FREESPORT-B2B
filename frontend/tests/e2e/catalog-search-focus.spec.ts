/**
 * E2E: переход из шапки к поиску каталога (Story 41.17, AC3)
 *
 * Юнит-тесты проверяют только document.activeElement. Здесь проверяется то,
 * что видит посетитель: поле в фокусе и не спрятано под sticky-шапкой после
 * прокрутки Next.js к фрагменту #search.
 */

import { test, expect, type Page } from '@playwright/test';

const SEARCH_PLACEHOLDER = 'Поиск в каталоге...';

/** Поле в фокусе, и точка в его центре не перекрыта другим элементом (шапкой). */
async function expectSearchFocusedAndVisible(page: Page) {
  const input = page.getByPlaceholder(SEARCH_PLACEHOLDER);
  await expect(input).toBeFocused();
  await expect(page).toHaveURL(/\/catalog#search$/);

  const coveredBy = await input.evaluate(element => {
    const rect = element.getBoundingClientRect();
    const hit = document.elementFromPoint(rect.left + rect.width / 2, rect.top + rect.height / 2);
    return hit && (hit === element || element.contains(hit)) ? null : (hit?.tagName ?? 'offscreen');
  });
  expect(coveredBy).toBeNull();
}

/**
 * В CI e2e идут без backend. Сценарию нужна только разметка шапки и каталога,
 * поэтому все запросы к API получают пустые ответы.
 */
async function mockEmptyApi(page: Page) {
  await page.route('**/api/v1/**', async route => {
    const url = route.request().url();
    // /banners/ и /categories-tree/ отдают голый массив, а не пагинированный объект:
    // HeroSection берёт banners[index] — пагинация там уронила бы страницу.
    const isArrayEndpoint = url.includes('/banners/') || url.includes('/categories-tree/');
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(
        isArrayEndpoint ? [] : { count: 0, next: null, previous: null, results: [] }
      ),
    });
  });
}

test.describe('Поиск из шапки — фокус в поле каталога', () => {
  test.beforeEach(async ({ page }) => {
    await mockEmptyApi(page);
  });

  test('с главной страницы', async ({ page }) => {
    await page.goto('/home');
    await page.locator('header').getByRole('link', { name: 'Поиск' }).first().click();

    await expectSearchFocusedAndVisible(page);
  });

  test('повторный клик, когда каталог уже открыт', async ({ page }) => {
    await page.goto('/catalog');
    await expect(page.getByPlaceholder(SEARCH_PLACEHOLDER)).toBeVisible();
    await page.mouse.wheel(0, 1200);

    await page.locator('header').getByRole('link', { name: 'Поиск' }).first().click();

    await expectSearchFocusedAndVisible(page);
  });

  test('из мобильного меню', async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto('/home');
    await page.getByRole('button', { name: 'Открыть меню' }).click();
    await page.locator('header').getByRole('link', { name: 'Поиск' }).last().click();

    await expectSearchFocusedAndVisible(page);
  });
});
