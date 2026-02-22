# 6. Высокоуровневая Архитектура

### Диаграмма развертывания инфраструктуры

```mermaid
C4Deployment
    title Deployment Diagram - FREESPORT Production Infrastructure (Optimized Layout)

    %% Группируем всех пользователей
    Deployment_Node(client, "Client Devices", "User Environment") {
        Person(b2b_users, "B2B Users", "Wholesale buyers, trainers")
        Person(b2c_users, "B2C Users", "Retail customers")
        Person(admins, "Administrators", "System managers")
    }
    %% Основной узел сервера с вложенной группировкой для ясности
    Deployment_Node(cloud, "VPS/VDS Server", "Production Environment") {
        
        %% Внутренний узел для компонентов, отвечающих за обработку запросов
        Deployment_Node(app_layer, "Application Layer") {
            Container(nginx, "Nginx", "Web Server", "Load balancer, SSL")
            Container(nextjs, "Next.js App", "Node.js 18+", "Frontend + BFF")
            Container(django, "Django API", "Python 3.11+", "Backend API")
        }

        %% Внутренний узел для данных и фоновых служб с измененным порядком
        Deployment_Node(data_layer, "Data & Processing Layer") {
            ContainerDb(postgres, "PostgreSQL", "Database", "Primary data store")
            Container(celery, "Celery Workers", "Python 3.11+", "Async tasks")
            ContainerDb(redis, "Redis", "Cache & Broker", "Sessions, message queue")
            Container(celery_beat, "Celery Beat", "Python 3.11+", "Task scheduler")
        }

        %% --- Внутренние связи ---
        Rel(nginx, nextjs, "Проксирует запросы", "port 3000")
        Rel(nginx, django, "Проксирует /api", "port 8000")
        Rel(nextjs, django, "Внутренние вызовы API")

        Rel(django, postgres, "Читает/пишет данные", "SQL/5432")
        Rel(django, redis, "Кэширует данные")

        Rel(celery, redis, "Забирает задачи из", "Queue/6379")
        Rel(celery_beat, redis, "Публикует задачи в")
        Rel(celery, postgres, "Читает/пишет данные")
    }

    %% Группируем внешние сервисы
    Deployment_Node(external, "External Services", "Third-party Integrations") {
        System_Ext(onec, "1C ERP", "Business management")
        System_Ext(yukassa, "YuKassa", "Payment processing")
        System_Ext(delivery, "Delivery APIs", "CDEK, Boxberry")
    }

    %% --- Внешние связи ---
    Rel(b2b_users, nginx, "Использует", "HTTPS")
    Rel(b2c_users, nginx, "Использует", "HTTPS")
    Rel(admins, nginx, "Управляет через", "HTTPS")

    Rel(django, onec, "Синхронизирует данные", "API/Files")
    Rel(django, yukassa, "Обрабатывает платежи", "Webhooks")
    Rel(django, delivery, "Получает тарифы", "API")
```

### Схема сетевого взаимодействия

```mermaid
graph LR
    subgraph "DMZ Zone"
        NGINX[Nginx<br/>:443, :80]
        FIREWALL[Firewall<br/>Rules]
    end
    
    subgraph "Application Zone"
        NEXT[Next.js<br/>:3000]
        DJANGO[Django<br/>:8000]
        CELERY[Celery Workers<br/>Background]
    end
    
    subgraph "Data Zone"
        POSTGRES[PostgreSQL<br/>:5432]
        REDIS[Redis<br/>:6379]
        FILES[File Storage<br/>Local/S3]
    end
    
    subgraph "External Zone"
        ONEC[1C ERP<br/>Various]
        PAYMENTS[YuKassa<br/>:443]
        DELIVERY[Delivery APIs<br/>:443]
    end
    
    Internet -->|TCP:443| FIREWALL
    FIREWALL -->|HTTP/HTTPS| NGINX
    
    NGINX -->|Proxy| NEXT
    NGINX -->|Proxy /api/| DJANGO
    NGINX -->|Static files| FILES
    
    NEXT -->|Internal API| DJANGO
    
    DJANGO -->|SQL| POSTGRES
    DJANGO -->|Cache| REDIS
    CELERY -->|Queue| REDIS
    CELERY -->|Data| POSTGRES
    
    DJANGO -.->|Scheduled sync| ONEC
    DJANGO -.->|Webhooks| PAYMENTS
    DJANGO -.->|Rate limited| DELIVERY
```

