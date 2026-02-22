# 1C HTTP Exchange Module PRD

## 1. Intro Project Analysis and Context

### Existing Project Overview
**Current State:**
Проект FREESPORT умеет импортировать товары, цены и остатки из XML-файлов (функционал "Import Attributes" и базовый импорт).
Доставка файлов осуществляется вручную или через файловую систему.

**Goal:**
Реализовать "Транспортный уровень" интеграции с 1С:Предприятие по стандартному протоколу обмена (CommerceML/1C-Bitrix protocol).
1С сама будет инициировать соединение, авторизовываться и передавать файлы выгрузки (XML **и изображения**) по HTTP.

### Available Documentation (External)
*   [Протокол обмена с сайтом (v8.1c.ru)](https://v8.1c.ru/tekhnologii/obmen-dannymi-i-integratsiya/standarty-i-formaty/protokol-obmena-s-saytom/)
*   [Алгоритм Bitrix](https://dev.1c-bitrix.ru/api_help/sale/algorithms/data_2_site.php)
*   [Внутренняя архитектура импорта](file:///c%3A/Users/1/DEV/FREESPORT/docs/integrations/1c/architecture.md)

---

## 2. Requirements

### Functional Requirements (FR)

*   **FR1 (Endpoint):** Реализовать единую точку входа (endpoint), например `/api/v1/integration/1c/exchange/`.
*   **FR2 (Authentication - `checkauth`):**
    *   Поддержка Basic Auth (login/password).
    *   Ответ: `success`, `Cookie_Name`, `Cookie_Value`.
*   **FR3 (Initialization - `init`):**
    *   Параметры: `zip=yes/no`, `file_limit`.
    *   Ответ: `zip=zip`, `file_limit=<bytes>`.
*   **FR4 (File Upload & Organization - `file`):**
    *   Прием бинарного содержимого (chunked upload).
    *   Сборка полного файла/архива во временной директории.
    *   **Unpacking & Sorting:** Если передан ZIP-архив, он разархивируется.
    *   **Structure Rule (Strict):** Система должна поддерживать и воспроизводить файловую структуру 1С, описанную в [architecture.md](file:///c%3A/Users/1/DEV/FREESPORT/docs/integrations/1c/architecture.md#приложение-а-анализ-структуры-данных-commerceml).
        *   Целевая директория: `MEDIA_ROOT/1c_import/`
        *   `groups/groups.xml`
        *   `goods/goods.xml` (и картинки к ним могут лежать рядом или в подпапках в зависимости от архива)
        *   `offers/offers.xml`
        *   `prices/prices.xml`
        *   `rests/rests.xml`
        *   `propertiesGoods/*.xml`
        *   `propertiesOffers/*.xml`
        *   `priceLists/priceLists.xml`
        *   `storages/storages.xml`
        *   `units/units.xml`
        *   `contragents/contragents.xml`
    *   Если 1С присылает файлы без архива (последовательно), мы должны складывать их в соответствующие папки, опираясь на имя файла или тип контента (если возможно определить). Но основной сценарий - ZIP.
*   **FR5 (Import Trigger - `import`):**
    *   Параметр: `filename`.
    *   Действие: Запуск асинхронной Celery-задачи.
        *   Задача должна определить тип импорта на основе имени файла или переданного контекста.
        *   **Важно:** Учитывая сложную структуру зависимостей (справочники -> товары -> предложения), возможно потребуется "оркестратор" импорта, который запускается после получения всех файлов, либо последовательный импорт. Протокол обычно отправляет `import.xml` или `offers.xml` как триггер.
    *   Ответ: `success`.
*   **FR6 (Logging):** Полное логирование запросов/ответов.

### Non-Functional Requirements (NFR)

*   **NFR1 (Iterative Dev):** Разработка должна вестись законченными, проверяемыми этапами (Stories). Нельзя переходить к следующему этапу, пока предыдущий не верифицирован (например, сначала только auth, потом только upload).
*   **NFR2 (Perf):** Stream upload для RAM safety.
*   **NFR3 (Security):** Доступ только для 1C-юзера.

---

## 3. Technical Constraints & Architecture

> [!NOTE]
> Этот раздел требует детальной проработки Design Doc на этапе реализации, особенно в части архитектуры файлового хранилища и очередей. Ниже приведен верхнеуровневый дизайн.

### High-Level Architecture
1.  **View Layer:** `ICExchangeView` обрабатывает логику роутинга по `mode` (checkauth, init, file, import).
2.  **File Handler Service:** Сервис, отвечающий за сборку чанков.
3.  **Archive Processor:** Сервис распаковки, который знает о целевой структуре папок (goods/, offers/, etc.) и раскладывает файлы соответственно.

### Folder Structure (Target)
```
MEDIA_ROOT/
  1c_temp/       # Сборка чанков
  1c_import/     # Очищается перед каждым полным обменом (или управляется версионностью)
    goods/
    groups/
    offers/
    ... (см. FR4)
    logs/
```

---

## 4. Work Breakdown (Epics/Stories)

### Epic: 1C HTTP Transport Layer

#### Story 1: Transport Foundation & Auth (`checkauth`, `init`)
*   **Goal:** Настроить "рукопожатие" с 1С.
*   **Tasks:** Endpoint view, Basic Auth, Session cookie handling, Response formatting (text/plain).
*   **Verification:** `curl -u user:pass /exchange?mode=checkauth` returns `success`.

#### Story 2: File Upload Core (`file` - Single File)
*   **Goal:** Научиться принимать один бинарный файл чанками.
*   **Tasks:** Chunk appending logic, temp storage in `1c_temp`.
*   **Verification:** Upload a 50MB dummy file via curl/script, verify hash.

#### Story 3: Structure-Aware Unpacking
*   **Goal:** Поддержка ZIP и раскладывание по сложной структуре папок 1С.
*   **Tasks:** Unzip service that respects/creates subdirectories (`goods/`, `offers/`, etc.) inside `1c_import/`.
*   **Verification:** Upload `full_export.zip` with nested folders, verify exact structure is recreated in `1c_import/`.

#### Story 4: Asynchronous Import Trigger (`import`)
*   **Goal:** Связать транспорт с бизнес-логикой.
*   **Tasks:** Celery task `run_import_task(filepath)`, API `mode=import` handler calling `.delay()`.
*   **Verification:** Call `mode=import`, verify Celery worker received the task (logs).
