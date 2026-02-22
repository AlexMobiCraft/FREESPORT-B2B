# AI Implementation Guide для FREESPORT

## Обзор

Руководство для AI агентов по работе с существующей кодовой базой FREESPORT. Основано на реальной структуре проекта и существующих паттернах.

## Существующая Структура Проекта

### Backend (Django) - реальная структура:
```
backend/
├── apps/
│   ├── users/          # ✅ Пользователи с ролевой системой
│   ├── products/       # ✅ Каталог товаров с брендами и категориями  
│   ├── cart/           # ✅ Корзина (включает дедупликацию)
│   ├── orders/         # ✅ Система заказов
│   └── common/         # ✅ Общие компоненты
├── freesport/          # ✅ Django settings
└── tests/              # ✅ Тестовая структура
```

### Frontend (Next.js) - реальная структура:
```
frontend/src/
├── app/                # ✅ Next.js App Router
│   ├── (auth)/         # ✅ Группированные routes
│   ├── api/            # ✅ API routes
│   └── catalog/        # ✅ Каталог товаров
├── components/         # ✅ React компоненты
│   ├── ui/             # ✅ Базовые UI компоненты (Button и др.)
│   ├── layout/         # ✅ Layout компоненты
│   └── forms/          # ✅ Формы
└── types/              # ✅ TypeScript типы
```

## Существующие Паттерны (используйте их!)

### 1. Django Models (apps/products/models.py)

**Реальный пример из кодабазы:**
```python
class Brand(models.Model):
    """Модель бренда товаров"""
    
    name = models.CharField("Название бренда", max_length=100, unique=True)
    slug = models.SlugField("Slug", max_length=255, unique=True)
    logo = models.ImageField("Логотип", upload_to="brands/", blank=True)
    description = models.TextField("Описание", blank=True)
    website = models.URLField("Веб-сайт", blank=True)
    is_active = models.BooleanField("Активный", default=True)
    created_at = models.DateTimeField("Дата создания", auto_now_add=True)
    updated_at = models.DateTimeField("Дата обновления", auto_now=True)

    class Meta:
        verbose_name = "Бренд"
        verbose_name_plural = "Бренды"
        db_table = "brands"  # 👈 Используют кастомные имена таблиц

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)  # 👈 Авто-генерация slug
        super().save(*args, **kwargs)
```

**Паттерн для новых моделей:**
```python
class YourModel(models.Model):
    """Описание вашей модели"""
    
    # Обязательные поля (следуйте паттерну проекта)
    name = models.CharField("Название", max_length=255)
    is_active = models.BooleanField("Активный", default=True)
    created_at = models.DateTimeField("Дата создания", auto_now_add=True)
    updated_at = models.DateTimeField("Дата обновления", auto_now=True)
    
    class Meta:
        verbose_name = "Ваша модель"
        verbose_name_plural = "Ваши модели"
        db_table = "your_table_name"  # 👈 Кастомное имя таблицы
        ordering = ['-created_at']    # 👈 Сортировка по умолчанию
```

### 2. Django Serializers (apps/products/serializers.py)

**Реальный паттерн из кодабазы:**
```python
class ProductImageSerializer(serializers.ModelSerializer):
    """Serializer для изображений товара"""
    url = serializers.SerializerMethodField()  # 👈 Кастомные поля
    
    class Meta:
        model = ProductImage
        fields = ['url', 'alt_text', 'is_main', 'sort_order']
    
    def get_url(self, obj):
        """Получить URL изображения с учетом контекста запроса"""
        if isinstance(obj, dict):  # 👈 Обработка dict и model объектов
            return obj.get('url', '')
        
        if hasattr(obj, 'url'):
            url = obj.url
        elif hasattr(obj, 'image') and hasattr(obj.image, 'url'):
            url = obj.image.url
        else:
            return ''
```

### 3. Django ViewSets (apps/products/views.py)

**Реальный паттерн из кодабазы:**
```python
from rest_framework import viewsets, permissions, filters
from rest_framework.pagination import PageNumberPagination
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import extend_schema, OpenApiParameter  # 👈 OpenAPI docs

class CustomPageNumberPagination(PageNumberPagination):  # 👈 Кастомная пагинация
    page_size_query_param = 'page_size'

class ProductViewSet(viewsets.ReadOnlyModelViewSet):  # 👈 ReadOnly для каталога
    """ViewSet для товаров с фильтрацией и ролевым ценообразованием"""
    
    permission_classes = [permissions.AllowAny]
    pagination_class = CustomPageNumberPagination
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_class = ProductFilter  # 👈 Кастомные фильтры
    search_fields = ['name', 'description']
    
    @extend_schema(  # 👈 OpenAPI документация
        description="Получить список товаров с фильтрацией",
        parameters=[
            OpenApiParameter(name='category', description='ID категории', type=int),
        ]
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)
```

