/**
 * E2E тесты Search History Flow
 * Story 18.3: История и автодополнение поиска
 *
 * Тестируемые сценарии:
 * - AC1: История хранится в localStorage (последние 10 запросов)
 * - AC2: При фокусе на пустом поле показывается история
 * - AC3: Клик по истории → выполняется поиск
 * - AC4: Кнопка очистки истории
 * - AC5: История сохраняется между сессиями
 */

import { test, expect, Page } from '@playwright/test';

/**
 * Ключ localStorage для истории поиска
 */
const STORAGE_KEY = 'search_history';

/**
 * Тестовые поисковые запросы
 */
const testSearchQueries = ['кроссовки', 'мяч', 'футболка', 'шорты', 'гантели'];

/**
 * Мок данные для результатов поиска
 */
const mockSearchResults = {
  results: [
    {
      id: 1,
      name: 'Кроссовки для бега Nike',
      slug: 'krossovki-nike',
      retail_price: 7990,
      is_in_stock: true,
    },
    {
      id: 2,
      name: 'Мяч футбольный Adidas',
      slug: 'myach-adidas',
      retail_price: 2990,
      is_in_stock: true,
    },
  ],
  count: 2,
};

/**
 * Настройка моков API для E2E тестов
 */
async function setupApiMocks(page: Page) {
  // Мок API поиска товаров
  await page.route('**/api/v1/products/**', async route => {
    const url = route.request().url();

    if (url.includes('search') || url.includes('q=')) {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(mockSearchResults),
      });
    } else {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ results: [], count: 0 }),
      });
    }
  });

  // Мок API категорий (для главной страницы)
  await page.route('**/api/v1/categories/**', async route => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify([]),
    });
  });

  // Мок баннеров
  await page.route('**/api/v1/banners/**', async route => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify([]),
    });
  });
}

/**
 * Инициализация localStorage с историей поиска
 */
async function initSearchHistory(page: Page, queries: string[]) {
  await page.addInitScript(
    ({ key, data }) => {
      localStorage.setItem(key, JSON.stringify(data));
    },
    { key: STORAGE_KEY, data: queries }
  );
}

/**
 * Получение истории поиска из localStorage
 */
async function getSearchHistory(page: Page): Promise<string[]> {
  return page.evaluate(key => {
    const stored = localStorage.getItem(key);
    return stored ? JSON.parse(stored) : [];
  }, STORAGE_KEY);
}

