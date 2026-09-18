# Модели данных (Data Models)

Этот документ описывает структуру базы данных платформы FREESPORT, включая ключевые поля, связи и бизнес-логику моделей.

## 👥 Пользователи и Роли (`apps.users`)

### User

Основная модель пользователя (расширение `AbstractUser`).

- **email**: Unique ID (вместо username).
- **role**: Роль пользователя (`retail`, `wholesale_level1-3`, `trainer`, `federation_rep`, `admin`).
- **verification_status**: Статус верификации B2B (`unverified`, `verified`, `pending`).
- **onec_id**: Привязка к контрагенту в 1С.
- **customer_code**: Пятизначный код клиента для схемы нумерации заказов и интеграционных сценариев.

### Company

Реквизиты юридического лица (для B2B).

- Связь 1:1 с `User`.
- Поля: ИНН, КПП, ОГРН, банковские реквизиты.

### Address

Адреса доставки.

- Связь M:1 с `User`.
- Поле `is_default` с логикой автоматического сброса старого адреса по умолчанию.

---

## 📦 Каталог товаров (`apps.products`)

### Product

Базовое описание товара.

- **base_images**: JSON-список URL изображений из 1С (fallback).
- **specifications**: JSONB-поле для технических характеристик.
- **vat_rate**: Ставка НДС базового товара из `goods.xml`. Используется как fallback для `ProductVariant.vat_rate`, если ставка пришла отдельно от `offers.xml`.
- **Маркетинговые флаги**: `is_hit`, `is_new`, `is_sale`, `is_promo`, `is_premium`.

### ProductVariant (SKU)

Конкретный вариант товара. Это единица учета в корзине и заказах.

- **sku**: Уникальный артикул.
- **Цены (6 типов)**: `retail_price`, `opt1-3_price`, `trainer_price`, `federation_price`.
- **Остатки**: `stock_quantity`, `reserved_quantity`.
- **Характеристики**: `color_name`, `size_value`.
- **vat_rate**: Основной каталожный источник НДС для создания заказа и fallback при экспорте.
- **warehouse_id / warehouse_name**: GUID и имя склада из 1С; используются для split заказов и выбора склада в CommerceML.

### Category & Brand

- **Category**: Иерархическая структура (Self-referencing FK).
- **Brand**: Дедупликация через `normalized_name` и маппинг `Brand1CMapping`.

---

## 🛒 Корзина и Заказы (`apps.cart`, `apps.orders`)

### Cart & CartItem

- **Cart**: Привязка к `User` или `session_key` (для гостей).
- **CartItem**: Хранит `price_snapshot` — цену в момент добавления товара.
- **Checkout-ограничение**: Гостевая корзина поддерживается для browsing/cart flow, но создание заказа через `/orders/` доступно только авторизованному пользователю с валидным `customer_code`.

### Order

Заказ пользователя.

- **order_number**: Канонический immutable-номер. Для master-заказа формат `CCCCCYYNNN`, для sub-order — `CCCCCYYNNNS`.
- **customer_code_snapshot / order_year / customer_year_sequence / suborder_sequence**: Снимки, поддерживающие атомарную генерацию, аудит и поиск.
- **total_amount**: Сумма (товары + доставка - скидки).
- **Статусы**: `pending`, `confirmed`, `processing`, `shipped`, `delivered`, `cancelled`.
- **Платежи**: Интеграция с ЮKassa через `payment_id`.
- **parent_order / is_master / vat_group**: Структура `master-order` + технические `sub-orders` для экспорта в 1С. `sub-order` группируется по `(vat_rate, warehouse_name)`, а `vat_group` является авторитетной ставкой документа CommerceML.
- **order_number_display**: Производное UI-представление номера. Для master используется формат `CCCC-YYNNN`, для sub-order — `CCCCC-YYNNN-S`.

### OrderItem

Снимок (Snapshot) купленного товара.

- Копирует `product_name`, `product_sku` и `unit_price` из `ProductVariant` в момент создания заказа. Это гарантирует неизменность истории заказов.
- **vat_rate**: Snapshot ставки НДС на момент заказа. Последующие изменения `Product` или `ProductVariant` не меняют уже созданную позицию.

---

## ⚙️ Интеграция (`apps.integrations`)

### ImportSession

Логирование обмена с 1С.

- Хранит тип импорта, статус, `celery_task_id` и детальный JSON-отчет о результатах обработки.
