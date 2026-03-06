# Отчет для Product Manager: Модель ProductVariant

## Статус документа

| Параметр | Значение |
|----------|----------|
| **Дата создания** | 30.11.2025 |
| **Автор** | Sarah (PO) |
| **Статус** | Draft |
| **Связанные истории** | Story 12.2 (Выбор опций товара) |

---

## Резюме

Для реализации функциональности выбора опций товара (Story 12.2) и корректной интеграции с 1С необходимо разработать новую модель `ProductVariant`. Текущая архитектура не позволяет корректно отображать варианты товаров с разными цветами, размерами, ценами и остатками.

---

## Бизнес-контекст

### Текущая проблема

Сейчас каждый SKU из 1С импортируется как **отдельный `Product`**. Это приводит к:

- Дублированию базовой информации (описание, бренд, категория)
- Невозможности группировки вариантов одного товара на странице
- Отсутствию UX-сценария "выбор цвета/размера" для покупателя

### Целевой UX

Покупатель на странице товара видит:

1. Базовую информацию о товаре (название, описание, бренд)
2. Селектор **цветов** с превью изображений
3. Селектор **размеров** с индикацией наличия
4. Актуальную цену и остаток для выбранной комбинации

---

## Архитектурное решение

### Новая модель `ProductVariant`

```text
Product (базовый товар)
├── name, description, brand, category
├── base_images (общие изображения)
└── variants[] → ProductVariant
    ├── sku (артикул SKU)
    ├── onec_id (ID из 1С)
    ├── color_name ("Красный", "Синий")
    ├── size_value ("42", "XL")
    ├── prices (retail, opt1, opt2...)
    ├── stock_quantity
    ├── main_image (основное изображение)
    └── gallery_images[] (галерея)
```

### Ключевые принципы

| # | Принцип | Обоснование |
|---|---------|-------------|
| 1 | **Один SKU = один ProductVariant** | Соответствует структуре данных 1С: каждое `<Предложение>` в `offers.xml` — отдельный SKU со своими ценами и остатками |
| 2 | **Цвет хранится как текст** | В 1С отсутствуют hex-коды, только справочники с текстовыми названиями ("Красный", "Синий") |
| 3 | **Матрица доступности не нужна** | Каждая комбинация цвет+размер — это отдельный SKU с собственным `stock_quantity` |
| 4 | **Изображения привязаны к варианту** | Каждый SKU имеет свои изображения, отражающие конкретный цвет товара |

---

## Соответствие данным 1С

### Источники данных

| Файл 1С | Что извлекаем | Куда записываем |
|---------|---------------|-----------------|
| `goods/goods.xml` | Базовая информация (название, описание, категория) | `Product` |
| `goods/goods.xml` → `<Картинка>` | Изображения варианта товара | `ProductVariant.main_image`, `ProductVariant.gallery_images` |
| `offers/offers.xml` | SKU, характеристики (цвет, размер) | `ProductVariant` |
| `prices/prices.xml` | Цены по типам (розница, опт1, опт2...) | `ProductVariant.prices` |
| `rests/rests.xml` | Остатки на складах | `ProductVariant.stock_quantity` |
| `propertiesOffers/` | Справочник цветов/размеров | Маппинг `color_name`, `size_value` |

### Структура изображений в 1С

Изображения находятся в `goods/goods.xml` и хранятся по пути:

```text
data/import_1c/goods/import_files/XY/[имя_файла]
```

где `XY` — первые две цифры UUID товара.

```xml
<!-- goods.xml -->
<Товар>
  <Ид>12345678-abcd-...</Ид>
  <Картинка>goods/import_files/12/front.jpg</Картинка>
  <Картинка>goods/import_files/12/back.jpg</Картинка>
  <Картинка>goods/import_files/12/detail.jpg</Картинка>
</Товар>
```

### Пример данных SKU из 1С