test.describe('Search History Flow E2E Tests', () => {
  test.beforeEach(async ({ page }) => {
    await setupApiMocks(page);
  });

  /**
   * AC1: История хранится в localStorage
   */
  test('stores search queries in localStorage', async ({ page }) => {
    await page.goto('/catalog');

    // Находим поле поиска в header
    const searchField = page.locator('[data-testid="search-field"]').first();
    await expect(searchField).toBeVisible();

    // Вводим поисковый запрос
    await searchField.fill('кроссовки');

    // Ждём debounce и нажимаем Enter
    await page.waitForTimeout(400);
    await searchField.press('Enter');

    // Проверяем, что запрос сохранён в localStorage
    const history = await getSearchHistory(page);
    expect(history).toContain('кроссовки');
  });

  /**
   * AC1: Лимит 10 запросов в истории
   */
  test('limits history to 10 items', async ({ page }) => {
    // Инициализируем историю с 10 записями
    const initialHistory = [
      'запрос1',
      'запрос2',
      'запрос3',
      'запрос4',
      'запрос5',
      'запрос6',
      'запрос7',
      'запрос8',
      'запрос9',
      'запрос10',
    ];
    await initSearchHistory(page, initialHistory);

    await page.goto('/catalog');

    const searchField = page.locator('[data-testid="search-field"]').first();
    await expect(searchField).toBeVisible();

    // Добавляем новый запрос
    await searchField.fill('новый запрос');
    await page.waitForTimeout(400);
    await searchField.press('Enter');

    // Проверяем, что история содержит макс 10 элементов
    const history = await getSearchHistory(page);
    expect(history.length).toBeLessThanOrEqual(10);
    expect(history[0]).toBe('новый запрос');
  });

  /**
   * AC2: При фокусе на пустом поле показывается история
   */
  test('shows search history on focus with empty field', async ({ page }) => {
    // Инициализируем историю
    await initSearchHistory(page, testSearchQueries.slice(0, 3));

    await page.goto('/catalog');

    const searchField = page.locator('[data-testid="search-field"]').first();
    await expect(searchField).toBeVisible();

    await searchField.locator('input').focus();

    // Ждём появления истории
    await expect(page.locator('[data-testid="search-history"]')).toBeVisible({ timeout: 5000 });

    // Проверяем наличие элементов истории
    await expect(page.locator('text=кроссовки')).toBeVisible();
    await expect(page.locator('text=мяч')).toBeVisible();
  });

  /**
   * AC2: История скрывается при вводе текста
   */
  test('hides history when typing', async ({ page }) => {
    await initSearchHistory(page, testSearchQueries.slice(0, 3));

    await page.goto('/catalog');

    const searchField = page.locator('[data-testid="search-field"]').first();
    await searchField.locator('input').focus();

    // Ждём появления истории
    await expect(page.locator('[data-testid="search-history"]')).toBeVisible({ timeout: 5000 });

    // Начинаем вводить текст
    await searchField.fill('ку');

    // История должна скрыться
    await expect(page.locator('[data-testid="search-history"]')).not.toBeVisible({ timeout: 3000 });
  });

  /**
   * AC3: Клик по истории выполняет поиск
   */
  test('clicking history item performs search', async ({ page }) => {
    await initSearchHistory(page, ['кроссовки', 'мяч']);

    await page.goto('/catalog');

    const searchField = page.locator('[data-testid="search-field"]').first();
    await searchField.locator('input').focus();

    // Ждём появления истории
    await expect(page.locator('[data-testid="search-history"]')).toBeVisible({ timeout: 5000 });

    // Кликаем по элементу истории
    await page
      .locator('[data-testid="search-history"] button:has-text("кроссовки")')
      .first()
      .click();

    // Проверяем редирект на страницу поиска
    await expect(page).toHaveURL(/\/search\?q=кроссовки/);
  });

  /**
   * AC4: Удаление отдельного элемента истории
   */
  test('removes individual history item', async ({ page }) => {
    await initSearchHistory(page, ['кроссовки', 'мяч', 'футболка']);

    await page.goto('/catalog');

    const searchField = page.locator('[data-testid="search-field"]').first();
    await searchField.locator('input').focus();

    // Ждём появления истории
    await expect(page.locator('[data-testid="search-history"]')).toBeVisible({ timeout: 5000 });

    // Находим и кликаем кнопку удаления для "мяч"
    const historyItem = page
      .locator('[data-testid="search-history"] [role="option"]')
      .filter({ hasText: 'мяч' });
    await historyItem.locator('[aria-label*="Удалить"]').click();

    // Проверяем, что элемент удалён из localStorage
    const history = await getSearchHistory(page);
    expect(history).not.toContain('мяч');
    expect(history).toContain('кроссовки');
    expect(history).toContain('футболка');
  });

  /**
   * AC4: Очистка всей истории
   */
  test('clears all search history', async ({ page }) => {
    await initSearchHistory(page, testSearchQueries);

    await page.goto('/catalog');

    const searchField = page.locator('[data-testid="search-field"]').first();
    await searchField.locator('input').focus();

    // Ждём появления истории
    await expect(page.locator('[data-testid="search-history"]')).toBeVisible({ timeout: 5000 });

    // Находим и кликаем кнопку очистки истории
    const clearButton = page.locator('[data-testid="search-history"] button:has-text("Очистить")');
    await clearButton.click();

    // Кликаем "Подтвердить" если есть диалог подтверждения
    const confirmButton = page.locator('text=Подтвердить');
    if (await confirmButton.isVisible({ timeout: 1000 }).catch(() => false)) {
      await confirmButton.click();
    }

    // Проверяем, что история очищена
    const history = await getSearchHistory(page);
    expect(history.length).toBe(0);
  });

  /**
   * AC5: История сохраняется между сессиями
   */
  test('persists history between sessions', async ({ page }) => {
    await page.goto('/catalog');

    const searchField = page.locator('[data-testid="search-field"]').first();
    await expect(searchField).toBeVisible();

    // Добавляем запрос в историю
    await searchField.fill('тренажёр');
    await page.waitForTimeout(400);
    await searchField.press('Enter');

    // Проверяем, что URL изменился
    const url = new URL(page.url());
    expect(url.pathname).toBe('/search');
    expect(url.searchParams.get('q')).toBe('тренажёр');

    // "Перезагружаем" страницу (симуляция новой сессии)
    await page.goto('/catalog');

    // Фокусируемся на поле поиска
    const searchFieldNew = page.locator('[data-testid="search-field"] input').first();
    await searchFieldNew.focus();

    // Проверяем, что история сохранилась
    await expect(page.locator('[data-testid="search-history"]')).toBeVisible({ timeout: 5000 });
    await expect(page.locator('text=тренажёр')).toBeVisible();
  });

  /**
   * Дубликаты перемещаются в начало истории
   */
  test('moves duplicate queries to top of history', async ({ page }) => {
    await initSearchHistory(page, ['мяч', 'кроссовки', 'футболка']);

    await page.goto('/catalog');

    const searchField = page.locator('[data-testid="search-field"]').first();
    await expect(searchField).toBeVisible();

    // Ищем запрос, который уже есть в истории
    await searchField.fill('футболка');
    await page.waitForTimeout(400);
    await searchField.press('Enter');

    // Проверяем, что "футболка" теперь первая в истории
    const history = await getSearchHistory(page);
    expect(history[0]).toBe('футболка');
    // И что она не дублируется
    expect(history.filter(q => q === 'футболка').length).toBe(1);
  });
});

