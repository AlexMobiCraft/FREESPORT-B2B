# ProductVariant System - Brownfield Enhancement PRD

**Version:** 1.0
**Date:** 2025-11-30
**Author:** John (PM)
**Status:** Draft

---

## 1. Intro Project Analysis and Context

### 1.1 Analysis Source

**Source:** IDE-based fresh analysis + existing project documentation

**Available Documentation:**
- ✅ [docs/PRD.md](../PRD.md) — основной Product Requirements Document
- ✅ [docs/architecture.md](../architecture.md) — архитектурная документация (v4, sharded)
- ✅ [docs/architecture/20-1c-integration.md](../architecture/20-1c-integration.md) — интеграция с 1С
- ✅ [docs/architecture/product-variant-proposal.md](../architecture/product-variant-proposal.md) — предложение от PO
- ✅ [CLAUDE.md](../../CLAUDE.md) — руководство для разработки
- ✅ [docs/stories/epic-12/12.2.product-options.md](../stories/epic-12/12.2.product-options.md) — Story 12.2 (блокирована)

### 1.2 Current Project State

**FREESPORT Platform** — API-First E-commerce платформа для B2B/B2C продаж спортивных товаров с интеграцией 1С.

**Current Functionality:**
- ✅ **12 завершённых Epic** (Epic 1-12)
- ✅ Backend API: Django 5.2.7 + DRF + PostgreSQL 15+
- ✅ Frontend: Next.js 15.4.6 + React 19 + TypeScript
- ✅ Интеграция с 1С: двусторонний обмен данными (товары, клиенты, заказы)
- ✅ Роле-ориентированное ценообразование: 7 ролей пользователей
- ✅ Каталог товаров, корзина, оформление заказа
- ✅ Личный кабинет пользователя

**Current Architecture Problem:**
- Каждый SKU из 1С импортируется как **отдельный Product**
- Отсутствует группировка вариантов товара (цвет, размер)
- Невозможна реализация UX "выбор опций" (Story 12.2 блокирована)

### 1.3 Enhancement Scope Definition

**Enhancement Type:**
- ☑️ New Feature Addition (модель ProductVariant)
- ☑️ Major Feature Modification (рефакторинг Product)
- ☑️ Integration with New Systems (обновление импорта 1С)

**Impact Assessment:**
- ☑️ Major Impact (architectural changes required)

**Enhancement Description:**

Разработка модели `ProductVariant` для хранения SKU-вариантов товаров (цвет, размер, цены, остатки). Текущая модель `Product` рефакторится в базовую информацию о товаре, а специфичные для варианта данные (цены, stock, изображения) переносятся в `ProductVariant`. Это обеспечит корректную группировку товаров на фронтенде и разблокирует Story 12.2.

### 1.4 Goals and Background Context

**Goals:**
- Разблокировать Story 12.2 (Выбор опций товара) для реализации UX выбора цвета/размера
- Обеспечить корректное соответствие архитектуры данных структуре CommerceML 3.1 из 1С
- Устранить дублирование базовой информации о товарах (описание, бренд, категория)
- Создать фундамент для точного учёта остатков и цен по каждому SKU-варианту
- Подготовить систему к масштабированию каталога с тысячами вариантов товаров

**Background Context:**

Сейчас каждое `<Предложение>` из offers.xml (1С) создаёт отдельный объект `Product` со всей базовой информацией. Например, кроссовки Nike Air Max в 5 цветах и 10 размерах создают 50 записей Product с дублированием названия, описания, бренда. Это блокирует UX-сценарий "карточка товара с выбором опций", который требуется в Story 12.2 для Epic 12 (Детализированная страница товара).

Модель `ProductVariant` решает проблему: один `Product` (базовый товар) имеет несколько `ProductVariant` (SKU), каждый с уникальными характеристиками (color, size, prices, stock). Это соответствует архитектуре 1С и разблокирует frontend-компонент `ProductOptions`.

### 1.5 Change Log

| Change | Date | Version | Description | Author |
|--------|------|---------|-------------|--------|
| Initial creation | 2025-11-30 | 1.0 | Создание Brownfield PRD для ProductVariant на основе product-variant-proposal.md | John (PM) |

---

## 2. Requirements

### 2.1 Functional Requirements

