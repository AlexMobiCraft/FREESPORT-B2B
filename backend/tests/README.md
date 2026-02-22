# Backend Tests - FREESPORT

## Быстрый старт

### Запуск всех тестов
```bash
cd backend
pytest tests/ -v
```

### Запуск конкретной категории
```bash
# Unit тесты
pytest tests/unit/ -v

# Integration тесты
pytest tests/integration/ -v

# Performance тесты
pytest tests/performance/ -v
```

### Запуск с покрытием кода
```bash
pytest --cov=apps --cov-report=html
# Откройте htmlcov/index.html в браузере
```

## Структура тестов

```
tests/
├── conftest.py              # Глобальные фикстуры и фабрики
├── pytest.ini               # Конфигурация pytest (в backend/)
├── unit/                    # Unit тесты
│   ├── test_models/         # Тесты моделей
│   ├── test_serializers/    # Тесты сериализаторов
│   ├── test_filters.py      # Тесты фильтров
│   └── test_search.py       # Тесты поиска
├── integration/             # Integration тесты
│   ├── test_cart_api.py     # API корзины
│   ├── test_order_api.py    # API заказов
│   └── test_catalog_api.py  # API каталога
├── performance/             # Performance тесты
├── fixtures/                # Тестовые данные
├── temp/                    # Временные тесты (не входят в CI)
└── legacy/                  # Устаревшие тесты

```

## Важные документы

- **[TEST_FIXES_GUIDE.md](./TEST_FIXES_GUIDE.md)** - Руководство по исправлению частых проблем
- **[CHANGELOG_TESTS.md](./CHANGELOG_TESTS.md)** - История изменений тестов

## Требования

### Обязательные декораторы

Все тесты, использующие базу данных, **ДОЛЖНЫ** иметь декоратор:

```python
import pytest

@pytest.mark.django_db
def test_something():
    # Ваш тест
    pass
```

### Использование Mock

При работе с Mock-объектами **всегда вызывайте методы**:

```python
# ❌ Неправильно
result = mock_obj.get_status_display
assert result == 'Доставлен'

# ✅ Правильно
result = mock_obj.get_status_display()
assert result == 'Доставлен'
```

### Уникальные значения

Используйте `get_unique_suffix()` для генерации уникальных значений:

```python
from tests.conftest import get_unique_suffix

def test_product_creation():
    suffix = get_unique_suffix()
    product = product_factory.create(
        sku=f"TEST-{suffix}",
        name=f"Test Product {suffix}"
    )
```

## Фикстуры

### Основные фабрики

- `user_factory` - Создание пользователей
- `product_factory` - Создание товаров
- `order_factory` - Создание заказов
- `cart_factory` - Создание корзин
- `category_factory` - Создание категорий
- `brand_factory` - Создание брендов

### Пример использования

```python
@pytest.mark.django_db
def test_order_creation(user_factory, product_factory, order_factory):
    user = user_factory.create()
    product = product_factory.create(stock_quantity=10)
    order = order_factory.create(user=user)
    
    assert order.user == user
```

## Временные тесты

- **Назначение:** быстрые эксперименты и изолированные проверки гипотез, не готовые для основной базы тестов.
- **Расположение:** сохраняйте такие файлы в `backend/tests/temp/`.
- **Запуск:** вручную через `pytest tests/temp/ -v`; каталог исключён из стандартного CI.
- **Уборка:** после подтверждения решения либо перенесите тест в соответствующую категорию, либо удалите.

## Маркеры pytest

- `@pytest.mark.django_db` - Доступ к базе данных
- `@pytest.mark.unit` - Unit тесты
- `@pytest.mark.integration` - Integration тесты
- `@pytest.mark.slow` - Медленные тесты
- `@pytest.mark.api` - API тесты

## Частые проблемы

### 1. Database access not allowed

**Решение:** Добавьте `@pytest.mark.django_db`

### 2. Mock comparison error

**Решение:** Вызывайте методы Mock с `()`

### 3. Duplicate key constraint

**Решение:** Используйте `get_unique_suffix()`

### 4. Database being accessed by other users

**Решение:** Уже исправлено автоматической фикстурой `close_db_connections`

## CI/CD

Тесты автоматически запускаются в GitHub Actions при:
- Push в ветки `main` и `develop`
- Pull Request в эти ветки

Конфигурация: `.github/workflows/backend-ci.yml`

## Покрытие кода

Минимальное требование: **70%**

Проверка покрытия:
```bash
pytest --cov=apps --cov-fail-under=70
```

## Полезные команды

### Запуск конкретного теста
```bash
pytest tests/unit/test_serializers/test_order_serializers.py::TestOrderDetailSerializer::test_serializer_fields -v
```

### Запуск с отладкой
```bash
pytest tests/ -v --pdb
```

### Показать медленные тесты
```bash
pytest tests/ --durations=10
```

### Остановка на первой ошибке
```bash
pytest tests/ -x
```

## Контакты

При возникновении проблем:
1. Проверьте [TEST_FIXES_GUIDE.md](./TEST_FIXES_GUIDE.md)
2. Проверьте [CHANGELOG_TESTS.md](./CHANGELOG_TESTS.md)
3. Обратитесь к команде разработки