### 4. User Model (apps/users/models.py)

**Специфика проекта - кастомная User модель:**
```python
class UserManager(BaseUserManager):
    """Кастомный менеджер с email аутентификацией"""
    
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError("Email обязателен для создания пользователя")
        # ... реализация

class User(AbstractUser):
    """Кастомная модель пользователя с ролевой системой"""
    
    # 👈 В проекте используется email вместо username
    username = None  # Отключаем username
    email = models.EmailField("Email", unique=True)
    
    # 👈 Ролевая система B2B/B2C
    ROLE_CHOICES = [
        ('retail', 'Розничный покупатель'),
        ('wholesale_level1', 'Оптовик уровень 1'),
        ('wholesale_level2', 'Оптовик уровень 2'),
        ('wholesale_level3', 'Оптовик уровень 3'),
        ('trainer', 'Тренер'),
        ('federation_rep', 'Представитель федерации'),
        ('admin', 'Администратор'),
    ]
    role = models.CharField("Роль", max_length=20, choices=ROLE_CHOICES, default='retail')
    
    USERNAME_FIELD = 'email'  # 👈 Аутентификация по email
    REQUIRED_FIELDS = []
```

### 5. Frontend Components (components/ui/Button.tsx)

**Реальный паттерн UI компонента:**
```typescript
import React from 'react';
import type { BaseComponentProps } from '@/types';  // 👈 Общие типы

interface ButtonProps extends BaseComponentProps {
  variant?: 'primary' | 'secondary' | 'outline' | 'ghost' | 'danger';
  size?: 'sm' | 'md' | 'lg';
  disabled?: boolean;
  loading?: boolean;  // 👈 Поддержка loading состояния
  type?: 'button' | 'submit' | 'reset';
  onClick?: (event: React.MouseEvent<HTMLButtonElement>) => void;
}

const Button: React.FC<ButtonProps> = ({
  children,
  className = '',
  variant = 'primary',
  size = 'md',
  disabled = false,
  loading = false,
  type = 'button',
  onClick,
  ...props  // 👈 Spread остальных props
}) => {
  // 👈 Используют Tailwind CSS классы
  const baseStyles = 'inline-flex items-center justify-center font-medium rounded-lg transition-all duration-200 focus:outline-none focus:ring-2 focus:ring-offset-2 disabled:opacity-50 disabled:cursor-not-allowed';
  
  const variantStyles = {
    primary: 'bg-blue-600 text-white hover:bg-blue-700 focus:ring-blue-500',
    secondary: 'bg-gray-600 text-white hover:bg-gray-700 focus:ring-gray-500',
    // ... остальные варианты
  };
  
  // 👈 Динамическая сборка классов
  const buttonClasses = [
    baseStyles,
    variantStyles[variant],
    sizeStyles[size],
    loading && 'cursor-wait',
    className,
  ].filter(Boolean).join(' ');
  
  return (
    <button
      type={type}
      className={buttonClasses}
      disabled={disabled || loading}
      onClick={onClick}
      {...props}
    >
      {loading && (
        // 👈 SVG spinner для loading состояния
        <svg className="-ml-1 mr-2 h-4 w-4 animate-spin" ...>
          {/* SVG content */}
        </svg>
      )}
      {children}
    </button>
  );
};
```

## Специфика Проекта FREESPORT

### 1. Ролевое Ценообразование