/**
 * Accessibility Tests
 */
test.describe('Search History Accessibility Tests', () => {
  test.beforeEach(async ({ page }) => {
    await setupApiMocks(page);
    await initSearchHistory(page, ['кроссовки', 'мяч']);
  });

  /**
   * История имеет корректные ARIA атрибуты
   */
  test('has correct ARIA attributes', async ({ page }) => {
    await page.goto('/catalog');

    const searchField = page.locator('[data-testid="search-field"]').first();
    await expect(searchField).toBeVisible();
    await searchField.locator('input').focus();

    // Ждём появления истории
    await expect(page.locator('[data-testid="search-history"]')).toBeVisible({ timeout: 5000 });

    // Проверяем role="listbox" на контейнере
    await expect(page.locator('[data-testid="search-history"] [role="listbox"]')).toBeVisible();

    // Проверяем role="option" на элементах
    const options = page.locator('[data-testid="search-history"] [role="option"]');
    expect(await options.count()).toBeGreaterThan(0);
  });

  /**
   * Кнопки имеют aria-label
   */
  test('buttons have aria-labels', async ({ page }) => {
    await page.goto('/catalog');

    const searchField = page.locator('[data-testid="search-field"]').first();
    await searchField.locator('input').focus();

    await expect(page.locator('[data-testid="search-history"]')).toBeVisible({ timeout: 5000 });

    // Проверяем aria-label на кнопках удаления
    const deleteButtons = page.locator(
      '[data-testid="search-history"] button[aria-label*="Удалить"]'
    );
    expect(await deleteButtons.count()).toBeGreaterThan(0);

    // Проверяем кнопку очистки
    await expect(page.locator('[aria-label*="Очистить"]')).toBeVisible();
  });

  /**
   * Escape закрывает историю
   */
  test('Escape key closes history dropdown', async ({ page }) => {
    await page.goto('/catalog');

    const searchField = page.locator('[data-testid="search-field"]').first();
    await searchField.locator('input').focus();

    await expect(page.locator('[data-testid="search-history"]')).toBeVisible({ timeout: 5000 });

    // Нажимаем Escape
    await searchField.press('Escape');

    // История должна скрыться
    await expect(page.locator('[data-testid="search-history"]')).not.toBeVisible({ timeout: 3000 });
  });
});
