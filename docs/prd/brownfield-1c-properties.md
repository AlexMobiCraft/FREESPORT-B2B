# 1C Integration Properties Enhancement PRD

## 1. Intro Project Analysis and Context

### Existing Project Overview

**Analysis Source:**

* IDE-based fresh analysis
* User-provided information

**Current Project State:**
Проект представляет собой E-commerce платформу (FREESPORT) с разделением на Backend (Django) и Frontend (Next.js). Реализована базовая интеграция с 1С:Управление Торговлей через обмен XML-файлами (CommerceML 3.1). На данный момент импортируются товары, категории, бренды, цены и остатки. Однако, свойства товаров и предложений (SKU) не импортируются в структурированном виде, что ограничивает возможности фильтрации и детального отображения характеристик на сайте.

### Available Documentation Analysis

**Available Documentation:**

* [x] Tech Stack Documentation
* [x] Source Tree/Architecture
* [x] API Documentation
* [x] External API Documentation (1C Integration specs)

### Enhancement Scope Definition

**Enhancement Type:**

* [x] Major Feature Modification
* [x] Integration with New Systems (Deepening existing integration)

**Enhancement Description:**
Расширение существующей интеграции с 1С для полноценной поддержки свойств товаров и SKU. Создание системы атрибутов, импорт справочников свойств из XML, привязка свойств к товарам и вариантам, а также реализация API для фильтрации по этим свойствам.

**Impact Assessment:**

* [x] Significant Impact (Changes to data models, migrations, import logic)

### Goals and Background Context

**Goals:**

* Создать структурированное хранилище атрибутов товаров и SKU.
* Обеспечить автоматический импорт свойств из выгрузки 1С.
* Реализовать возможность фильтрации товаров по любым импортированным свойствам.
* Предоставить API для получения свойств товара и доступных фильтров (фасетов).

**Background Context:**
Текущая реализация импорта сохраняет свойства товаров в неструктурированное JSON-поле `specifications`, что делает невозможным эффективную фильтрацию и поиск по характеристикам (например, "Цвет", "Размер", "Материал"). Для улучшения UX и функциональности каталога необходимо внедрить полноценную систему атрибутов (EAV или гибридную), которая будет автоматически наполняться данными из 1С.

---

## 2. Requirements

### Functional Requirements (FR)

* **FR1:** Система должна парсить файлы справочников свойств `propertiesGoods/*.xml` и `propertiesOffers/*.xml`.
* **FR2:** Должны быть созданы модели `Attribute` (Свойство) и `AttributeValue` (Значение свойства) для хранения справочных данных.
* **FR3:** Система должна поддерживать маппинг свойств с одинаковыми именами из разных источников (товары и предложения) в единый атрибут (опционально, через настройку).
* **FR4:** При импорте товаров (`goods.xml`) и предложений (`offers.xml`) значения свойств должны привязываться к соответствующим объектам `Product` и `ProductVariant` через связи с `AttributeValue`.
* **FR5:** Существующая логика определения Бренда (из свойств) должна быть сохранена или корректно интегрирована в новую систему.
* **FR6:** Импорт должен быть идемпотентным: повторный запуск не должен дублировать атрибуты или значения.
* **FR7 (Data Mapping):** Система должна корректно обрабатывать вложенную структуру `ВариантыЗначений` -> `Справочник` из XML.
* **FR8 (Value Types):** Поддержка как справочных значений (ссылка на `AttributeValue`), так и произвольных значений (строка/число), если они придут в XML.
* **FR9 (Deduplication):** Атрибуты с одинаковым `onec_id` считаются одним и тем же атрибутом.

### Non-Functional Requirements (NFR)

* **NFR1:** Процесс импорта свойств не должен увеличивать время общего импорта более чем на 20% (использовать bulk operations).
* **NFR2:** Структура БД должна быть оптимизирована для фасетного поиска (фильтрации) по атрибутам на фронтенде (время ответа API фильтрации < 200ms).

### Compatibility Requirements (CR)

* **CR1:** Существующие поля `specifications` (JSON) в `Product` могут быть сохранены для обратной совместимости.
* **CR2:** Текущий API получения товаров должен быть расширен (добавлено поле `attributes`), но не сломан для старых клиентов.

---

## 3. Technical Constraints and Integration Requirements

### Existing Technology Stack

* **Languages:** Python 3.10+, TypeScript 5.0+
* **Frameworks:** Django 4.2, DRF 3.14, Next.js 14
* **Database:** PostgreSQL 15+
* **Infrastructure:** Docker, Nginx
* **External Dependencies:** Celery, Redis

### Integration Approach

* **Database Integration Strategy:**
  * Новые модели: `Attribute`, `AttributeValue`.
  * Связи: `Product` <-> `AttributeValue` (Many-to-Many), `ProductVariant` <-> `AttributeValue` (Many-to-Many).
  * Индексы на поля связей для быстрой фильтрации.
* **API Integration Strategy:**
  * Расширение `ProductSerializer` и `ProductVariantSerializer`.
  * Использование `django-filter` для реализации фильтрации.
  * Добавление метаданных с фасетами в ответ списка товаров.

