# 8. Основные Рабочие Процессы

### Процесс регистрации пользователя

```mermaid
flowchart TD
    A[Пользователь заполняет форму] --> B{Тип регистрации}
    B -->|B2C| C[Валидация email]
    B -->|B2B| D[Валидация компании + документы]
    
    C --> E[Отправка кода подтверждения]
    D --> F[Ручная модерация админом]
    
    E --> G[Пользователь вводит код]
    F --> H{Одобрено?}
    
    G --> I{Код верный?}
    H -->|Да| J[Активация B2B аккаунта]
    H -->|Нет| K[Отклонение с объяснением]
    
    I -->|Да| L[Активация B2C аккаунта]
    I -->|Нет| M[Повторная отправка кода]
    
    J --> N[Доступ к B2B ценам]
    L --> O[Доступ к розничным ценам]
    K --> P[Уведомление пользователю]
    M --> G
```

### Процесс создания заказа

```mermaid
sequenceDiagram
    participant User as Пользователь
    participant Frontend as Next.js Frontend
    participant BFF as Next.js API (BFF)
    participant Django as Django API
    participant YuKassa as ЮКасса
    participant Celery as Celery Worker
    participant OneC as 1C ERP

    User->>Frontend: Нажимает "Оформить заказ"
    Frontend->>BFF: POST /api/orders
    BFF->>Django: POST /orders/
    
    Django->>Django: Валидация корзины
    Django->>Django: Проверка остатков
    Django->>Django: Расчет цены по роли пользователя
    
    Django->>YuKassa: Создание платежа
    YuKassa-->>Django: Ссылка на оплату
    
    Django-->>BFF: Заказ + ссылка на оплату
    BFF-->>Frontend: Данные заказа
    Frontend-->>User: Редирект на оплату
    
    User->>YuKassa: Оплачивает заказ
    YuKassa->>Django: Webhook о статусе оплаты
    
    Django->>Celery: Задача экспорта в 1С
    Celery->>OneC: Экспорт заказа
    OneC-->>Celery: Подтверждение
    Celery->>Django: Обновление статуса
```

### Процесс синхронизации с 1С

```mermaid
flowchart TD
    A[Celery Beat Scheduler] --> B[Запуск задачи синхронизации]
    B --> C{Проверка Circuit Breaker}
    
    C -->|Open| D[HTTP запрос к 1С]
    C -->|Closed| E[Файловый экспорт]
    
    D --> F{1С доступна?}
    F -->|Да| G[Синхронизация товаров]
    F -->|Нет| H[Circuit Breaker -> Closed]
    
    G --> I[Обновление цен и остатков]
    I --> J[Экспорт новых заказов]
    J --> K[Импорт статусов заказов]
    
    E --> L[Создание XML файлов]
    L --> M[Сохранение в FTP папку]
    M --> N[Уведомление администратора]
    
    H --> O[Переход к файловому обмену]
    O --> L
    
    K --> P[Завершение синхронизации]
    N --> P
```

### Workflow управления ценами

```mermaid
stateDiagram-v2
    [*] --> PriceUpdate
    
    PriceUpdate --> B2CValidation: Розничная цена
    PriceUpdate --> B2BValidation: Оптовые цены
    
    B2CValidation --> PriceApproval: Валидация успешна
    B2BValidation --> PriceApproval: Валидация успешна
    
    PriceApproval --> AutoApproval: Изменение < 10%
    PriceApproval --> ManualApproval: Изменение > 10%
    
    AutoApproval --> PriceActivation
    ManualApproval --> AdminReview
    
    AdminReview --> PriceActivation: Одобрено
    AdminReview --> PriceRejection: Отклонено
    
    PriceActivation --> CacheInvalidation
    CacheInvalidation --> PriceNotification
    
    PriceNotification --> [*]
    PriceRejection --> [*]
```

### Процесс обработки возвратов

