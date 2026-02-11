# 4. Структура Компонентов

### Frontend Architecture (Next.js 14+)

#### Компонентная архитектура

```
frontend/src/
├── app/                          # App Router (Next.js 13+)
│   ├── (auth)/                   # Route groups
│   ├── catalog/
│   ├── product/[id]/
│   ├── admin/                    # Административные маршруты
│   └── api/                      # API Routes (BFF)
├── components/                   # React компоненты
│   ├── ui/                       # Базовые UI компоненты
│   │   ├── Button/
│   │   ├── Input/
│   │   ├── Modal/
│   │   └── Toast/
│   ├── business/                 # Бизнес-логика компоненты
│   │   ├── ProductCard/
│   │   ├── Cart/
│   │   ├── Checkout/
│   │   └── B2BVerification/
│   ├── admin/                    # Административные компоненты
│   │   ├── Dashboard/
│   │   ├── ApplicationModeration/
│   │   ├── Integration1CMonitor/
│   │   └── UserManagement/
│   └── layout/                   # Лейаут компоненты
│       ├── Header/
│       ├── Navigation/
│       └── Footer/
├── hooks/                        # Custom React hooks
├── services/                     # API сервисы
├── stores/                       # State management (Zustand)
├── types/                        # TypeScript типы
└── utils/                        # Утилиты
```

#### UI Component Library (согласно front-end-spec.md)

**Базовые компоненты:**
```typescript
// Кнопки с B2B/B2C вариантами
interface ButtonProps {
  variant: 'primary' | 'secondary' | 'outline' | 'ghost' | 'b2b-bulk' | 'danger'
  size: 'xs' | 'sm' | 'md' | 'lg' | 'xl'
  mode: 'b2c' | 'b2b' | 'universal'
}

// Карточки товаров с ролевым ценообразованием  
interface ProductCardProps {
  mode: 'b2c' | 'b2b'
  layout: 'grid' | 'list' | 'compact'
  product: Product
  showRRP?: boolean // Для B2B пользователей
  showMSRP?: boolean // Для B2B пользователей
}

// Фильтры и сортировка
interface SortOptionsProps {
  options: SortOption[]
  currentSort: string
  mode: 'b2c' | 'b2b'
}
```

**Административные компоненты:**
```typescript
// Дашборд админ-панели
interface AdminDashboardProps {
  kpis: KPIData
  alerts: AlertItem[]
  integrationStatus: Integration1CStatus
  systemMetrics: SystemMetrics
}

// Модерация B2B заявок
interface ModerationListProps {
  applications: B2BApplication[]
  filters: ModerationFilters
  onApprove: (id: string, role: UserRole) => void
  onReject: (id: string, reason: string) => void
}

// Мониторинг интеграции с 1С
interface Integration1CMonitorProps {
  status: CircuitBreakerStatus
  syncHistory: SyncLogEntry[]
  onManualSync: (type: SyncType) => void
}
```

### Backend Architecture (Django + DRF)

#### Модульная структура приложений

```
backend/
├── apps/                             # Django приложения
│   ├── users/                        # Управление пользователями
│   │   ├── views/                    # ✅ Модульная структура views (Story 2.3)
│   │   │   ├── __init__.py           # Экспорт для совместимости
│   │   │   ├── authentication.py     # UserRegistrationView, UserLoginView
│   │   │   ├── profile.py            # UserProfileView
│   │   │   ├── misc.py               # user_roles_view
│   │   │   └── personal_cabinet.py   # Dashboard, Addresses, Favorites, Orders
│   │   ├── models.py                 # User, Company, Address, Favorite
│   │   ├── serializers.py            # DRF serializers с валидацией
│   │   ├── urls.py                   # Router с ViewSets
│   │   ├── migrations/               # Database migrations
│   │   └── admin.py                  # Django admin
│   ├── products/                     # Каталог товаров
│   │   ├── models.py                 # Product, Category, Brand, ImportSession
│   │   ├── views.py                  # API endpoints каталога
│   │   ├── serializers.py            # Роле-ориентированное ценообразование
│   │   ├── filters.py                # Фильтрация и поиск
│   │   ├── services/                 # Сервисы для импорта и обработки данных
│   │   │   ├── __init__.py           # Инициализация модуля сервисов
│   │   │   ├── parser.py             # XMLDataParser для парсинга файлов 1С
│   │   │   └── processor.py          # ProductDataProcessor для обработки данных
│   │   └── management/               # Management команды
│   │       └── commands/             # Django management команды
│   │           ├── load_test_catalog.py  # Генерация тестовых данных
│   │           ├── load_catalog.py       # Импорт реальных данных из XML
│   │           └── backup_db.py          # Создание резервных копий БД
│   ├── orders/                       # Система заказов
│   │   ├── models.py                 # Order, OrderItem
│   │   ├── views.py                  # Checkout, order management
│   │   └── tasks.py                  # Celery tasks для интеграции
│   ├── cart/                         # Корзина покупок
│   │   ├── models.py                 # Cart, CartItem
│   │   └── views.py                  # Session-based cart
│   └── common/                       # Общие компоненты
│       ├── permissions.py            # Custom permissions
│       ├── pagination.py             # Стандартизированная пагинация
│       ├── exceptions.py             # Обработка ошибок
│       └── utils.py                  # Общие утилиты
├── freesport/                        # Django настройки
│   ├── settings/                     # Модульные настройки
│   │   ├── base.py                   # OpenAPI 3.1, JWT, DRF
│   │   ├── development.py            # Dev настройки
│   │   └── production.py             # Production конфигурация
│   ├── urls.py                       # Root URL configuration
│   └── wsgi.py                       # WSGI application
├── requirements.txt                  # Python dependencies
├── TODO_TEMPORARY_FIXES.md           # ✅ Документация временных заглушек
└── manage.py                         # Django CLI
```

#### Security & Rate Limiting

**Django Admin Rate Limiting Strategy:**

Для Django Admin применяется встроенная защита Django + дополнительные меры:

1. **Django встроенная защита:**
   - CSRF protection (включен по умолчанию)
   - Session-based authentication с timeout
   - Permission-based access control

2. **Rate Limiting подход (для будущей реализации):**
   - **Уровень приложения:** Django-ratelimit middleware для ограничения запросов к admin endpoints
   - **Уровень веб-сервера:** Nginx rate limiting для защиты от DDoS
   - **Рекомендуемые лимиты:**
     - Admin login: 5 попыток / 5 минут
     - Bulk actions: 10 операций / минуту
     - API endpoints: 100 запросов / минуту

3. **Текущая реализация (MVP):**
   - Permissions check на уровне admin actions (`@admin.action(permissions=['users.change_user'])`)
   - Input validation для предотвращения некорректных массовых операций
   - AuditLog для отслеживания всех критичных действий

4. **Планируемые улучшения:**
   - Интеграция django-ratelimit для admin endpoints
   - Мониторинг подозрительной активности через AuditLog
   - Автоматическая блокировка IP при превышении лимитов

#### Views Architecture Pattern (Реализовано в Story 2.3)

**Модульная организация views для масштабируемости:**

```python