### Code Organization and Standards

* **File Structure Approach:**
  * `apps/products/models.py`: Добавление новых моделей.
  * `apps/products/services/attribute_import.py`: Логика импорта атрибутов.
  * `apps/products/filters.py`: Логика фильтрации.
* **Naming Conventions:**
  * Models: `Attribute`, `AttributeValue`.
  * Fields: `attributes` (M2M relation).

### Risk Assessment

* **Technical Risks:**
  * Снижение производительности при большом количестве атрибутов и товаров.
  * *Mitigation:* Тщательное профилирование SQL-запросов, использование индексов, кэширование результатов фильтрации.
* **Integration Risks:**
  * Дубликаты и "мусорные" данные в справочниках 1С.
  * *Mitigation:* Инструменты администрирования для очистки и слияния атрибутов.

---

## 4. Epic and Story Structure

**Epic Structure Decision:** Single Epic
**Rationale:** Задачи тесно связаны и представляют собой единый функциональный блок интеграции.

### Epic 14: 1C Properties Integration & Filtering System

**Epic Goal:** Реализовать полную поддержку свойств товаров из 1С, включая импорт, хранение, API и фильтрацию.

**Integration Requirements:**

* Сохранение совместимости с текущим процессом импорта.
* Отсутствие регрессии в производительности каталога.

#### Story 14.1: Attribute Models & Infrastructure

**As a** Developer,
**I want** to create database models for storing product attributes,
**so that** we can store structured data from 1C.

**Acceptance Criteria:**

1. Создана модель `Attribute` (fields: `name`, `slug`, `onec_id`, `type`).
2. Создана модель `AttributeValue` (fields: `attribute`, `value`, `slug`, `onec_id`).
3. Созданы промежуточные модели для связи с `Product` и `ProductVariant`.
4. Настроена Django Admin для управления атрибутами и значениями.
5. Созданы миграции.

**Integration Verification:**

* IV1: Миграции применяются успешно на существующей базе.
* IV2: Админка открывается, модели доступны для редактирования.

#### Story 14.2: Import Attributes from 1C (Reference Data) & Admin UI

**As a** Content Manager,
**I want** attributes to be automatically imported from 1C and visible in the Admin UI,
**so that** I can verify the data quality and manage attributes.

**Acceptance Criteria:**

1. Реализован парсер файлов `propertiesGoods/*.xml` и `propertiesOffers/*.xml`.
2. Скрипт импорта создает/обновляет записи в `Attribute` и `AttributeValue`.
3. Реализована дедупликация по `onec_id`.
4. В Django Admin реализован удобный интерфейс для просмотра загруженных атрибутов (списки, фильтры, поиск).
5. В админке отображается статистика по количеству значений для каждого атрибута.

**Integration Verification:**

* IV1: Запуск команды импорта корректно заполняет таблицы атрибутов данными из XML.
* IV2: Повторный запуск не создает дубликатов.
* IV3: В админке можно найти атрибут по имени или ID и просмотреть его значения.

#### Story 14.3: Link Attributes to Products & Variants

**As a** User,
**I want** products to have detailed specifications linked to them,
**so that** the data is structured and accurate.

**Acceptance Criteria:**

1. Обновлен парсер `goods.xml`: при создании/обновлении `Product` создаются связи с `AttributeValue`.
2. Обновлен парсер `offers.xml`: при создании/обновлении `ProductVariant` создаются связи с `AttributeValue`.
3. Обработаны случаи, когда значение атрибута в товаре ссылается на несуществующее значение (создание on-the-fly или логирование ошибки).

**Integration Verification:**

* IV1: После полного импорта у товаров в БД есть связи с атрибутами.
* IV2: Проверено соответствие данных в XML и в БД для тестового товара.

#### Story 14.4: API Enhancement for Attributes

**As a** Frontend Developer,
**I want** to receive structured attributes in the Product API,
**so that** I can display them on the product page.

**Acceptance Criteria:**

1. `ProductSerializer` включает поле `attributes` со списком пар (имя атрибута, значение).
2. `ProductVariantSerializer` включает поле `attributes` (специфичные для варианта + наследуемые от товара).
3. Оптимизированы SQL-запросы (prefetch_related) для избежания N+1 проблемы.

**Integration Verification:**

* IV1: GET запрос к товару возвращает корректный JSON с атрибутами.
* IV2: Время ответа API не увеличилось значительно.

#### Story 14.5: Filtering & Facets API

**As a** User,
**I want** to filter products by attributes (e.g., Size, Color),
**so that** I can find exactly what I need.

**Acceptance Criteria:**

1. Реализован `ProductFilterSet` с поддержкой динамической фильтрации по атрибутам.
2. API списка товаров возвращает метаданные с доступными фильтрами (фасетами) и количеством товаров.
3. Поддержка множественного выбора значений фильтра (OR внутри атрибута, AND между атрибутами).

**Integration Verification:**

* IV1: Запрос `?attr_color=red` возвращает только красные товары.
* IV2: Фасеты корректно пересчитываются при применении фильтров.
