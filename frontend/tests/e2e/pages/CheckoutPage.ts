/**
 * Page Object Model для страницы Checkout
 * Story 15.5: E2E тестирование упрощённого флоу
 *
 * Инкапсулирует взаимодействие с элементами страницы checkout
 * для улучшения читаемости и переиспользования тестов.
 */

import { Page, Locator, expect } from '@playwright/test';

/**
 * Интерфейс контактных данных
 */
export interface ContactInfo {
  email: string;
  phone: string;
  firstName: string;
  lastName: string;
}

/**
 * Интерфейс адреса доставки
 */
export interface DeliveryAddress {
  city: string;
  street: string;
  house: string;
  apartment?: string;
  postalCode: string;
}

/**
 * Полные данные формы checkout
 */
export interface CheckoutFormData extends ContactInfo, DeliveryAddress {
  deliveryMethod?: string;
  comment?: string;
}

/**
 * Page Object для страницы Checkout
 */
export class CheckoutPage {
  readonly page: Page;

  // Локаторы секций
  readonly contactSection: Locator;
  readonly addressSection: Locator;
  readonly deliverySection: Locator;
  readonly orderSummary: Locator;

  // Локаторы полей контактных данных
  readonly emailInput: Locator;
  readonly phoneInput: Locator;
  readonly firstNameInput: Locator;
  readonly lastNameInput: Locator;

  // Локаторы полей адреса
  readonly cityInput: Locator;
  readonly streetInput: Locator;
  readonly houseInput: Locator;
  readonly apartmentInput: Locator;
  readonly postalCodeInput: Locator;

  // Локаторы кнопок
  readonly submitButton: Locator;

  constructor(page: Page) {
    this.page = page;

    // Секции
    this.contactSection = page.locator('section:has(h2:has-text("Контактные данные"))');
    this.addressSection = page.locator('section:has(h2:has-text("Адрес доставки"))');
    this.deliverySection = page.locator('section:has(h2:has-text("Способ доставки"))');
    this.orderSummary = page.locator('div:has(h2:has-text("Ваш заказ"))');

    // Поля контактных данных
    this.emailInput = page.locator('input[name="email"]');
    this.phoneInput = page.locator('input[name="phone"]');
    this.firstNameInput = page.locator('input[name="firstName"]');
    this.lastNameInput = page.locator('input[name="lastName"]');

    // Поля адреса
    this.cityInput = page.locator('input[name="city"]');
    this.streetInput = page.locator('input[name="street"]');
    this.houseInput = page.locator('input[name="house"]');
    this.apartmentInput = page.locator('input[name="apartment"]');
    this.postalCodeInput = page.locator('input[name="postalCode"]');

    // Кнопки
    this.submitButton = page.locator('button[type="submit"]:has-text("Оформить заказ")');
  }

  /**
   * Навигация на страницу checkout
   */
  async goto() {
    await this.page.goto('/checkout');
    await this.waitForPageLoad();
  }

  /**
   * Ожидание загрузки страницы
   */
  async waitForPageLoad() {
    await expect(this.contactSection).toBeVisible();
    await expect(this.addressSection).toBeVisible();
  }

  /**
   * Заполнение контактных данных
   */
  async fillContactInfo(data: ContactInfo) {
    await this.emailInput.fill(data.email);
    await this.phoneInput.fill(data.phone);
    await this.firstNameInput.fill(data.firstName);
    await this.lastNameInput.fill(data.lastName);
  }

  /**
   * Заполнение адреса доставки
   */
  async fillAddress(data: DeliveryAddress) {
    await this.cityInput.fill(data.city);
    await this.streetInput.fill(data.street);
    await this.houseInput.fill(data.house);
    if (data.apartment) {
      await this.apartmentInput.fill(data.apartment);
    }
    await this.postalCodeInput.fill(data.postalCode);
  }

  /**
   * Выбор способа доставки
   */
  async selectDeliveryMethod(methodId: string) {
    await this.page.click(`input[value="${methodId}"]`);
  }

  /**
   * Заполнение всей формы
   */
  async fillForm(data: CheckoutFormData) {
    await this.fillContactInfo({
      email: data.email,
      phone: data.phone,
      firstName: data.firstName,
      lastName: data.lastName,
    });

    await this.fillAddress({
      city: data.city,
      street: data.street,
      house: data.house,
      apartment: data.apartment,
      postalCode: data.postalCode,
    });

    if (data.deliveryMethod) {
      await this.selectDeliveryMethod(data.deliveryMethod);
    }
  }

  /**
   * Отправка формы
   */
  async submitOrder() {
    await this.submitButton.click();
  }

  /**
   * Полный флоу оформления заказа
   */
  async completeCheckout(data: CheckoutFormData) {
    await this.fillForm(data);
    await this.submitOrder();
  }

  /**
   * Проверка наличия ошибки валидации
   */
  async hasValidationError(errorText: string): Promise<boolean> {
    return await this.page.locator(`text=${errorText}`).isVisible();
  }

  /**
   * Ожидание редиректа на success страницу
   */
  async waitForSuccessPage() {
    await expect(this.page).toHaveURL(/\/checkout\/success\/\d+/);
  }

  /**
   * Проверка значения поля email
   */
  async getEmailValue(): Promise<string> {
    return await this.emailInput.inputValue();
  }

  /**
   * Проверка значения поля firstName
   */
  async getFirstNameValue(): Promise<string> {
    return await this.firstNameInput.inputValue();
  }

  /**
   * Проверка что способ доставки выбран
   */
  async isDeliveryMethodSelected(methodId: string): Promise<boolean> {
    return await this.page.locator(`input[value="${methodId}"]`).isChecked();
  }
}

/**
 * Page Object для страницы Success
 */
export class SuccessPage {
  readonly page: Page;

  readonly successIcon: Locator;
  readonly orderNumber: Locator;
  readonly continueShoppingButton: Locator;
  readonly profileButton: Locator;

  constructor(page: Page) {
    this.page = page;

    this.successIcon = page.locator('.bg-green-100');
    this.orderNumber = page.locator('text=FS-');
    this.continueShoppingButton = page.locator('text=Продолжить покупки');
    this.profileButton = page.locator('text=Личный кабинет');
  }

  /**
   * Навигация на страницу success по ID заказа
   */
  async goto(orderId: number | string) {
    await this.page.goto(`/checkout/success/${orderId}`);
  }

  /**
   * Проверка успешного оформления заказа
   */
  async verifySuccess() {
    await expect(this.page.locator('text=Заказ успешно оформлен')).toBeVisible();
  }

  /**
   * Получение номера заказа
   */
  async getOrderNumber(): Promise<string | null> {
    const text = await this.orderNumber.textContent();
    return text;
  }
}
