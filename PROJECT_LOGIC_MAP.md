# Карта бизнес-логики FREESPORT (backend)

## Архитектура: Fat Services, Thin Views

---

## 1. Модели данных (Django ORM)

### apps/users/models.py
- `User` (AbstractUser) — email-авторизация, роли: retail, wholesale_level1-3, trainer, federation_rep, admin
- `UserManager` — кастомный менеджер с `create_user`/`create_superuser`

### apps/products/models.py
- `Product` — базовый товар (name, slug, brand, category, description, base_images)
- `ProductVariant` — SKU, характеристики, цены, остатки (Story 13)
- `Category` — иерархическая структура с parent
- `Brand` + `Brand1CMapping` — бренды с маппингом 1С
- `Attribute` + `AttributeValue` + маппинги 1С — дедуплицированные атрибуты
- `ColorMapping` — маппинг цветов для извлечения из названия
- `ImportSession` — сессии импорта из 1С
- `PriceType` — типы цен (розница, опт1-3)

### apps/orders/models.py
- `Order` — мастер-заказ + субзаказы (VAT-split, Story 34-2)
  - `is_master`, `parent_order`, `vat_group`
  - Поля 1С: `sent_to_1c`, `sent_to_1c_at`, `status_1c`
  - Нумерация: `customer_code_snapshot`, `order_year`, `customer_year_sequence`
- `OrderItem` — позиции заказа
- `CustomerOrderSequence` — атомарная генерация номеров заказов

### apps/cart/models.py
- `Cart` — корзина (user OneToOne или session_key для гостей)
- `CartItem` — позиции корзины со снимками цен

### apps/banners/models.py
- `Banner` — hero/marketing баннеры с таргетингом по ролям
  - `cta_link` с валидацией `is_safe_internal_cta_link`
  - `start_date`/`end_date` для планирования

### apps/common/models.py
- `News`, `BlogPost` — CMS-контент
- `CustomerSyncLog` — логи синхронизации
- `NotificationRecipient` — получатели email-уведомлений
- `AuditLog` — аудит действий
- `Category` (common) — категории новостей (deprecated?)

### apps/delivery/models.py
- Модели доставки (не прочитаны детально)

---

## 2. Сервисный слой (Fat Services)

### apps/orders/services/
- `order_create.py` — `OrderCreateService` — создание мастер-заказа + субзаказов по VAT-группам
- `order_numbering.py` — `OrderNumberingService` — атомарная генерация CCCCCYYNNN, форматирование UI
- `order_status_import.py` — `OrderStatusImportService` — импорт статусов из 1С (CommerceML 3.1)
  - Master Status Aggregation (Story 34-4)
  - Rate-limited logging, batch processing

### apps/products/services/
- `variant_import.py` — `VariantImportProcessor` — импорт товаров из 1С
  - goods.xml → Product, offers.xml → ProductVariant, prices.xml, rests.xml
  - Дедупликация, batch processing (500), image normalization
- `parser.py` — `XMLDataParser` — парсинг CommerceML 3.1 (XXE-защита)
- `attribute_import.py` — `AttributeImportService` — импорт атрибутов с дедупликацией
- `facets.py` — `AttributeFacetService` — фасетный поиск

### apps/banners/services.py
- `get_role_key()`, `validate_banner_type()`, `build_cache_key()`
- `get_active_banners()` — ролевая фильтрация + кеширование (15 мин)
- `invalidate_banner_cache()` — инвалидация по типу

### apps/common/services/
- `monitoring.py` — `PrometheusMetrics`, `CustomerSyncMonitor` — метрики синхронизации
- `alerting.py` — алерты
- `customer_sync_monitor.py` — мониторинг синхронизации клиентов

### apps/integrations/onec_exchange/
- `import_orchestrator.py` — `ImportOrchestratorService` — оркестрация полного цикла импорта
- `file_service.py` — `FileStreamService`, `FileLock` — потоковая загрузка файлов с блокировками
- `routing_service.py` — `FileRoutingService` — маршрутизация файлов по правилам

---

## 3. Views/API (Thin Views)

### apps/products/views.py
- `ProductViewSet` — ReadOnlyModelViewSet с ролевым ценообразованием
  - Фильтрация, сортировка, пагинация
  - Prefetch: brand, category, attributes, variants
  - Featured brands endpoint (`/brands/featured/`) с кешированием