- **FR1:** Система должна поддерживать модель `ProductVariant` для хранения SKU-вариантов товара с полями: sku, onec_id, color_name, size_value, retail_price, opt1-3_price, trainer_price, federation_price, stock_quantity, reserved_quantity, main_image (опционально), gallery_images (опционально). **Hybrid подход к изображениям:** `ProductVariant` может иметь собственные изображения (main_image, gallery_images), если они специфичны для варианта (например, разные цвета). Если изображения отсутствуют, используется fallback на `Product.base_images` через computed property `effective_images`

- **FR2:** Модель `Product` должна быть рефакторирована в базовый товар, содержащий только общие поля: name, slug, brand, category, description, short_description, specifications, seo-поля, **base_images** (общие изображения из 1С), без цен и остатков

- **FR3:** Каждый `Product` должен иметь related field `variants` (ForeignKey в ProductVariant), позволяющий получить все SKU-варианты товара через `product.variants.all()`

- **FR4:** Импорт из 1С (CommerceML 3.1) должен создавать один `Product` из `<Товар>` в goods.xml и множество `ProductVariant` из `<Предложение>` в offers.xml с корректным маппингом parent_id#variant_id

- **FR4a:** Импорт из 1С должен обрабатывать некорректные данные: пропускать `<Предложение>` без parent товара с логированием warning, игнорировать дубли SKU, создавать ProductVariant с пустыми color_name/size_value если характеристики отсутствуют

- **FR5:** API endpoint `/products/{slug}/` должен возвращать `ProductDetail` с вложенным массивом `variants[]`, содержащим все SKU-варианты с их ценами, остатками и изображениями

- **FR6:** Модель `ColorMapping` должна обеспечивать маппинг текстовых названий цветов из 1С на hex-коды для frontend-отображения. **MVP подход:** предзаполнить 20 базовых цветов (белый, черный, красный, синий, зелёный, жёлтый, серый, розовый, оранжевый, фиолетовый, коричневый, бежевый, бордовый, голубой, салатовый, сиреневый, тёмно-синий, тёмно-серый, светло-серый, золотой), для остальных использовать fallback на текстовое название

- **FR7:** Система должна поддерживать миграцию существующих данных через очистку таблиц products/product_images и полный реимпорт из 1С с новой структурой моделей

- **FR8:** ProductVariant должен иметь computed properties `is_in_stock` (stock_quantity > 0) и `available_quantity` (stock - reserved) аналогично текущей модели Product

- **FR9:** ProductVariant должен поддерживать метод `get_price_for_user(user)` для получения роле-ориентированной цены в зависимости от типа пользователя

- **FR10:** Frontend компонент `ProductOptions` (Story 12.2) должен получать данные о вариантах из поля `product.variants[]` и отображать селекторы размеров/цветов с индикацией доступности

- **FR10a:** Товары без вариантов (single SKU) должны автоматически создавать один ProductVariant при импорте для унификации API response, чтобы `product.variants[]` всегда был непустым массивом

### 2.2 Non-Functional Requirements

- **NFR1:** Время отклика API `/products/{slug}/` с вложенными variants не должно превышать 500ms для товаров с до 100 вариантами при использовании `prefetch_related('variants')`

- **NFR2:** База данных должна использовать индексы на поля `ProductVariant.sku`, `ProductVariant.onec_id`, `ProductVariant.product_id`, `ProductVariant.is_active` для оптимизации запросов фильтрации

- **NFR3:** Миграция должна включать pre-migration backup БД с документированной процедурой rollback (restore from backup) в случае критических ошибок. **Backward compatibility на уровне Django migrations не требуется**, так как проект находится на этапе разработки с тестовыми данными (production еще не запущен). Backup выполняется через `pg_dump` перед запуском миграции. **Quality Gate:** обязательное тестирование rollback процедуры на staging перед production deployment (Story 13.4 AC6)

- **NFR4:** Импорт из 1С должен обрабатывать до 10,000 SKU-вариантов за один запуск без превышения лимита памяти Django (batch processing по 500 записей)

- **NFR5:** OpenAPI спецификация (`docs/api-spec.yaml`) должна быть обновлена с новой схемой `ProductVariantSchema` и изменениями в `ProductDetailSchema.variants[]`

- **NFR6:** Все новые модели и методы должны иметь полную типизацию Python (type hints) с проверкой через mypy без ошибок

- **NFR7:** Покрытие кода тестами для новых моделей и API endpoints должно быть >= 90% (unit + integration тесты с использованием Factory Boy)