```xml
<!-- offers.xml -->
<Предложение>
  <Ид>parent-uuid#variant-uuid</Ид>
  <Наименование>Кроссовки Nike Air Max (Красный, 42)</Наименование>
  <Артикул>NIKE-AM-RED-42</Артикул>
  <ХарактеристикиТовара>
    <Характеристика>
      <Наименование>Цвет</Наименование>
      <Значение>Красный</Значение>
    </Характеристика>
    <Характеристика>
      <Наименование>Размер</Наименование>
      <Значение>42</Значение>
    </Характеристика>
  </ХарактеристикиТовара>
</Предложение>
```

---

## Предлагаемая структура моделей

### ProductVariant

```python
class ProductVariant(models.Model):
    """
    Вариант товара (SKU) с конкретным цветом, размером, ценами и остатками.
    
    Каждый вариант соответствует одному <Предложение> из offers.xml в 1С.
    """
    
    product = models.ForeignKey(
        Product, 
        on_delete=models.CASCADE,
        related_name='variants',
        verbose_name='Базовый товар'
    )
    
    # Идентификация
    sku = models.CharField('Артикул', max_length=100, unique=True)
    onec_id = models.CharField(
        'ID в 1С', 
        max_length=100, 
        unique=True,
        help_text='Составной ID из offers.xml: parent_id#variant_id'
    )
    
    # Характеристики варианта
    color_name = models.CharField(
        'Цвет', 
        max_length=100, 
        blank=True,
        help_text='Текстовое название цвета из справочника 1С'
    )
    size_value = models.CharField(
        'Размер', 
        max_length=50, 
        blank=True,
        help_text='Значение размера (42, XL, и т.д.)'
    )
    
    # Цены (аналогично текущей модели Product)
    retail_price = models.DecimalField('Розничная цена', max_digits=10, decimal_places=2)
    opt1_price = models.DecimalField('Опт 1', max_digits=10, decimal_places=2, null=True, blank=True)
    opt2_price = models.DecimalField('Опт 2', max_digits=10, decimal_places=2, null=True, blank=True)
    opt3_price = models.DecimalField('Опт 3', max_digits=10, decimal_places=2, null=True, blank=True)
    trainer_price = models.DecimalField('Для тренеров', max_digits=10, decimal_places=2, null=True, blank=True)
    federation_price = models.DecimalField('Для федераций', max_digits=10, decimal_places=2, null=True, blank=True)
    
    # Остатки
    stock_quantity = models.PositiveIntegerField('Количество на складе', default=0)
    reserved_quantity = models.PositiveIntegerField('Зарезервировано', default=0)
    
    # Изображения (аналогично текущей модели Product)
    main_image = models.ImageField(
        'Основное изображение',
        upload_to='products/variants/',
        blank=True,
        help_text='Первое изображение из <Картинка> в goods.xml'
    )
    gallery_images = models.JSONField(
        'Галерея изображений',
        default=list,
        blank=True,
        help_text='Список путей к дополнительным изображениям'
    )
    
    # Статус и синхронизация
    is_active = models.BooleanField('Активен', default=True)
    last_sync_at = models.DateTimeField('Последняя синхронизация', null=True, blank=True)
    
    # Временные метки
    created_at = models.DateTimeField('Создан', auto_now_add=True)
    updated_at = models.DateTimeField('Обновлен', auto_now=True)
    
    class Meta:
        verbose_name = 'Вариант товара'
        verbose_name_plural = 'Варианты товаров'
        db_table = 'product_variants'
        ordering = ['color_name', 'size_value']
        indexes = [
            models.Index(fields=['product', 'is_active']),
            models.Index(fields=['sku']),
            models.Index(fields=['onec_id']),
            models.Index(fields=['color_name']),
            models.Index(fields=['size_value']),
            models.Index(fields=['stock_quantity']),
        ]
    
    @property
    def is_in_stock(self) -> bool:
        """Проверка наличия на складе"""
        return self.stock_quantity > 0
    
    @property
    def available_quantity(self) -> int:
        """Доступное количество (с учетом резерва)"""
        return max(0, self.stock_quantity - self.reserved_quantity)
    
    def get_price_for_user(self, user) -> Decimal:
        """Получить цену для конкретного пользователя"""
        # Логика аналогична Product.get_price_for_user
        pass
```