**Использование в products/models.py:**
```python
class Product(models.Model):
    # 👈 Разные цены для разных ролей пользователей
    retail_price = models.DecimalField("Розничная цена", max_digits=10, decimal_places=2)
    opt1_price = models.DecimalField("Оптовая цена 1", max_digits=10, decimal_places=2, null=True)
    opt2_price = models.DecimalField("Оптовая цена 2", max_digits=10, decimal_places=2, null=True)
    opt3_price = models.DecimalField("Оптовая цена 3", max_digits=10, decimal_places=2, null=True)
    trainer_price = models.DecimalField("Цена для тренеров", max_digits=10, decimal_places=2, null=True)
    federation_price = models.DecimalField("Цена для федераций", max_digits=10, decimal_places=2, null=True)
    
    def get_price_for_user(self, user):
        """Получить цену товара для конкретного пользователя"""
        price_map = {
            'retail': self.retail_price,
            'wholesale_level1': self.opt1_price or self.retail_price,
            'wholesale_level2': self.opt2_price or self.retail_price,
            'wholesale_level3': self.opt3_price or self.retail_price,
            'trainer': self.trainer_price or self.retail_price,
            'federation_rep': self.federation_price or self.retail_price,
        }
        return price_map.get(user.role, self.retail_price)
```

### 2. Дедупликация в Корзине (apps/cart/)

**Существующий паттерн:**
```python
# Корзина использует unique_together для предотвращения дубликатов
class CartItem(models.Model):
    cart = models.ForeignKey(Cart, related_name='items', on_delete=models.CASCADE)
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1)
    
    class Meta:
        unique_together = ('cart', 'product')  # 👈 Один товар = одна позиция
```

### 3. Тестирование (следуйте существующим паттернам)

**Структура тестов (уже существует):**
```python
# tests/unit/ - Unit тесты
# tests/integration/ - Интеграционные тесты
# frontend/src/components/__tests__/ - Frontend тесты
```

## Шаблоны для AI Агентов

### Создание нового Django App

```bash
# 1. Создать приложение
cd backend/apps
python ../manage.py startapp your_app_name

# 2. Добавить в INSTALLED_APPS
'apps.your_app_name',

# 3. Создать базовые файлы по паттерну существующих apps
```

### Создание нового React Компонента

```typescript
// src/components/YourComponent/YourComponent.tsx
import React from 'react';
import type { BaseComponentProps } from '@/types';

interface YourComponentProps extends BaseComponentProps {
  // ваши props
}

const YourComponent: React.FC<YourComponentProps> = ({
  className = '',
  children,
  ...props
}) => {
  return (
    <div className={`your-base-classes ${className}`} {...props}>
      {children}
    </div>
  );
};

export default YourComponent;

// src/components/YourComponent/index.ts
export { default } from './YourComponent';
export type { YourComponentProps } from './YourComponent';
```

## Важные Принципы

### 1. Следуйте существующим соглашениям:
- ✅ Русские verbose_name в моделях Django
- ✅ db_table для кастомных имен таблиц  
- ✅ Tailwind CSS для стилизации
- ✅ TypeScript типы для всех компонентов
- ✅ drf-spectacular для API документации

### 2. Используйте существующие компоненты:
- ✅ `Button` из `components/ui/Button.tsx`
- ✅ Layout компоненты из `components/layout/`
- ✅ Базовые типы из `@/types`

### 3. Тестирование:
- ✅ Все новые компоненты должны иметь тесты
- ✅ Backend тесты в `tests/unit/` и `tests/integration/`
- ✅ Frontend тесты в `__tests__/` рядом с компонентами

### 4. API Документация:
- ✅ Используйте `@extend_schema` для всех ViewSet методов
- ✅ Добавляйте описания и примеры

## Команды для Разработки

**Используйте существующий Makefile:**
```bash
make up          # Запуск development среды
make test        # Запуск всех тестов
make shell       # Shell в backend контейнере
make migrate     # Применить миграции
make lint        # Проверка кода
```

## Checklist для AI Агентов

### Перед началом работы:
- [ ] Изучил существующий код в соответствующем app
- [ ] Понял паттерны именования и структуру
- [ ] Проверил существующие компоненты, которые можно переиспользовать
- [ ] Понял ролевую систему пользователей (если релевантно)

### Во время разработки:
- [ ] Следую существующим naming conventions
- [ ] Добавляю русские verbose_name для моделей Django
- [ ] Использую существующие UI компоненты
- [ ] Создаю тесты для нового функционала
- [ ] Добавляю OpenAPI документацию к ViewSet

### После завершения:
- [ ] Все тесты проходят (`make test`)
- [ ] Код отформатирован (`make lint`)
- [ ] Миграции созданы (если нужно)
- [ ] Документация обновлена

Этот guide основан на реальной структуре проекта FREESPORT и поможет AI агентам работать эффективно с существующей кодовой базой!