- **NFR8:** Система должна логировать все ошибки при импорте вариантов из 1С (отсутствие цвета/размера, некорректный onec_id, missing parent товар) в отдельный лог-файл для аудита

- **NFR9:** Документация должна включать: обновлённую OpenAPI спецификацию, migration guide для dev team, admin guide по заполнению ColorMapping

### 2.3 Compatibility Requirements

- **CR1:** Существующие API endpoints для списка товаров `/products/` и категорий `/categories/` не должны изменять свою схему ответа, только `/products/{slug}/` расширяется полем `variants[]`

- **CR2:** Миграция базы данных должна сохранять структуру таблиц `orders`, `order_items`, `cart_items` без изменений на этапе внедрения ProductVariant (изменения корзины/заказов — отдельный Epic, планируется после завершения Epic 13)

- **CR3:** Frontend дизайн-система (Chip, цветовая палитра, типографика из [front-end-spec.md](../front-end-spec.md)) должна использоваться без изменений для компонента ProductOptions

- **CR4:** Интеграция с 1С должна оставаться совместимой с CommerceML 3.1 (goods.xml, offers.xml, prices.xml, rests.xml) без изменений протокола обмена

---

## 3. User Interface Enhancement Goals

### 3.1 Integration with Existing UI

**Дизайн-система проекта:**

Все UI компоненты должны следовать единой дизайн-системе из [front-end-spec.md](../front-end-spec.md):