### ColorMapping (справочник цветов)

```python
class ColorMapping(models.Model):
    """
    Маппинг текстовых названий цветов на hex-коды.
    
    Заполняется вручную администратором, т.к. в 1С hex-коды отсутствуют.
    """
    
    name = models.CharField(
        'Название цвета', 
        max_length=100, 
        unique=True,
        help_text='Название из справочника 1С'
    )
    hex_code = models.CharField(
        'Hex-код', 
        max_length=7,
        help_text='Например: #FF0000'
    )
    swatch_image = models.ImageField(
        'Изображение образца', 
        upload_to='colors/',
        blank=True,
        help_text='Для сложных цветов (градиенты, паттерны)'
    )
    
    class Meta:
        verbose_name = 'Маппинг цвета'
        verbose_name_plural = 'Маппинг цветов'
        db_table = 'color_mappings'
```

---

## Влияние на существующую систему

### Требуемые изменения

| Компонент | Изменение | Сложность | Приоритет |
|-----------|-----------|-----------|-----------|
| **Модели** | Новые модели `ProductVariant`, `ColorMapping` | Средняя | Высокий |
| **Импорт 1С** | Рефакторинг парсера для создания вариантов вместо отдельных Product | Высокая | Высокий |
| **API** | Расширение `ProductDetailSerializer` полем `variants[]` | Средняя | Высокий |
| **Frontend** | Компонент `ProductOptions` (Story 12.2) | Средняя | Высокий |
| **Корзина** | Хранение `variant_id` вместо `product_id` | Средняя | Средний |
| **Заказы** | Связь позиции заказа с `ProductVariant` | Средняя | Средний |
| **Admin** | Inline-редактирование вариантов в карточке товара | Низкая | Низкий |

### Миграция данных

Для упрощения процесса миграции предлагается **очистить данные и выполнить импорт с нуля**:

1. **Очистить таблицы** `products`, `product_images`, связанные корзины и заказы
2. **Создать новые модели** `ProductVariant`, `ColorMapping`
3. **Обновить импорт из 1С** для работы с новой структурой
4. **Выполнить полный импорт** каталога из 1С

**Обоснование:**
- Проект находится на этапе разработки, production-данных нет
- Сложная миграция существующих данных нецелесообразна
- Импорт с нуля гарантирует консистентность данных

---

## Hex-коды цветов

### Проблема

В 1С отсутствуют hex-коды цветов — только текстовые названия из справочника.

### Решение

1. **Создать модель `ColorMapping`** для соответствия название → hex-код
2. **Предзаполнить базовыми цветами:**

   ```python
   BASIC_COLORS = {
    'Белый': '#FFFFFF',
    'Черный': '#000000',
    'Красный': '#FF0000',
    'Синий': '#0000FF',
    'Зеленый': '#00FF00',
    'Желтый': '#FFFF00',
    'Серый': '#808080',
    'Розовый': '#FFC0CB',
    'Оранжевый': '#FFA500',
    'Фиолетовый': '#800080',
       # ... и т.д.
   }
```

3. **Администратор дополняет** маппинг для специфических цветов ("Терракотовый", "Морская волна")
4. **Fallback:** если hex-код не найден — показывать только текстовое название без цветового индикатора

---

## План реализации

### Фаза 1: Backend — модели, API, импорт (Epic 3)

**Модели:**