```mermaid
flowchart TD
    A[Клиент подает заявку на возврат] --> B[Создание Return Request]
    B --> C{Условия возврата?}
    
    C -->|В пределах 14 дней| D[Автоматическое одобрение]
    C -->|Вне срока| E[Ручное рассмотрение]
    C -->|Поврежденный товар| F[Запрос фотографий]
    
    D --> G[Генерация этикетки возврата]
    E --> H{Решение менеджера}
    F --> I[Рассмотрение фотографий]
    
    H -->|Одобрено| G
    H -->|Отклонено| J[Уведомление об отказе]
    I -->|Одобрено| G
    I -->|Отклонено| J
    
    G --> K[Получение товара на склад]
    K --> L[Проверка качества]
    L --> M{Товар в порядке?}
    
    M -->|Да| N[Возврат средств]
    M -->|Нет| O[Частичный возврат]
    
    N --> P[Обновление остатков в 1С]
    O --> P
    J --> Q[Закрытие заявки]
    P --> Q
```

### Процесс синхронизации покупателей с 1С

```mermaid
flowchart TD
    A[Планировщик запускает синхронизацию] --> B[Получение данных покупателей из 1С]
    B --> C{Формат данных}
    
    C -->|CommerceML 2.0| D[Парсинг XML файла]
    C -->|REST API| E[HTTP запрос к 1С]
    C -->|Файловый обмен| F[Чтение CSV/XML файла]
    
    D --> G[Обработка записи покупателя]
    E --> G
    F --> G
    
    G --> H{Покупатель существует?}
    H -->|Нет| I[Создание нового покупателя]
    H -->|Да| J{Данные изменились?}
    
    I --> K[Валидация данных]
    J -->|Нет| L[Пропуск записи]
    J -->|Да| M[Проверка конфликтов]
    
    K --> N{Валидация успешна?}
    N -->|Да| O[Сохранение покупателя]
    N -->|Нет| P[Логирование ошибки]
    
    M --> Q{Конфликт данных?}
    Q -->|Нет| R[Обновление покупателя]
    Q -->|Да| S[Создание SyncConflict]
    
    O --> T[Логирование успеха]
    R --> T
    P --> U[Переход к следующей записи]
    L --> U
    S --> V[Уведомление администратора]
    T --> U
    V --> U
    
    U --> W{Есть еще записи?}
    W -->|Да| G
    W -->|Нет| X[Генерация отчета синхронизации]
    
    X --> Y[Сохранение ImportLog]
    Y --> Z[Завершение процесса]
```

### Процесс разрешения конфликтов синхронизации

```mermaid
sequenceDiagram
    participant Admin as Администратор
    participant Platform as Платформа
    participant OneC as 1С
    participant ConflictResolver as Conflict Resolver

    Admin->>Platform: Просмотр конфликтов
    Platform->>Admin: Список неразрешенных конфликтов
    
    Admin->>Platform: Выбор конфликта для разрешения
    Platform->>Admin: Детали конфликта (платформа vs 1С)
    
    Admin->>ConflictResolver: Выбор стратегии разрешения
    
    alt Стратегия: platform_wins
        ConflictResolver->>Platform: Сохранение данных платформы
        ConflictResolver->>OneC: Экспорт изменений в 1С
    else Стратегия: onec_wins
        ConflictResolver->>Platform: Обновление данных из 1С
        ConflictResolver->>Platform: Сохранение изменений
    else Стратегия: merge
        ConflictResolver->>ConflictResolver: Объединение данных
        ConflictResolver->>Platform: Сохранение объединенных данных
        ConflictResolver->>OneC: Экспорт изменений в 1С
    else Стратегия: manual
        Admin->>ConflictResolver: Ручное редактирование данных
        ConflictResolver->>Platform: Сохранение отредактированных данных
    end
    
    ConflictResolver->>Platform: Отметка конфликта как разрешенного
    ConflictResolver->>Platform: Логирование разрешения
    Platform->>Admin: Подтверждение разрешения конфликта
```

### Процесс экспорта покупателей в 1С