- **Компонент Chip** для селекторов размеров и цветов
- **Цветовая палитра:** Primary (#004DFF), Neutral, Success/Error/Warning
- **Типографика:** Open Sans (текст), Montserrat (заголовки)
- **Spacing:** 4px grid system (8px, 16px, 24px, 32px)

**Интеграция ProductOptions:**

1. **Chip компонент:**
   - Default: `bg-neutral-100`, `border-neutral-400`
   - Selected: `bg-primary`, `text-inverse`
   - Disabled: `opacity: 0.5`, `cursor: not-allowed`

2. **Цветовые индикаторы:** круглый индикатор 16px с border 2px

3. **Layout:** размещение внутри ProductSummary с responsive breakpoints

### 3.2 Modified/New Screens and Views

**Modified Screens:**

1. **Страница товара (`/catalog/[category]/[slug]`):**
   - Обновлен компонент `ProductSummary` с интегрированным `ProductOptions`

**Component Structure:**

```jsx
<ProductGallery />
<ProductSummary>
  <ProductOptions />  ← Внутри ProductSummary
  <Price />
  <AddToCartButton />
</ProductSummary>
```

**New Components:**

2. **`ProductOptions` (новый):**
   - Location: `frontend/src/components/product/ProductOptions.tsx`
   - Подкомпоненты: `SizeSelector`, `ColorSelector`
   - **Расположение:** Внутри `ProductSummary` для логичной группировки опций + цена + кнопка покупки

3. **`ProductSummary` (обновление):**
   - Интегрирует `ProductOptions` как дочерний компонент
   - Prop `selectedVariant: ProductVariant | null`
   - Валидация опций перед добавлением в корзину
   - Управление состоянием `selectedOptions` и синхронизация с ProductGallery

### 3.3 UI Consistency Requirements

1. **Spacing:** 24px между группами, 8px между Chip, 32px отступ от gallery
2. **Typography:** Montserrat 600 14px (заголовки групп), Open Sans 400 14px (лейблы)
3. **Interaction:** Hover → border-color: primary, Active → scale(0.95)
4. **Accessibility:** role="radio", aria-checked, aria-disabled, keyboard navigation
5. **Error states:** красная обводка + error text (#DC2626)
6. **Loading states:** skeleton loader на gallery, spinner на кнопке

---

## 4. Technical Constraints and Integration Requirements

### 4.1 Existing Technology Stack

**Languages:** Python 3.11+, TypeScript 5.0+, SQL (PostgreSQL 15+)

**Frameworks:**
- Backend: Django 5.2.7, DRF 3.14+
- Frontend: Next.js 15.4.6, React 19.1.0
- State: Zustand 4.5.7
- Forms: React Hook Form 7.62.0
- Styling: Tailwind CSS 4.0

**Database:** PostgreSQL 15+ (ТОЛЬКО PostgreSQL), Redis 7.0+ (кэш)

**Infrastructure:** Docker + Docker Compose, Nginx, Celery + Beat, GitHub Actions

**External:** 1С CommerceML 3.1, YuKassa, CDEK, Boxberry, JWT, drf-spectacular 0.28.0

**Testing:** Pytest 7.4.3 + Factory Boy 3.3.0, Vitest 2.1.5 + RTL 16.3.0 + MSW 2.12.2

### 4.2 Integration Approach

**Database Integration:**
- Новые модели: `ProductVariant`, `ColorMapping`
- Рефакторинг `Product`: удаление цен/остатков
- Миграции с pre-backup через `pg_dump`
- Foreign Keys: `ProductVariant.product` → `Product` (CASCADE)

**API Integration:**
- `ProductVariantSerializer` + `ProductDetailSerializer.variants[]`
- `ProductViewSet.retrieve()` с `prefetch_related('variants')`
- OpenAPI update + регенерация `api.generated.ts`

**Frontend Integration:**
- Новый компонент `ProductOptions.tsx`
- Props drilling: `ProductDetail` → `ProductOptions` → `ProductSummary`
- State: `useState<SelectedOptions>` с callback `onSelectionChange`

**Testing Integration:**
- Backend: unit (models), API тесты, импорт тесты с реальными XML
- Frontend: Vitest + RTL, MSW mocks, E2E user flow

### 4.3 Code Organization and Standards

**File Structure:**
```
backend/apps/products/
├── models.py              # ProductVariant, ColorMapping
├── serializers.py         # ProductVariantSerializer
├── viewsets.py            # Updated ProductViewSet
├── factories.py           # ProductVariantFactory
└── tests/
    ├── test_models.py
    ├── test_serializers.py
    └── test_import_variants.py

frontend/src/components/product/
├── ProductOptions.tsx
└── __tests__/
    └── ProductOptions.test.tsx
```

**Naming:** PascalCase (models, components), snake_case (DB tables, test files)

**Coding Standards:**
- Python: Black, Flake8, isort, mypy type hints
- TypeScript: ESLint 9, Prettier, strict mode

**Documentation:** Docstrings, drf-spectacular decorators, JSDoc, migration/admin guides

### 4.4 Deployment and Operations

**Build Process:**
- Backend: auto migrations в CI/CD
- Frontend: `prebuild` script → `npm run generate:types`

**Deployment Strategy:**
1. Staging: deploy → migrate → reimport test data → QA
2. Production: backup → deploy (2AM-4AM window) → verify → monitoring
3. Rollback: restore backup + revert code (~15 min)

**Monitoring:**
- Logs: `logs/import_products.log` (INFO/ERROR)
- Performance: Django Debug Toolbar, APM metrics
- Alerting: критические ошибки → Slack #tech-alerts

**Configuration:**
```env
IMPORT_BATCH_SIZE=500
IMPORT_LOG_FILE=/app/logs/import_products.log
COLOR_MAPPING_PRELOAD=true
```

### 4.5 Risk Assessment and Mitigation

**Technical Risks:**
- Регрессия в импорте 1С (Высокая / Критическое) → тесты с реальными XML, rollback
- N+1 queries (Средняя / Высокое) → prefetch_related, мониторинг
- Миграция сломает prod (Низкая / Критическое) → backup, staging тест

**Integration Risks:**
- Несоответствие ProductOption schema (Средняя / Высокое) → согласование JSON, integration тесты
- Изменение 1С XML (Низкая / Критическое) → версионирование парсера, валидация schema
- Деградация при 100+ вариантов (Средняя / Среднее) → индексы, edge case тесты

**Deployment Risks:**
- Rollback не работает (Низкая / Критическое) → тест rollback на staging
- Downtime > 2ч (Средняя / Высокое) → maintenance window, мониторинг
- ColorMapping не заполнен (Высокая / Низкое) → предзагрузка 20 цветов, fallback

---

## 5. Epic and Story Structure

### 5.1 Epic Approach

**Epic Structure Decision:** Единый Epic 13 с параллелизацией stories для оптимизации velocity

**Rationale:**
- Атомарность внедрения минимизирует риски частично работающей системы
- Параллелизация backend/frontend сокращает timeline с 3 до 2 спринтов
- Все stories направлены на одну цель: разблокировать Story 12.2

---

## 6. Epic 13: Product Variant System

**Epic Goal:**

Внедрить модель ProductVariant для хранения SKU-вариантов товаров (цвет, размер, цены, остатки), обеспечив корректное соответствие структуре данных 1С и разблокировав UX-сценарий "выбор опций товара" для Story 12.2.

**Integration Requirements:**
- Совместимость с CommerceML 3.1
- Сохранение endpoints `/products/`, `/categories/`
- Использование существующей дизайн-системы
- Backward compatibility для orders/cart_items
- Pre-migration backup с rollback процедурой

**Timeline:** 2 спринта + post-sprint миграция (29 SP)

---

### Спринт 1 — Foundation (параллельно)

### Story 13.1: Backend модели ProductVariant и ColorMapping

**Как** Backend разработчик,
**Я хочу** создать модели ProductVariant и ColorMapping с полной типизацией,
**Чтобы** хранить SKU-варианты товаров с ценами, остатками и характеристиками.

**Acceptance Criteria:**

1. Модель `ProductVariant` создана в `apps/products/models.py` со всеми полями из FR1
2. Модель `ColorMapping` создана для маппинга цветов на hex-коды (FR6)
3. Модель `Product` рефакторирована: удалены поля цен/остатков, добавлен related field `variants`
4. Все модели имеют полную типизацию Python (type hints) с проверкой mypy
5. Созданы индексы на `ProductVariant.sku`, `onec_id`, `product_id`, `is_active` (NFR2)
6. Реализованы computed properties: `is_in_stock`, `available_quantity` (FR8)
7. Реализован метод `get_price_for_user(user)` для роле-ориентированного ценообразования (FR9)
8. Django миграция создана и протестирована на dev окружении
9. Предзагружено 20 базовых цветов в ColorMapping через data migration

**Integration Verification:**
- IV1: Существующие модели `Brand`, `Category` остались без изменений
- IV2: Foreign key `Product.brand` и `Product.category` работают корректно
- IV3: Миграция выполняется без ошибок на пустой БД

**Estimated Effort:** 5 SP

---

### Story 13.5a: ProductOptions UI component с MSW mock

**Как** Frontend разработчик,
**Я хочу** создать компонент ProductOptions с mock-данными из MSW,
**Чтобы** начать разработку UI параллельно с backend и протестировать UX.

**Acceptance Criteria:**

1. Компонент `ProductOptions.tsx` создан в `src/components/product/`
2. Отображаются селекторы размеров (Size) как группа Chip компонентов
3. Отображаются селекторы цветов (Color) как группа Chip с цветовыми индикаторами
4. Недоступные опции (is_available: false) визуально отключены (opacity 0.5, disabled)
5. При клике на опцию обновляется состояние `selectedOptions`
6. Компонент использует дизайн-систему: Chip styles из front-end-spec.md
7. MSW mock настроен для `/products/{slug}/` с variants данными
8. Написаны unit тесты (Vitest + RTL) для отображения и взаимодействия

**Integration Verification:**
- IV1: Компонент корректно рендерится на странице `/catalog/[category]/[slug]`
- IV2: Стили соответствуют существующей дизайн-системе
- IV3: MSW mock возвращает данные в формате согласованного API контракта

**Estimated Effort:** 5 SP

---

### Спринт 2 — Integration (последовательно backend, параллельно frontend)

### Story 13.2: Рефакторинг импорта из 1С для ProductVariant

**Как** Backend разработчик,
**Я хочу** обновить импорт из 1С для создания Product + ProductVariant,
**Чтобы** корректно импортировать товары с вариантами из CommerceML 3.1.

**Acceptance Criteria:**

1. Парсер `goods.xml` создаёт один `Product` из `<Товар>` с базовой информацией
2. Парсер `offers.xml` создаёт `ProductVariant` из каждого `<Предложение>` с маппингом parent_id#variant_id (FR4)
3. Обрабатываются некорректные данные: пропуск `<Предложение>` без parent с логированием warning (FR4a)
4. Характеристики (цвет, размер) из `<ХарактеристикиТовара>` записываются в `color_name`, `size_value`
5. Товары без вариантов автоматически создают один ProductVariant (FR10a)
6. Изображения из `<Картинка>` записываются в `ProductVariant.main_image` и `gallery_images`
7. Цены из `prices.xml` обновляют соответствующие поля ProductVariant
8. Остатки из `rests.xml` обновляют `ProductVariant.stock_quantity`
9. Batch processing по 500 записей для контроля памяти (NFR4)

**Integration Verification:**
- IV1: Существующий импорт брендов и категорий остался без изменений
- IV2: Интеграция с 1С остаётся совместимой с CommerceML 3.1 (CR4)
- IV3: Логи импорта содержат информацию о пропущенных записях и ошибках (NFR8)

**Estimated Effort:** 8 SP

---

### Story 13.3: API расширение с ProductVariantSerializer

**Как** Backend разработчик,
**Я хочу** расширить API `/products/{slug}/` полем `variants[]`,
**Чтобы** frontend мог получить все SKU-варианты товара с ценами и остатками.

**Acceptance Criteria:**

1. Создан `ProductVariantSerializer` в `apps/products/serializers.py`
2. `ProductDetailSerializer` расширен полем `variants = ProductVariantSerializer(many=True, read_only=True)`
3. API endpoint `/products/{slug}/` возвращает массив variants с ценами, остатками, изображениями (FR5)
4. Цены в variants рассчитываются роле-ориентированно через `get_price_for_user(user)`
5. `ProductViewSet.retrieve()` использует `prefetch_related('variants')` для оптимизации
6. OpenAPI спецификация обновлена: `docs/api-spec.yaml` содержит `ProductVariantSchema`
7. Response time <= 500ms для товаров с <= 100 вариантами (NFR1)
8. Написаны API тесты для новых endpoints

**Integration Verification:**
- IV1: Существующий endpoint `/products/` не изменён (CR1)
- IV2: Endpoint `/categories/` не изменён (CR1)
- IV3: Serializer использует те же роли пользователей

**Estimated Effort:** 5 SP

---

### Story 13.5b: Интеграция ProductOptions с реальным API

**Как** Frontend разработчик,
**Я хочу** интегрировать ProductOptions с реальным API `/products/{slug}/`,
**Чтобы** отображать актуальные варианты товара и разблокировать Story 12.2.

**Acceptance Criteria:**

1. ProductOptions использует реальные данные из API вместо MSW mock
2. Типы обновлены из `api.generated.ts` после регенерации OpenAPI
3. При выборе цвета обновляется основное изображение в ProductGallery (FR10, AC4)
4. При выборе опций обновляется информация о наличии и цене в ProductSummary
5. Интеграция с ProductSummary: передаётся `selectedVariant` через props
6. Валидация обязательных опций перед "Добавить в корзину" (FR10, AC7)
7. Написаны integration тесты с реальным API

**Integration Verification:**
- IV1: Компонент корректно работает с API данными (нет ошибок типов)
- IV2: ProductGallery обновляет изображение при смене цвета
- IV3: ProductSummary показывает цену выбранного варианта

**Estimated Effort:** 3 SP

---

### Post-Sprint — Production Deployment

### Story 13.4: Миграция данных в production

**Как** DevOps инженер,
**Я хочу** выполнить миграцию production БД с backup и rollback планом,
**Чтобы** безопасно внедрить ProductVariant без потери данных.

**Acceptance Criteria:**

1. Pre-migration backup БД создан через `pg_dump` (NFR3)
2. Миграция Django выполнена в production без ошибок
3. Старые данные Products очищены через management command
4. Полный импорт каталога из 1С выполнен успешно
5. Валидация: количество импортированных Product и ProductVariant соответствует ожидаемому
6. Rollback процедура протестирована на staging
7. Документация создана: migration guide, admin guide (NFR9)

**Integration Verification:**
- IV1: Таблицы orders, order_items, cart_items остались без изменений
- IV2: Существующие пользователи и заказы сохранены
- IV3: API endpoints работают корректно после миграции

**Estimated Effort:** 3 SP

---

## Epic Summary

**Total Story Points:** 29 SP
**Timeline:** 2 спринта + post-sprint миграция
**Dependencies:**
- 13.1 → 13.2 → 13.3 → 13.5b (последовательно backend)
- 13.1 → 13.5a (параллельно frontend)
- 13.3 → 13.5b (интеграция)
- Все → 13.4 (финальная миграция)

**Deliverables:**
- ✅ Backend модели ProductVariant/ColorMapping
- ✅ Рефакторинг импорта 1С
- ✅ API с variants[]
- ✅ Frontend ProductOptions
- ✅ Story 12.2 разблокирована
- ✅ Production migration
- ✅ Документация

---

**End of Document**