### apps/orders/views.py
- `OrderViewSet` — ModelViewSet
  - Только `is_master=True` для клиентов (субзаказы скрыты)
  - Double-submit protection через `select_for_update()`

### apps/cart/views.py
- `CartViewSet` — гостевые + авторизованные корзины
- `CartItemViewSet` — управление позициями

### apps/banners/views.py
- `ActiveBannersView` — ролевая фильтрация + кеширование

### apps/common/views.py
- `health_check` — endpoint состояния API
- Мониторинг метрик синхронизации

### apps/integrations/onec_exchange/views.py
- `ICExchangeView` — обработка всех mode из 1С (checkauth, init, file, import, query, success, complete, deactivate)
- `_handle_orders_xml` — синхронный импорт orders.xml (inline processing)

---

## 4. Интеграция с 1С (CommerceML 3.1)

### Протокол обмена
1. **checkauth** — аутентификация (Basic + Session без CSRF)
2. **init** — инициализация сессии (ZIP разрешён/запрещён)
3. **file** — потоковая загрузка файлов (chunked, FileStreamService)
4. **import** — триггер импорта (async via Celery)
5. **complete** — завершение цикла, финализация batch
6. **query** — выгрузка заказов из FREESPORT в 1С
7. **success** — подтверждение обработки
8. **deactivate** — уведомление о завершении обмена

### Обработка файлов
- goods.xml → `XMLDataParser.parse_goods_xml()` → Product
- offers.xml → `VariantImportProcessor` → ProductVariant
- prices.xml → цены вариантов
- rests.xml → остатки вариантов
- propertiesGoods.xml → `AttributeImportService` → Attribute
- orders.xml → `OrderStatusImportService.process()` → обновление статусов

### Защита
- XXE-защита (`defusedxml`)
- Zip Slip защита
- Размер файлов: `MAX_FILE_SIZE = 100MB`
- Rate limiting для импорта
- Stale session expiration (2 часа)

---

## 5. Асинхронные задачи (Celery)

### apps/orders/tasks.py
- `send_order_confirmation_to_customer` — email клиенту (retry 3x)
- `send_order_notification_to_staff` — email персоналу
- `send_order_cancellation_notification` — уведомление об отмене

### apps/products/tasks.py
- Импорт товаров (фоновый)

### apps/users/tasks.py
- Синхронизация пользователей

### apps/integrations/tasks.py
- Обработка интеграций

---

## 6. Ключевые паттерны

### Ролевое ценообразование
- Цена определяется ролью пользователя (retail, wholesale1-3)
- `ProductVariant.get_price_for_user(user)` — динамическая цена
- Кеширование с учётом роли (`banners:list:{type}:{role}`)

### VAT-split заказы (Story 34)
- Мастер-заказ (`is_master=True`) — видит клиент
- Субзаказы (`is_master=False`) — по группам НДС + склад
- Агрегация статуса мастера из субзаказов

### Нумерация заказов
- Формат: `CCCCC-YYNNN-S` (UI), `CCCCCYYNNNS` (канонический)
- Атомарная генерация через `CustomerOrderSequence`
- Поиск в админке нормализует UI-формат

### Импорт из 1С
- Service Layer: Parser → Processor
- Batch processing (500 записей)
- Дедупликация атрибутов по `normalized_name`
- Fallback брендов/категорий при отсутствии маппинга

---

## 7. Зависимости между модулями

```
orders ──→ products (Product, ProductVariant, PriceType)
     ──→ users (User)
     ──→ cart (Cart, CartItem)
     ──→ integrations/1c (1С exchange)

cart ──→ products (ProductVariant)
    ──→ users (User)

products ──→ common (AuditLog)
        ──→ integrations/1c (ImportSession)

banners ──→ users (User.ROLE_CHOICES)

integrations/1c ──→ products (ImportSession, Product, ProductVariant)
              ──→ orders (Order, status import)

common ──→ users (NotificationRecipient)
```

---

*Составлено: 2026-05-08. GitNexus: segfault в LadybugDB (неустранимый баг). Анализ выполнен ручным чтением исходников.*