### Диаграмма компонентов с портами и интерфейсами

```mermaid
graph TB
    subgraph "Frontend Layer"
        FE_COMPONENTS[React Components]
        FE_SERVICES[Frontend Services]
        FE_STORES[Zustand Stores]
        FE_ROUTER[Next.js Router]
    end
    
    subgraph "BFF Layer (Next.js API)"
        BFF_AUTH[Auth Middleware<br/>Port: JWT validation]
        BFF_RATE[Rate Limiter<br/>Port: Request control]
        BFF_AGGREGATE[Data Aggregator<br/>Port: Multi-source data]
    end
    
    subgraph "Backend API Layer"
        API_AUTH[Authentication<br/>Port: /auth/*]
        API_PRODUCTS[Products API<br/>Port: /products/*]
        API_ORDERS[Orders API<br/>Port: /orders/*]
        API_USERS[Users API<br/>Port: /users/*]
        API_CART[Cart API<br/>Port: /cart/*]
    end
    
    subgraph "Business Logic Layer"
        BL_USER[User Management<br/>Interface: UserService]
        BL_PRODUCT[Product Management<br/>Interface: ProductService]
        BL_ORDER[Order Processing<br/>Interface: OrderService]
        BL_PRICING[Pricing Engine<br/>Interface: PricingService]
        BL_INVENTORY[Inventory Management<br/>Interface: InventoryService]
    end
    
    subgraph "Integration Layer"
        INT_1C[1C Connector<br/>Interface: ERPInterface]
        INT_PAYMENT[Payment Gateway<br/>Interface: PaymentInterface]
        INT_DELIVERY[Delivery APIs<br/>Interface: ShippingInterface]
    end
    
    subgraph "Data Access Layer"
        DAL_USER[User Repository<br/>Interface: IUserRepository]
        DAL_PRODUCT[Product Repository<br/>Interface: IProductRepository]
        DAL_ORDER[Order Repository<br/>Interface: IOrderRepository]
    end
    
    FE_COMPONENTS --> FE_SERVICES
    FE_SERVICES --> BFF_AUTH
    FE_STORES --> FE_SERVICES
    
    BFF_AUTH --> API_AUTH
    BFF_RATE --> API_PRODUCTS
    BFF_AGGREGATE --> API_ORDERS
    
    API_AUTH --> BL_USER
    API_PRODUCTS --> BL_PRODUCT
    API_ORDERS --> BL_ORDER
    API_CART --> BL_PRODUCT
    
    BL_ORDER --> BL_PRICING
    BL_ORDER --> BL_INVENTORY
    BL_PRODUCT --> BL_PRICING
    
    BL_USER --> DAL_USER
    BL_PRODUCT --> DAL_PRODUCT
    BL_ORDER --> DAL_ORDER
    
    BL_ORDER --> INT_1C
    BL_ORDER --> INT_PAYMENT
    BL_ORDER --> INT_DELIVERY
    BL_INVENTORY --> INT_1C
```

### Обзор системной архитектуры

```mermaid
graph TB
    subgraph "Client Layer"
        WEB[Next.js App]
        MOBILE[Future Mobile App]
        ADMIN_CUSTOM[Custom Admin Dashboard]
        ADMIN_DJANGO[Django Admin Panel]
    end
    
    subgraph "API Gateway Layer (Nginx)"
        NGINX[Nginx + Load Balancer]
        SSL[SSL Termination]
        BASIC_RATE[Basic IP Rate Limiting]
        STATIC[Static Files Serving]
    end
    
    subgraph "BFF Layer (Next.js API)"
        AUTH_BFF[JWT Authentication]
        SMART_RATE[Smart Rate Limiting]
        RBAC[Role-Based Access Control]
        AGGREGATION[Data Aggregation]
    end
    
    subgraph "Application Layer"
        API[Django REST API]
        CELERY[Celery Workers]
        SCHEDULER[Celery Beat]
    end
    
    subgraph "Data Layer"
        PG[(PostgreSQL)]
        REDIS[(Redis Cache)]
        FILES[File Storage]
    end
    
    subgraph "External Integrations"
        ONEC[1C ERP System]
        YUKASSA[YuKassa Payment Gateway]
        DELIVERY[Delivery Services]
    end
    
    WEB --> NGINX
    MOBILE --> NGINX
    ADMIN_CUSTOM --> NGINX
    ADMIN_DJANGO --> NGINX
    
    NGINX --> SSL
    SSL --> BASIC_RATE
    BASIC_RATE --> STATIC
    STATIC --> AUTH_BFF
    
    AUTH_BFF --> SMART_RATE
    SMART_RATE --> RBAC
    RBAC --> AGGREGATION
    AGGREGATION --> API
    
    ADMIN_DJANGO --> API
    
    API --> PG
    API --> REDIS
    API --> FILES
    API --> CELERY
    
    CELERY --> ONEC
    CELERY --> YUKASSA
    CELERY --> DELIVERY
    
    SCHEDULER --> CELERY
```