- [ ] Создать модель `ProductVariant` с полями: sku, onec_id, color_name, size_value, prices, stock, main_image, gallery_images
- [ ] Создать модель `ColorMapping` для маппинга цветов на hex-коды
- [ ] Обновить модель `Product` — убрать поля цен/остатков, оставить базовую информацию (name, description, brand, category)
- [ ] Написать миграцию схемы БД

**Импорт из 1С:**

- [ ] Рефакторинг парсера для создания `Product` + `ProductVariant`
- [ ] Обновить процессор для записи изображений в `ProductVariant`
- [ ] Очистить старые данные (products, product_images)
- [ ] Выполнить полный импорт каталога из 1С

**API:**

- [ ] Создать `ProductVariantSerializer`
- [ ] Расширить `ProductDetailSerializer` полем `variants[]`
- [ ] Обновить OpenAPI спецификацию (`api-spec.yaml`)
- [ ] Написать unit + API тесты

**Оценка:** 8-13 story points

### Фаза 2: Frontend — Story 12.2

- [ ] Обновить типы в `api.generated.ts`
- [ ] Реализовать компонент `ProductOptions`
- [ ] Интеграция с `ProductSummary`
- [ ] Написать frontend тесты

**Оценка:** 5-8 story points

### Фаза 3: Корзина и заказы (отдельный Epic, не блокирует Story 12.2)

- [ ] Обновить модель `CartItem` — добавить `variant_id`
- [ ] Обновить модель `OrderItem` — связь с `ProductVariant`
- [ ] Обновить API корзины и заказов
- [ ] Написать тесты

**Оценка:** 3-5 story points

---

## Риски и митигация

| Риск | Вероятность | Влияние | Митигация |
|------|-------------|---------|-----------|
| Изменение структуры корзины/заказов | Средняя | Среднее | Обратная совместимость через `product_id` fallback |
| Неполные данные о цветах/размерах в 1С | Средняя | Среднее | Валидация при импорте, логирование пропусков |
| Отсутствие hex-кодов в 1С | 100% | Низкое | Справочник `ColorMapping` с ручным заполнением |
| Производительность при большом количестве вариантов | Низкая | Среднее | Индексы, prefetch_related, пагинация |

---

## Альтернативы (рассмотрены и отклонены)

### 1. Хранить варианты в JSONField

**Минусы:**
- Невозможность эффективной фильтрации по цвету/размеру
- Сложность обновления остатков отдельного варианта
- Нет referential integrity

### 2. Оставить текущую структуру (каждый SKU = Product)

**Минусы:**
- Невозможность группировки на фронтенде
- Дублирование данных
- Не соответствует UX требованиям Story 12.2

---

## Заключение

Разработка модели `ProductVariant` является **необходимым условием** для:

- ✅ Корректного отображения вариантов товара на фронтенде
- ✅ Точного учета остатков по каждому SKU
- ✅ Правильной работы корзины и заказов
- ✅ Соответствия архитектуры данным из 1С
- ✅ Реализации Story 12.2 (Выбор опций товара)

**Рекомендация:** Включить разработку `ProductVariant` в ближайший спринт как **блокирующую задачу** для Story 12.2.

---

## Приложения

### A. Связанные документы

- [20-1c-integration.md](./20-1c-integration.md) — Архитектура интеграции с 1С
- [Story 12.2](../stories/epic-12/12.2.product-options.md) — Выбор опций товара
- [data-analysis.md](../epics/epic-3/data-analysis.md) — Анализ структуры данных CommerceML

### B. Глоссарий

| Термин | Определение |
|--------|-------------|
| **SKU** | Stock Keeping Unit — уникальный идентификатор товарной позиции |
| **Вариант** | Конкретная комбинация цвет+размер товара |
| **CommerceML** | Стандарт обмена данными с 1С |
| **Предложение** | Элемент `<Предложение>` в offers.xml, соответствует одному SKU |

---

---

Документ подготовлен: Sarah (PO) | Дата: 30.11.2025
