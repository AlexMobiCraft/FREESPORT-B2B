# Стандарты кодирования FREESPORT

## Общие принципы

### Архитектурные принципы

- **API-First подход**: Все функции должны быть доступны через API перед созданием UI
- **Separation of Concerns**: Четкое разделение бизнес-логики, представления и доступа к данным  
- **DRY (Don't Repeat Yourself)**: Избегать дублирования кода через переиспользуемые компоненты
- **SOLID принципы**: Следование принципам объектно-ориентированного программирования
- **12-Factor App**: Соблюдение принципов для современных веб-приложений

### Безопасность

- **НИКОГДА** не включать секреты, ключи API или пароли в код
- **НИКОГДА** не коммитить конфиденциальные данные в репозиторий
- Использовать переменные окружения для конфигурации
- Валидировать все пользовательские данные
- Следовать принципу наименьших привилегий

## Backend (Django)

### Стиль кода Python

#### Форматирование

- **Black** для автоматического форматирования кода
- **Длина строки**: 88 символов (стандарт Black)
- **Кодировка**: UTF-8 для всех файлов

```bash
# Форматирование кода
black .

# Проверка без изменений
black --check .
```

#### Импорты

- **isort** для сортировки импортов
- Порядок импортов:
  1. Стандартная библиотека Python
  2. Сторонние пакеты
  3. Django импорты
  4. Локальные импорты приложения

```python
# Правильный порядок импортов
import json
import logging
from datetime import datetime

import requests
from django.db import models
from django.contrib.auth import get_user_model
from rest_framework import serializers

from apps.common.models import BaseModel
from .utils import calculate_price
```

#### Линтинг

- **Flake8** для проверки стиля кода
- Настройки в `backend/.flake8` или `setup.cfg`

```bash
# Проверка линтером
flake8 apps/
```

#### Типизация

- **mypy** для статической проверки типов
- Обязательная типизация для всех публичных методов
- Настройки в `backend/mypy.ini`

```python
from typing import Dict, List, Optional, Union
from django.http import JsonResponse

def get_user_data(user_id: int) -> Optional[Dict[str, Union[str, int]]]:
    """Получает данные пользователя по ID."""
    try:
        user = User.objects.get(id=user_id)
        return {
            'id': user.id,
            'username': user.username,
            'email': user.email,
        }
    except User.DoesNotExist:
        return None
```

### Архитектура Django приложений

#### Структура приложений

```text
apps/
├── users/          # Пользователи и аутентификация
├── products/       # Каталог товаров
├── orders/         # Система заказов  
├── cart/          # Корзина покупок
└── common/        # Общие компоненты
```

#### Модели (Models)

```python
from django.db import models
from apps.common.models import BaseModel

class Product(BaseModel):
    """Модель товара."""
    
    name = models.CharField(max_length=255, verbose_name="Название")
    slug = models.SlugField(max_length=255, unique=True)
    description = models.TextField(blank=True, verbose_name="Описание")
    
    # Многоуровневое ценообразование
    retail_price = models.DecimalField(max_digits=10, decimal_places=2)
    opt1_price = models.DecimalField(max_digits=10, decimal_places=2, null=True)
    
    class Meta:
        verbose_name = "Товар"
        verbose_name_plural = "Товары"
        ordering = ['name']
        
    def __str__(self) -> str:
        return self.name
        
    @property
    def is_in_stock(self) -> bool:
        """Проверяет наличие товара на складе."""
        return self.stock_quantity > 0
```

#### Сериализаторы (Serializers)

```python
from rest_framework import serializers
from .models import Product

class ProductSerializer(serializers.ModelSerializer):
    """Сериализатор товара."""
    
    is_in_stock = serializers.ReadOnlyField()
    
    class Meta:
        model = Product
        fields = ['id', 'name', 'slug', 'description', 'retail_price', 'is_in_stock']
        read_only_fields = ['id', 'created_at', 'updated_at']
        
    def validate_retail_price(self, value):
        """Валидация розничной цены."""
        if value <= 0:
            raise serializers.ValidationError("Цена должна быть положительной")
        return value
```

#### Представления (Views)

```python
from rest_framework import viewsets, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend

class ProductViewSet(viewsets.ModelViewSet):
    """ViewSet для управления товарами."""
    
    queryset = Product.objects.all()
    serializer_class = ProductSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['category', 'brand']
    
    @action(detail=True, methods=['get'])
    def stock_status(self, request, pk=None):
        """Получить статус наличия товара."""
        product = self.get_object()
        return Response({
            'in_stock': product.is_in_stock,
            'quantity': product.stock_quantity
        })
```

### Тестирование

#### Стратегия тестирования

- **Пирамида тестирования**: Unit > Integration > E2E
- **Покрытие кода**: минимум 70%, критические модули 90%
- **Изоляция тестов**: каждый тест должен быть независимым

#### Структура тестов

```python
import pytest
from django.test import TestCase
from apps.products.models import Product

@pytest.mark.unit
class TestProductModel(TestCase):
    """Тесты модели Product."""
    
    def setUp(self):
        """Настройка тестовых данных."""
        self.product = Product.objects.create(
            name="Test Product",
            slug="test-product",
            retail_price=100.00
        )
    
    def test_str_representation(self):
        """Тест строкового представления модели."""
        self.assertEqual(str(self.product), "Test Product")
        
    def test_is_in_stock_property(self):
        """Тест свойства is_in_stock."""
        self.product.stock_quantity = 5
        self.assertTrue(self.product.is_in_stock)
```

## Frontend (Next.js)

### Стиль кода TypeScript

#### ESLint конфигурация

```javascript
// eslint.config.mjs
import { dirname } from "path";
import { fileURLToPath } from "url";
import { FlatCompat } from "@eslint/eslintrc";

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

const compat = new FlatCompat({
  baseDirectory: __dirname,
});

const eslintConfig = [
  ...compat.extends("next/core-web-vitals", "next/typescript"),
];

export default eslintConfig;
```

#### TypeScript стандарты

```typescript
// Строгая типизация
interface User {
  id: number;
  username: string;
  email: string;
  role: 'retail' | 'wholesale_level1' | 'wholesale_level2' | 'wholesale_level3' | 'trainer' | 'federation_rep' | 'admin';
}

interface Product {
  id: number;
  name: string;
  slug: string;
  retail_price: number;
  opt1_price?: number;
  is_in_stock: boolean;
}

// React компонент с типизацией
interface ProductCardProps {
  product: Product;
  onAddToCart: (productId: number) => void;
}

const ProductCard: React.FC<ProductCardProps> = ({ product, onAddToCart }) => {
  const handleAddToCart = () => {
    onAddToCart(product.id);
  };

  return (
    <div className="product-card">
      <h3>{product.name}</h3>
      <p>Цена: {product.retail_price} ₽</p>
      {product.is_in_stock && (
        <button onClick={handleAddToCart}>В корзину</button>
      )}
    </div>
  );
};
```

#### Zustand Store

```typescript
// stores/cartStore.ts
import { create } from 'zustand';

interface CartItem {
  productId: number;
  quantity: number;
  price: number;
}

interface CartState {
  items: CartItem[];
  addItem: (productId: number, price: number) => void;
  removeItem: (productId: number) => void;
  clearCart: () => void;
  totalAmount: number;
}

export const useCartStore = create<CartState>((set, get) => ({
  items: [],
  
  addItem: (productId: number, price: number) => {
    set((state) => {
      const existingItem = state.items.find(item => item.productId === productId);
      
      if (existingItem) {
        return {
          items: state.items.map(item =>
            item.productId === productId 
              ? { ...item, quantity: item.quantity + 1 }
              : item
          )
        };
      }
      
      return {
        items: [...state.items, { productId, quantity: 1, price }]
      };
    });
  },
  
  removeItem: (productId: number) => {
    set((state) => ({
      items: state.items.filter(item => item.productId !== productId)
    }));
  },
  
  clearCart: () => set({ items: [] }),
  
  get totalAmount() {
    return get().items.reduce((total, item) => total + (item.price * item.quantity), 0);
  }
}));
```

### Стилизация (Tailwind CSS)

#### Соглашения по классам

```typescript
// Использование cn() для условных классов
import { cn } from '@/lib/utils';

interface ButtonProps {
  variant?: 'primary' | 'secondary' | 'danger';
  size?: 'sm' | 'md' | 'lg';
  disabled?: boolean;
  children: React.ReactNode;
}

const Button: React.FC<ButtonProps> = ({ 
  variant = 'primary', 
  size = 'md', 
  disabled = false, 
  children 
}) => {
  return (
    <button
      className={cn(
        // Базовые стили
        'rounded-lg font-medium transition-colors focus:outline-none focus:ring-2',
        
        // Варианты
        {
          'bg-blue-600 text-white hover:bg-blue-700 focus:ring-blue-500': variant === 'primary',
          'bg-gray-600 text-white hover:bg-gray-700 focus:ring-gray-500': variant === 'secondary',
          'bg-red-600 text-white hover:bg-red-700 focus:ring-red-500': variant === 'danger',
        },
        
        // Размеры
        {
          'px-3 py-1.5 text-sm': size === 'sm',
          'px-4 py-2 text-base': size === 'md',
          'px-6 py-3 text-lg': size === 'lg',
        },
        
        // Состояния
        {
          'opacity-50 cursor-not-allowed': disabled,
        }
      )}
      disabled={disabled}
    >
      {children}
    </button>
  );
};
```

### Тестирование (Jest + React Testing Library)

```typescript
// __tests__/components/ProductCard.test.tsx
import { render, screen, fireEvent } from '@testing-library/react';
import { ProductCard } from '@/components/ProductCard';

const mockProduct = {
  id: 1,
  name: 'Test Product',
  slug: 'test-product',
  retail_price: 100,
  is_in_stock: true,
};

describe('ProductCard', () => {
  const mockOnAddToCart = jest.fn();

  beforeEach(() => {
    mockOnAddToCart.mockClear();
  });

  it('renders product information correctly', () => {
    render(
      <ProductCard product={mockProduct} onAddToCart={mockOnAddToCart} />
    );

    expect(screen.getByText('Test Product')).toBeInTheDocument();
    expect(screen.getByText('Цена: 100 ₽')).toBeInTheDocument();
  });

  it('calls onAddToCart when button is clicked', () => {
    render(
      <ProductCard product={mockProduct} onAddToCart={mockOnAddToCart} />
    );

    const addButton = screen.getByText('В корзину');
    fireEvent.click(addButton);

    expect(mockOnAddToCart).toHaveBeenCalledWith(1);
  });

  it('does not show add to cart button when out of stock', () => {
    const outOfStockProduct = { ...mockProduct, is_in_stock: false };
    
    render(
      <ProductCard product={outOfStockProduct} onAddToCart={mockOnAddToCart} />
    );

    expect(screen.queryByText('В корзину')).not.toBeInTheDocument();
  });
});
```

## Команды разработки

### Backend команды

```bash
# Форматирование и линтинг
black .
isort .
flake8 apps/
mypy apps/

# Тестирование
pytest                       # Все тесты
pytest -m unit              # Unit-тесты
pytest -m integration       # Интеграционные тесты
pytest --cov=apps           # С покрытием кода

# Django команды
python manage.py runserver 8001
python manage.py makemigrations
python manage.py migrate
python manage.py shell
```

### Frontend команды

```bash
# Разработка
npm run dev                 # Запуск dev сервера
npm run build              # Сборка продакшена
npm run start              # Запуск продакшена
npm run lint               # ESLint проверка

# Тестирование
npm run test               # Запуск тестов
npm run test:watch         # Тесты в watch режиме
npm run test:coverage      # Тесты с покрытием
```

## Git Workflow

### Структура веток

- **main** - продакшен ветка (защищена)
- **develop** - основная ветка разработки (защищена)
- **feature/*** - ветки для новых функций
- **hotfix/*** - ветки для критических исправлений

### Commit сообщения

```text
type(scope): краткое описание

Более детальное описание изменений, если необходимо.

- Список изменений
- Можно в виде списка

Fixes #123
```

Типы commit'ов:

- **feat**: новая функция
- **fix**: исправление бага
- **docs**: изменения в документации
- **style**: форматирование, без изменения логики
- **refactor**: рефакторинг кода
- **test**: добавление или изменение тестов
- **chore**: обновление сборки или вспомогательных инструментов

### Pull Request процесс

1. Создать feature ветку от develop
2. Реализовать функцию с тестами
3. Убедиться что все тесты проходят
4. Создать Pull Request в develop
5. Code Review от коллег
6. Merge после одобрения

## Мониторинг качества кода

### Автоматизация

- **GitHub Actions** для CI/CD
- Автоматический запуск тестов при PR
- Проверка покрытия кода
- Линтинг и форматирование

### Метрики качества

- **Покрытие тестами**: минимум 70%
- **Cyclomatic Complexity**: максимум 10
- **Технический долг**: отслеживание через SonarQube
- **Performance**: мониторинг времени отклика AP