### Разграничение ответственности по слоям

#### Nginx Gateway Layer:
- **SSL Termination**: Let's Encrypt сертификаты
- **Базовое Rate Limiting**: 1000 запросов/минуту с IP
- **Static Files**: Раздача медиа файлов и статики
- **Load Balancing**: Распределение между инстансами Django
- **DDoS Protection**: Базовая защита от атак

#### Next.js BFF Layer:
- **JWT Authentication**: Валидация токенов и refresh logic
- **Интеллектуальное Rate Limiting**: 
  - 5 попыток логина/минуту для пользователя
  - 10 заказов/день для розничных клиентов
  - Разные лимиты для B2B пользователей
- **Role-Based Access Control**: Проверка ролей и прав доступа
- **Data Aggregation**: Объединение данных от нескольких API endpoints
- **Request/Response трансформация**: Адаптация под frontend нужды

#### Django API Layer:
- **Business Logic**: Основная логика приложения
- **Data Management**: CRUD операции с БД
- **External Integrations**: 1C, платежи, доставка
- **Admin Interface**: Django Admin для контент-менеджмента

### Стратегия админ-панели (гибридный подход)

```
┌─────────────────────────────────────────────────────────┐
│                    ADMIN STRATEGY                       │
├─────────────────────┬───────────────────────────────────┤
│    Django Admin     │      Next.js Custom Admin        │
├─────────────────────┼───────────────────────────────────┤
│ • CRUD товары       │ • Дашборды продаж                │
│ • CRUD категории    │ • Аналитика клиентов              │
│ • Модерация заказов │ • Управление ценами/акциями       │
│ • Управление юзерами│ • Отчеты и визуализация           │
│ • Системные         │ • Мониторинг интеграций           │
│   настройки         │ • UX-критичные операции           │
├─────────────────────┼───────────────────────────────────┤
│ Быстрая разработка  │ Качественный UX                   │
│ Готовые компоненты  │ Кастомная бизнес-логика           │
└─────────────────────┴───────────────────────────────────┘
```

**Обоснование решения:**
- Django Admin для рутинных операций и быстрого прототипирования
- Custom Admin для критичного UX и сложной бизнес-логики
- Единое API, разные интерфейсы

### Механизмы отказоустойчивости

**1С Integration Resilience:**
- **Circuit Breaker Pattern**: Автоматическое переключение на файловый обмен
- **File-based Fallback**: Экспорт заказов в XML/JSON для ручной обработки
- **Retry Logic**: Экспоненциальная задержка для повторных попыток

**Payment Gateway Resilience:**
- **Webhook Validation**: Криптографическая подпись YuKassa
- **Idempotency Keys**: Предотвращение дублирования платежей
- **Status Reconciliation**: Периодическая сверка статусов

**Database Resilience:**
- **Connection Pooling**: pgBouncer для оптимизации подключений
- **Read Replicas**: Масштабирование чтения каталога товаров
- **Backup Strategy**: Ежедневные инкрементальные бэкапы + WAL

### Масштабируемость

**Горизонтальное масштабирование:**
- Django API servers (stateless)
- Celery workers (по типам задач)  
- Read-only replicas PostgreSQL
- Redis Cluster для сессий и кэша

**Вертикальное масштабирование:**
- CPU для обработки изображений
- RAM для кэширования товаров
- Storage для медиа файлов

---