```mermaid
flowchart TD
    A[Триггер: новая регистрация B2B] --> B[Проверка настроек синхронизации]
    B --> C{Автоэкспорт включен?}
    
    C -->|Да| D[Немедленная отправка]
    C -->|Нет| E[Добавление в очередь экспорта]
    
    D --> F[Формирование данных для 1С]
    E --> G[Ожидание планового экспорта]
    G --> F
    
    F --> H[Конвертация в формат 1С]
    H --> I{Метод передачи}
    
    I -->|API| J[HTTP POST к 1С]
    I -->|Файловый| K[Создание XML файла]
    
    J --> L{Ответ 1С успешный?}
    K --> M[Сохранение в папку обмена]
    M --> N[FTP загрузка]
    N --> O[Ожидание обработки 1С]
    
    L -->|Да| P[Обновление onec_id покупателя]
    L -->|Нет| Q[Логирование ошибки]
    O --> R{Файл обработан?}
    
    P --> S[Отметка экспорта как успешного]
    Q --> T[Повторная попытка через интервал]
    R -->|Да| P
    R -->|Нет| U[Ожидание таймаута]
    
    S --> V[Логирование CustomerSyncLog]
    T --> W{Превышен лимит попыток?}
    U --> R
    
    W -->|Нет| F
    W -->|Да| X[Отправка в ручную обработку]
    V --> Y[Завершение экспорта]
    X --> Z[Уведомление администратора]
```

### Процесс обработки дублирующихся покупателей

```mermaid
stateDiagram-v2
    [*] --> DuplicateDetection
    
    DuplicateDetection --> EmailMatch: Найден email
    DuplicateDetection --> TaxIdMatch: Найден ИНН
    DuplicateDetection --> PhoneMatch: Найден телефон
    
    EmailMatch --> ConflictAnalysis
    TaxIdMatch --> ConflictAnalysis
    PhoneMatch --> ConflictAnalysis
    
    ConflictAnalysis --> DataComparison: Сравнение полей
    
    DataComparison --> IdenticalData: Данные идентичны
    DataComparison --> MinorDifferences: Незначительные различия
    DataComparison --> MajorConflicts: Серьезные конфликты
    
    IdenticalData --> AutoMerge: Автоматическое объединение
    MinorDifferences --> AdminReview: Требует проверки
    MajorConflicts --> ManualResolution: Ручное разрешение
    
    AutoMerge --> UpdateOnecId: Обновление 1С ID
    AdminReview --> AdminDecision
    ManualResolution --> AdminDecision
    
    AdminDecision --> MergeAccounts: Объединить
    AdminDecision --> KeepSeparate: Оставить отдельно
    AdminDecision --> RejectImport: Отклонить импорт
    
    MergeAccounts --> UpdateOnecId
    KeepSeparate --> CreateSyncConflict
    RejectImport --> LogRejection
    
    UpdateOnecId --> SyncComplete
    CreateSyncConflict --> SyncComplete
    LogRejection --> SyncComplete
    
    SyncComplete --> [*]
```

### Workflow мониторинга синхронизации

```mermaid
flowchart TD
    A[Система мониторинга] --> B[Проверка статуса последней синхронизации]
    B --> C{Синхронизация просрочена?}
    
    C -->|Нет| D[Мониторинг ImportLog]
    C -->|Да| E[Критическое уведомление]
    
    D --> F{Есть ошибки?}
    F -->|Нет| G[Проверка конфликтов]
    F -->|Да| H[Анализ ошибок]
    
    G --> I{Неразрешенные конфликты?}
    I -->|Нет| J[Система работает нормально]
    I -->|Да| K[Уведомление о конфликтах]
    
    H --> L{Критические ошибки?}
    L -->|Да| M[Экстренное уведомление]
    L -->|Нет| N[Обычное уведомление об ошибках]
    
    E --> O[Отправка алерта администратору]
    K --> O
    M --> O
    N --> P[Отправка summary отчета]
    
    O --> Q[Логирование инцидента]
    P --> Q
    J --> R[Обновление dashboard статуса]
    Q --> R
    
    R --> S[Ожидание следующей проверки]
    S --> A
```

---
