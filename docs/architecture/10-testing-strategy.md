# 10. Стратегия Тестирования

## 10.1. Философия и принципы тестирования

### Пирамида тестирования

```text
                  E2E Tests (Playwright)
                 /        \
        Integration Tests (Pytest + APIClient)
               /            \
      Backend Unit Tests (Pytest)  Frontend Unit (Jest)
```

**Testing Philosophy:** Стратегия тестирования FREESPORT основана на классической пирамиде тестирования с упором на быстрые unit-тесты в основании и критически важные E2E тесты на вершине. Особое внимание уделяется полной изоляции тестов и их стабильности.

### Технологический стек тестирования

**Backend:**

- **Основной фреймворк**: `pytest`
- **Интеграция с Django**: `pytest-django`
- **Генерация данных**: `Factory Boy`
- **Мокинг (Mocking)**: `pytest-mock`
- **Изоляция БД**: Транзакционные тесты с автоочисткой

**Frontend:**

- **Jest**: Unit testing framework
- **React Testing Library**: Component testing
- **MSW (Mock Service Worker)**: API mocking
- **Jest Environment**: jsdom для браузерной среды

**E2E:**

- **Playwright**: Primary E2E framework
- **TypeScript**: Type-safe test scripts
- **Page Object Model**: Maintainable test structure
- **Multiple Browsers**: Chrome, Firefox, Safari testing

## 10.2. Организация и структура тестов

### Backend Tests - Детальная структура

```text
backend/
└── tests/
    ├── __init__.py
    ├── conftest.py                 # ✅ Общие фикстуры Pytest (Factory Boy, APIClient)
    │
    ├── unit/                       # ✅ Unit-тесты (быстрые, изолированные)
    │   ├── __init__.py
    │   ├── test_models/            # Тесты моделей
    │   ├── test_serializers/       # Тесты сериализаторов
    │   ├── test_services/          # Тесты сервисов
    │   ├── test_utils/             # Тесты утилит
    │   ├── test_orders.py          # Тесты заказов
    │   ├── test_product_filters.py # Тесты фильтров
    │   └── test_search.py          # Тесты поиска
    │
    ├── integration/                # ✅ Интеграционные тесты
    │   ├── __init__.py
    │   ├── base.py                 # Базовый класс для интеграционных тестов
    │   ├── test_auth_api.py
    │   ├── test_products_api.py    # Тестирование API каталога
    │   ├── test_orders_api.py      # Тестирование API заказов
    │   ├── test_b2b_workflow.py    # B2B workflow тесты
    │   ├── test_b2c_workflow.py    # B2C workflow тесты
    │   ├── test_cart_api.py        # API корзины
    │   ├── test_catalog_api.py     # API каталога
    │   ├── test_search_api.py      # API поиска
    │   └── test_management_commands/ # Тесты management команд
    │
    ├── performance/                # 🆕 Тесты производительности
    │   ├── __init__.py
    │   ├── test_catalog_performance.py
    │   ├── test_order_creation_performance.py
    │   └── test_search_performance.py
    │
    ├── legacy/                     # ⚠️  Устаревшие тесты (НЕ запускаются в CI)
    │   └── .gitkeep               # Пустая директория для будущих устаревших тестов
    │
    └── fixtures/                   # ✅ Статические фикстуры
        ├── __init__.py
        └── images/                 # Тестовые изображения
```

### Frontend Tests - Актуальная структура

```text
frontend/
└── src/
    ├── components/
    │   ├── __tests__/             # Тесты компонентов
    │   │   └── Button.test.tsx    # Пример теста компонента
    │   └── [компоненты].tsx       # Компоненты с тестами рядом
    ├── hooks/
    │   └── [хуки].test.ts         # Тесты хуков рядом с файлами
    ├── services/
    │   └── [сервисы].test.ts      # Тесты сервисов рядом с файлами
    ├── utils/
    │   └── [утилиты].test.ts      # Тесты утилит рядом с файлами
    └── [другие модули]/
        └── [файлы].test.ts        # Тесты рядом с тестируемыми файлами

# Конфигурация тестов:
├── jest.config.js                # Jest конфигурация
├── jest.setup.js                 # Настройка тестовой среды
└── __mocks__/                    # Mock-реализации
    └── .gitkeep
```

### Типы тестов и их назначение

#### 10.2.1. Unit-тесты (`tests/unit/`)

- **Назначение**: Тестирование одного изолированного компонента (модели, сериализатора, сервиса, утилиты)
- **Технологии**: `pytest`, `pytest-mock`
- **Особенности**: НЕ обращаются к базе данных или внешним сервисам
- **Маркировка**: `@pytest.mark.unit`
- **Пример**: Проверка метода модели `Product.can_be_ordered()` возвращает `False` при `stock_quantity = 0`

#### 10.2.2. Интеграционные тесты (`tests/integration/`)

- **Назначение**: Тестирование взаимодействия между несколькими компонентами системы
- **Технологии**: `pytest`, `pytest-django`, `APIClient`, `Factory Boy`
- **Особенности**: Используют тестовую БД, проверяют полный цикл "запрос-ответ" для API
- **Маркировка**: `@pytest.mark.integration`, `@pytest.mark.django_db`
- **Пример**: POST-запрос на `/api/v1/orders/`, проверка создания заказа в БД и корректности ответа

#### 10.2.3. Тесты производительности (`tests/performance/`)

- **Назначение**: Тестирование производительности критичных операций
- **Технологии**: `pytest`, `pytest-benchmark`, `locust`
- **Особенности**: Тестируют время выполнения операций, нагрузочное тестирование
- **Примеры**:
  - Производительность каталога товаров
  - Время создания заказов
  - Скорость поиска

#### 10.2.4. Устаревшие тесты (`tests/legacy/`)

**⚠️ ВАЖНО**:

- Содержит тесты для устаревшего функционала
- **НЕ запускаются** в основном CI-пайплайне: `pytest --ignore=tests/legacy`
- Исключены из отчетов о покрытии кода
- Новые тесты **ЗАПРЕЩЕНО** добавлять в эту директорию
- На данный момент директория пуста (содержит только .gitkeep)

#### E2E Tests - Статус

```text
# В проекте отсутствует директория e2e тестов
# E2E тесты будут добавлены в будущем при необходимости
```

**E2E Testing Stack:**

- **Playwright**: Primary E2E framework
- **TypeScript**: Type-safe test scripts
- **Page Object Model**: Maintainable test structure
- **Multiple Browsers**: Chrome, Firefox, Safari testing

### Примеры тестов

#### Frontend Component Test с ценообразованием по ролям

```typescript
// ProductCard.test.tsx
import { render, screen, fireEvent } from '@testing-library/react';
import { ProductCard } from '../ProductCard';
import { CartProvider } from '../../contexts/CartContext';

const mockProduct = {
  id: 1,
  name: 'Test Product',
  retail_price: 1200,
  opt1_price: 1000,
  trainer_price: 950,
  recommended_retail_price: 1300, // RRP для B2B
  max_suggested_retail_price: 1400, // MSRP для B2B
  main_image: '/test-image.jpg',
  stock_quantity: 50
};

describe('ProductCard', () => {
  it('displays retail pricing for B2C users', () => {
    render(
      <CartProvider>
        <ProductCard product={mockProduct} userRole="retail" />
      </CartProvider>
    );

    expect(screen.getByText('1 200 ₽')).toBeInTheDocument();
    expect(screen.queryByText('РРЦ:')).not.toBeInTheDocument(); // RRP не показывается B2C
    expect(screen.queryByText('Макс. цена:')).not.toBeInTheDocument(); // MSRP не показывается B2C
  });

  it('displays wholesale pricing and RRP/MSRP for B2B users', () => {
    render(
      <CartProvider>
        <ProductCard product={mockProduct} userRole="wholesale_level1" showRRP={true} showMSRP={true} />
      </CartProvider>
    );

    // Показывает оптовую цену как основную
    expect(screen.getByText('1 000 ₽')).toBeInTheDocument();

    // Показывает RRP и MSRP для B2B пользователей (FR5)
    expect(screen.getByText('РРЦ: 1 300 ₽')).toBeInTheDocument();
    expect(screen.getByText('Макс. цена: 1 400 ₽')).toBeInTheDocument();
  });

  it('displays trainer pricing for trainers', () => {
    render(
      <CartProvider>
        <ProductCard product={mockProduct} userRole="trainer" />
      </CartProvider>
    );

    expect(screen.getByText('950 ₽')).toBeInTheDocument();
    expect(screen.getByText('Цена для тренеров')).toBeInTheDocument();
  });
});
```

#### Backend API Test с тестированием ролевого ценообразования

```python
# tests/integration/test_product_api.py
import pytest
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient
from apps.users.factories import UserFactory
from apps.products.factories import ProductFactory

@pytest.mark.django_db
class TestProductAPI:
    """Тестирование Product API с ролевым ценообразованием"""

    def setup_method(self):
        self.client = APIClient()
        self.product = ProductFactory(
            retail_price=1200.00,
            opt1_price=1000.00,
            opt2_price=950.00,
            trainer_price=900.00,
            recommended_retail_price=1300.00,  # RRP для B2B
            max_suggested_retail_price=1400.00,  # MSRP для B2B
            stock_quantity=50
        )
        self.url = reverse('products-detail', kwargs={'pk': self.product.pk})

    def test_retail_user_sees_retail_pricing(self):
        """B2C пользователь видит только розничные цены"""
        user = UserFactory(role='retail')
        self.client.force_authenticate(user=user)

        response = self.client.get(self.url)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        # Видит розничную цену
        assert data['current_user_price'] == '1200.00'

        # Не видит оптовые цены
        assert 'opt1_price' not in data
        assert 'opt2_price' not in data
        assert 'trainer_price' not in data

        # Не видит RRP/MSRP (только для B2B)
        assert 'recommended_retail_price' not in data
        assert 'max_suggested_retail_price' not in data

    def test_wholesale_user_sees_wholesale_pricing_and_rrp_msrp(self):
        """B2B пользователь видит свои цены + RRP/MSRP (FR5)"""
        user = UserFactory(role='wholesale_level2')
        self.client.force_authenticate(user=user)

        response = self.client.get(self.url)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        # Видит свою оптовую цену
        assert data['current_user_price'] == '950.00'

        # Видит RRP и MSRP для принятия решений (FR5)
        assert data['recommended_retail_price'] == '1300.00'
        assert data['max_suggested_retail_price'] == '1400.00'

        # Видит все уровни оптовых цен для сравнения
        assert data['opt1_price'] == '1000.00'
        assert data['opt2_price'] == '950.00'

    def test_trainer_sees_trainer_pricing(self):
        """Тренер видит специальную цену"""
        user = UserFactory(role='trainer')
        self.client.force_authenticate(user=user)

        response = self.client.get(self.url)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        # Видит тренерскую цену
        assert data['current_user_price'] == '900.00'
        assert data['trainer_price'] == '900.00'

@pytest.mark.django_db
class TestCustomerSyncAPI:
    """Тестирование API синхронизации покупателей с 1С"""

    def setup_method(self):
        self.client = APIClient()
        self.sync_url = reverse('onec-customers-list')

    def test_import_customers_from_1c(self):
        """Тестирование импорта покупателей из 1С"""
        # Подготовка данных как от 1С
        customers_data = {
            'customers': [
                {
                    'onec_id': 'CLIENT_001',
                    'onec_guid': '550e8400-e29b-41d4-a716-446655440000',
                    'email': 'client@example.com',
                    'first_name': 'Иван',
                    'last_name': 'Петров',
                    'company_name': 'ООО Спорт',
                    'tax_id': '1234567890',
                    'role': 'wholesale_level2'
                }
            ]
        }

        # Имитируем вызов от 1С системы
        self.client.credentials(HTTP_X_API_KEY='test-1c-api-key')
        response = self.client.post(self.sync_url, customers_data, format='json')

        assert response.status_code == status.HTTP_202_ACCEPTED
        data = response.json()
        assert data['imported_count'] == 1
        assert data['conflicts_count'] == 0

        # Проверяем что пользователь создался
        from apps.users.models import User
        user = User.objects.get(email='client@example.com')
        assert user.onec_id == 'CLIENT_001'
        assert user.role == 'wholesale_level2'
        assert user.company_name == 'ООО Спорт'

    def test_import_handles_conflicts(self):
        """Тестирование обработки конфликтов при импорте"""
        # Создаем существующего пользователя
        existing_user = UserFactory(
            email='conflict@example.com',
            company_name='ООО Старая компания',
            tax_id='1111111111'
        )

        # Импортируем того же пользователя с другими данными
        customers_data = {
            'customers': [
                {
                    'onec_id': 'CLIENT_002',
                    'email': 'conflict@example.com',
                    'first_name': 'Иван',
                    'last_name': 'Петров',
                    'company_name': 'ООО Новая компания',  # Конфликт!
                    'tax_id': '2222222222',  # Конфликт!
                    'role': 'wholesale_level1'
                }
            ]
        }

        self.client.credentials(HTTP_X_API_KEY='test-1c-api-key')
        response = self.client.post(self.sync_url, customers_data, format='json')

        assert response.status_code == status.HTTP_202_ACCEPTED
        data = response.json()
        assert data['conflicts_count'] == 1

        # Проверяем что создалась запись о конфликте
        from apps.common.models import SyncConflict
        conflict = SyncConflict.objects.filter(customer=existing_user).first()
        assert conflict is not None
        assert not conflict.is_resolved
        assert 'company_name' in conflict.conflicting_fields
        assert 'tax_id' in conflict.conflicting_fields
```

#### Integration Test для синхронизации с 1С

```python
# tests/integration/test_1c_sync.py
import pytest
import json
from unittest.mock import patch, Mock
from django.test import TestCase
from apps.common.services import OneCCustomerSyncService
from apps.users.factories import UserFactory

@pytest.mark.django_db
class TestOneCCustomerSync:
    """Интеграционные тесты синхронизации покупателей с 1С"""

    def setup_method(self):
        self.sync_service = OneCCustomerSyncService()

    @patch('apps.common.services.OneCCircuitBreaker.call_1c_api')
    def test_successful_customer_export_to_1c(self, mock_1c_call):
        """Тестирование успешного экспорта покупателя в 1С"""
        # Настраиваем mock ответ от 1С
        mock_1c_call.return_value = {
            'status': 'success',
            'onec_id': 'CLIENT_NEW_001',
            'message': 'Customer created successfully'
        }

        # Создаем B2B пользователя для экспорта
        user = UserFactory(
            role='wholesale_level2',
            company_name='ООО Тест',
            tax_id='1234567890',
            is_verified_b2b=True
        )

        # Экспортируем в 1С
        result = self.sync_service.export_customer_to_1c(user)

        # Проверяем результат
        assert result['status'] == 'success'
        assert result['onec_id'] == 'CLIENT_NEW_001'

        # Проверяем что пользователь обновился
        user.refresh_from_db()
        assert user.onec_id == 'CLIENT_NEW_001'
        assert user.last_sync_to_1c is not None

        # Проверяем что создался лог
        from apps.common.models import CustomerSyncLog
        sync_log = CustomerSyncLog.objects.filter(
            customer=user,
            operation_type='export_to_1c'
        ).first()
        assert sync_log is not None
        assert sync_log.status == 'success'

    @patch('apps.common.services.OneCCircuitBreaker.call_1c_api')
    def test_fallback_to_file_exchange_when_1c_unavailable(self, mock_1c_call):
        """Тестирование fallback к файловому обмену при недоступности 1С"""
        # Настраиваем mock для имитации недоступности 1С
        mock_1c_call.return_value = {
            'status': 'fallback_success',
            'method': 'file',
            'message': 'Exported to XML file for manual processing'
        }

        user = UserFactory(role='wholesale_level1')

        result = self.sync_service.export_customer_to_1c(user)

        # Проверяем что сработал fallback
        assert result['status'] == 'fallback_success'
        assert result['method'] == 'file'

        # Проверяем что создался соответствующий лог
        from apps.common.models import CustomerSyncLog
        sync_log = CustomerSyncLog.objects.filter(customer=user).first()
        assert 'fallback' in sync_log.details.get('method', '')

    def test_conflict_resolution_strategy_selection(self):
        """Тестирование выбора стратегии разрешения конфликтов"""
        platform_data = {
            'email': 'test@example.com',
            'company_name': 'ООО Платформа',
            'tax_id': '1111111111',
            'phone': '+7900123456'
        }

        onec_data = {
            'email': 'test@example.com',
            'company_name': 'ООО 1С Система',  # Конфликт!
            'tax_id': '2222222222',  # Конфликт!
            'phone': '+7900123456'
        }

        from apps.common.services import CustomerSyncConflictResolver
        resolver = CustomerSyncConflictResolver()

        conflicts = resolver._detect_conflicts(platform_data, onec_data)

        # Проверяем обнаружение конфликтов
        assert len(conflicts) == 2
        conflict_fields = [c['field'] for c in conflicts]
        assert 'company_name' in conflict_fields
        assert 'tax_id' in conflict_fields

        # Проверяем определение серьезности
        tax_id_conflict = next(c for c in conflicts if c['field'] == 'tax_id')
        assert tax_id_conflict['severity'] == 'high'

@pytest.mark.django_db
class TestOneCMetricsCollection:
    """Тестирование сбора метрик интеграции с 1С"""

    def test_metrics_collection(self):
        """Тестирование сбора основных метрик"""
        # Создаем тестовые данные для метрик
        from apps.common.models import ImportLog, SyncConflict
        from apps.users.factories import UserFactory

        # Создаем логи импорта
        ImportLog.objects.create(
            import_type='customers',
            status='completed',
            total_records=10,
            successful_records=8,
            failed_records=2
        )

        # Создаем конфликт
        user = UserFactory()
        SyncConflict.objects.create(
            conflict_type='customer_data',
            customer=user,
            platform_data={'test': 'data'},
            onec_data={'test': 'other_data'},
            conflicting_fields=['company_name']
        )

        from apps.common.services import OneCMetricsCollector
        collector = OneCMetricsCollector()

        metrics = collector.collect_sync_metrics()

        # Проверяем собранные метрики
        assert metrics['total_sync_operations'] == 1
        assert metrics['successful_syncs'] == 1
        assert metrics['unresolved_conflicts'] == 1
```

### Тестирование интеграций с внешними системами

#### Mock серверы для разработки

```python
# tests/mocks/onec_mock_server.py
from unittest.mock import Mock
import json

class OneCMockServer:
    """Mock сервер для имитации 1С API в тестах"""

    def __init__(self):
        self.customers_db = {}
        self.orders_db = {}
        self.call_count = 0

    def create_customer(self, customer_data: dict) -> dict:
        """Имитация создания покупателя в 1С"""
        self.call_count += 1
        onec_id = f"MOCK_CLIENT_{self.call_count:03d}"

        self.customers_db[onec_id] = customer_data

        return {
            'status': 'success',
            'onec_id': onec_id,
            'message': 'Customer created successfully'
        }

    def get_customers(self, modified_since: str = None) -> dict:
        """Имитация получения списка покупателей из 1С"""
        customers = list(self.customers_db.values())

        # Фильтрация по дате при необходимости
        if modified_since:
            # В реальной системе здесь была бы фильтрация по дате
            pass

        return {
            'status': 'success',
            'customers': customers,
            'total_count': len(customers)
        }

    def simulate_network_error(self):
        """Имитация сетевой ошибки"""
        raise ConnectionError("Mock network error for testing")

    def simulate_timeout(self):
        """Имитация таймаута"""
        raise TimeoutError("Mock timeout error for testing")

# Использование в тестах
@pytest.fixture
def mock_onec_server():
    return OneCMockServer()

@patch('apps.common.services.requests.post')
def test_1c_integration_with_mock(mock_post, mock_onec_server):
    """Пример использования mock сервера в тестах"""
    # Настраиваем mock
    mock_response = Mock()
    mock_response.json.return_value = mock_onec_server.create_customer({
        'email': 'test@example.com',
        'company_name': 'Test Company'
    })
    mock_response.status_code = 200
    mock_post.return_value = mock_response

    # Выполняем тест
    from apps.common.services import OneCCustomerSyncService
    service = OneCCustomerSyncService()

    user = UserFactory(email='test@example.com')
    result = service.export_customer_to_1c(user)

    assert result['status'] == 'success'
    assert 'MOCK_CLIENT' in result['onec_id']
```

### E2E тесты критических сценариев

```typescript
// e2e/tests/integration/b2b-customer-sync.spec.ts
import { test, expect } from "@playwright/test";

test.describe("B2B Customer Sync Flow", () => {
  test("B2B registration triggers 1C export after verification", async ({
    page,
  }) => {
    // Регистрация B2B пользователя
    await page.goto("/register");
    await page.selectOption("#role", "wholesale_level2");

    await page.fill("#email", "b2b-test@example.com");
    await page.fill("#company_name", "ООО Тест Интеграция");
    await page.fill("#tax_id", "1234567890");
    await page.fill("#password", "SecurePassword123!");

    await page.click('button[type="submit"]');

    // Проверяем что показывается статус ожидания верификации
    await expect(page.locator(".verification-pending")).toBeVisible();
    await expect(page.locator(".verification-pending")).toContainText(
      "На проверке",
    );

    // Имитируем верификацию администратором
    // (в реальном тесте это было бы через API или админ панель)
    await page.goto("/admin/verify-b2b-user/test@example.com");
    await page.click("#approve-user");

    // Проверяем что пользователь получил уведомление
    await page.goto("/profile");
    await expect(page.locator(".verification-status")).toContainText(
      "Верифицирован",
    );

    // Проверяем что запустилась синхронизация с 1С
    await expect(page.locator(".sync-status")).toContainText(
      "Синхронизация с 1С",
    );

    // В реальном тесте здесь проверялся бы лог синхронизации через API
  });

  test("B2B user sees correct pricing after sync", async ({ page }) => {
    // Авторизуемся как B2B пользователь
    await page.goto("/login");
    await page.fill("#email", "wholesale@example.com");
    await page.fill("#password", "password");
    await page.click('button[type="submit"]');

    // Идем в каталог
    await page.goto("/catalog");
    await page.click(".product-card:first-child");

    // Проверяем что отображаются B2B цены
    await expect(page.locator(".wholesale-price")).toBeVisible();
    await expect(page.locator(".rrp-price")).toBeVisible(); // RRP для B2B (FR5)
    await expect(page.locator(".msrp-price")).toBeVisible(); // MSRP для B2B (FR5)

    // Проверяем что не отображается розничная цена
    await expect(page.locator(".retail-price")).not.toBeVisible();

    // Проверяем корректность отображения информационных цен
    const rrpText = await page.locator(".rrp-price").textContent();
    const msrpText = await page.locator(".msrp-price").textContent();

    expect(rrpText).toContain("РРЦ:");
    expect(msrpText).toContain("Макс. цена:");
  });
});
```

### Требования к покрытию тестами

#### Целевые показатели покрытия

```yaml
# .coverage.yml - Требования к покрытию
coverage_targets:
  overall: 70%
  critical_modules: 90%

critical_modules:
  - apps.users.models
  - apps.users.serializers
  - apps.products.models
  - apps.orders.models
  - apps.common.services # Включая 1С интеграцию
  - apps.common.models # CustomerSyncLog, ImportLog, SyncConflict

integration_modules:
  required_coverage: 85%
  modules:
    - apps.common.services.onec_sync
    - apps.common.services.conflict_resolver
    - apps.users.serializers # B2B/B2C разделение
    - apps.products.views # Ролевое ценообразование
```

#### Обязательные тестовые сценарии

**Для интеграции с 1С:**

1. ✅ Успешный импорт покупателей из 1С
2. ✅ Обработка конфликтов данных при импорте
3. ✅ Экспорт новых B2B регистраций в 1С
4. ✅ Fallback к файловому обмену при недоступности 1С
5. ✅ Circuit breaker behavior при ошибках 1С
6. ✅ Разрешение конфликтов различными стратегиями

**Для ролевого ценообразования:**

1. ✅ B2C пользователи видят только retail цены
2. ✅ B2B пользователи видят свои цены + RRP/MSRP (FR5)
3. ✅ Тренеры видят специальные цены
4. ✅ Админы видят все цены
5. ✅ Анонимные пользователи видят retail цены

### Continuous Testing в CI/CD

```yaml
# .github/workflows/test.yml - Фрагмент
test_matrix:
  unit_tests:
    - backend_unit_tests
    - frontend_unit_tests

  integration_tests:
    - api_integration_tests
    - 1c_integration_mocks
    - database_integration_tests

  e2e_tests:
    - critical_user_flows
    - b2b_registration_flow
    - pricing_verification_flow

  performance_tests:
    - 1c_sync_performance
    - api_response_times
    - database_query_performance

success_criteria:
  unit_tests: 100% pass
  integration_tests: 100% pass
  e2e_tests: 95% pass (допустимы flaky tests)
  coverage: >= 70% overall, >= 90% critical modules
```

### Мониторинг качества тестов

```python
# tests/quality/test_coverage_requirements.py
import pytest
from coverage import Coverage

class TestCoverageRequirements:
    """Проверка соблюдения требований к покрытию тестами"""

    def test_critical_modules_coverage_above_90_percent(self):
        """Критичные модули должны иметь покрытие >= 90%"""
        cov = Coverage()
        cov.load()

        critical_modules = [
            'apps.users.models',
            'apps.common.services.onec_sync',
            'apps.common.models'
        ]

        for module in critical_modules:
            coverage_percent = cov.report(include=[module], show_missing=False)
            assert coverage_percent >= 90, f"{module} coverage is {coverage_percent}%, required 90%+"

    def test_integration_endpoints_have_tests(self):
        """Все endpoints интеграции с 1С должны быть покрыты тестами"""
        from django.urls import reverse
        from django.test import Client

        integration_endpoints = [
            'onec-customers-list',
            'onec-orders-list',
            'onec-sync-conflicts-list'
        ]

        client = Client()

        for endpoint_name in integration_endpoints:
            url = reverse(endpoint_name)
            # Проверяем что существует тест для этого endpoint
            test_file_exists = self._check_test_file_exists_for_endpoint(endpoint_name)
            assert test_file_exists, f"No test found for endpoint {endpoint_name}"
```

### Заключение по стратегии тестирования

**Архитектура тестирования FREESPORT** обеспечивает:

1. **Высокое покрытие критичных модулей** (90%+) включая интеграцию с 1С
2. **Comprehensive testing** ролевого ценообразования B2B/B2C
3. **Robust integration testing** внешних API с mock серверами
4. **E2E validation** критически важных пользовательских потоков
5. **Performance monitoring** интеграций в CI/CD

**Особое внимание уделено**:

- Тестированию синхронизации покупателей с 1С
- Проверке разрешения конфликтов данных
- Валидации ролевого ценообразования
- Circuit breaker поведения при отказах внешних систем
- Performance тестированию критичных интеграций

---

## 10.4. Критически важная система изоляции тестов

### 10.4.1. Полная изоляция тестов

**🚨 КРИТИЧЕСКИ ВАЖНО**: Каждый тест должен выполняться в полностью изолированной среде. Проект использует автоматические фикстуры для обеспечения полной изоляции:

```python
# conftest.py - автоматические фикстуры изоляции
@pytest.fixture(autouse=True)
def enable_db_access_for_all_tests(db):
    """Автоматически включает доступ к базе данных для всех тестов"""
    pass

@pytest.fixture(autouse=True)
def clear_db_before_test(transactional_db):
    """Очищает базу данных перед каждым тестом для полной изоляции"""
    from django.core.cache import cache
    from django.db import connection
    from django.apps import apps
    from django.db import transaction

    # Очищаем кэши Django
    cache.clear()

    # Принудительная очистка всех таблиц перед тестом
    with connection.cursor() as cursor:
        models = apps.get_models()
        for model in models:
            table_name = model._meta.db_table
            try:
                cursor.execute(f'TRUNCATE TABLE "{table_name}" RESTART IDENTITY CASCADE')
            except Exception:
                pass  # Игнорируем ошибки для системных таблиц

    # Используем транзакционную изоляцию
    with transaction.atomic():
        yield
```

### 10.4.2. Генерация уникальных данных

**Проблема**: Использование статических значений или простых последовательностей может приводить к constraint violations при параллельном выполнении тестов.

**Решение**: Обязательное использование комбинированного подхода для генерации уникальных значений:

```python
import uuid
import time

# Глобальный счетчик для обеспечения уникальности
_unique_counter = 0

def get_unique_suffix():
    """Генерирует абсолютно уникальный суффикс"""
    global _unique_counter
    _unique_counter += 1
    return f"{int(time.time() * 1000)}-{_unique_counter}-{uuid.uuid4().hex[:6]}"

# В Factory Boy
class BrandFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Brand

    name = factory.LazyFunction(lambda: f"Brand-{get_unique_suffix()}")  # ✅ Правильно
    # name = factory.Sequence(lambda n: f"Brand-{n}")  # ❌ Может дублироваться
```

### 10.4.3. Настройки pytest для изоляции

В `pytest.ini` должны быть следующие настройки:

```ini
[tool:pytest]
DJANGO_SETTINGS_MODULE = freesport.settings.test
addopts =
    --verbose
    --create-db        # ✅ Создавать чистую БД
    --nomigrations     # ✅ Не выполнять миграции для скорости
    # --reuse-db       # ❌ НЕ переиспользовать БД между запусками

markers =
    unit: Unit tests (fast, isolated, no DB)
    integration: Integration tests (with DB, API testing)
    django_db: Tests requiring database access
```

## 10.5. Команды запуска тестов

Все тесты запускаются с помощью `pytest` из корневой директории `backend/`:

```bash
# Запустить все тесты (unit + integration)
pytest

# Запустить только unit-тесты
pytest -m unit

# Запустить только интеграционные тесты
pytest -m integration

# Запустить тесты с отчетом о покрытии
pytest --cov=apps

# Запустить тесты для конкретного файла
pytest tests/integration/test_products_api.py

# Исключить устаревшие тесты (по умолчанию в CI)
pytest --ignore=tests/legacy
```

### Docker команды для тестирования

```bash
# Тестирование в Docker (рекомендуется)
make test                    # Все тесты с PostgreSQL + Redis
make test-unit               # Только unit-тесты
make test-integration        # Только интеграционные тесты
make test-fast               # Без пересборки образов
```

## 10.6. Обязательные правила написания тестов

### 10.6.1. Правила для Factory Boy

**✅ Правильно:**

```python
# Всегда используйте LazyFunction для уникальных полей
class ProductFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Product

    name = factory.LazyFunction(lambda: f"Product-{get_unique_suffix()}")
    sku = factory.LazyFunction(lambda: f"SKU-{get_unique_suffix().upper()}")
    slug = factory.LazyAttribute(lambda obj: obj.name.lower().replace(' ', '-'))
```

**❌ Неправильно:**

```python
# НЕ используйте статические значения или простые Sequence
class ProductFactory(factory.django.DjangoModelFactory):
    name = "Test Product"  # ❌ Статическое значение
    sku = factory.Sequence(lambda n: f"SKU{n}")  # ❌ Может дублироваться
```

### 10.6.2. Маркировка тестов

**Обязательные маркеры:**

- `@pytest.mark.unit` - для unit тестов (без БД, быстрые)
- `@pytest.mark.integration` - для интеграционных тестов (с БД, API)
- `@pytest.mark.django_db` - для всех тестов, использующих БД

**✅ Правильная структура файла:**

```python
import pytest
from rest_framework.test import APIClient

# Маркировка для всего модуля
pytestmark = pytest.mark.django_db

@pytest.mark.integration
class TestProductAPI:
    def test_product_list_returns_200(self, api_client):
        response = api_client.get('/api/products/')
        assert response.status_code == 200
```

### 10.6.3. Структура тестов (AAA Pattern)

**✅ Обязательная структура:**

```python
def test_order_creation_calculates_total_correctly():
    # ARRANGE - подготовка данных
    user = UserFactory.create()
    product1 = ProductFactory.create(retail_price=100)
    product2 = ProductFactory.create(retail_price=200)

    # ACT - выполнение действия
    order = Order.objects.create(user=user)
    OrderItem.objects.create(order=order, product=product1, quantity=1)
    OrderItem.objects.create(order=order, product=product2, quantity=2)

    # ASSERT - проверка результата
    assert order.calculate_total() == 500  # 100*1 + 200*2
```

### 10.6.4. Именование тестов

**Файлы:**

- Unit тесты: `tests/unit/test_[module]_[component].py`
- Интеграционные: `tests/integration/test_[feature]_api.py`

**Функции и классы:**

- Функции: `test_[action]_[expected_result]()`
- Классы: `Test[ComponentName]` или `Test[FeatureName]API`

**✅ Примеры хороших имен:**

```python
def test_user_registration_creates_inactive_user():
def test_product_search_filters_by_brand():
def test_order_calculation_includes_delivery_cost():
def test_unauthorized_user_cannot_access_profile():

class TestProductModel:
class TestUserRegistrationAPI:
class TestOrderCalculationService:
```

## 10.7. Контрольные точки качества (Quality Gates)

### 10.7.1. Требования к покрытию

- **Общее покрытие по проекту**: **не менее 70%**
- **Покрытие критических модулей**: **не менее 90%**
  - `apps.users.models`
  - `apps.users.serializers`
  - `apps.products.models`
  - `apps.orders.models`
  - `apps.common.services` (включая 1С интеграцию)
  - `apps.common.models` (CustomerSyncLog, ImportLog, SyncConflict)

### 10.7.2. CI/CD интеграция

Все тесты автоматически запускаются в GitHub Actions при каждом пуше в ветки `develop` и `main`. Конфигурация находится в файле `.github/workflows/backend-ci.yml`.

**Критерии успеха:**

- `unit_tests`: 100% pass
- `integration_tests`: 100% pass
- `e2e_tests`: 95% pass (допустимы flaky tests)
- `coverage`: >= 70% overall, >= 90% critical modules

**Блокировка мержа**: Пулл-реквесты, в которых тесты не проходят или покрытие падает ниже установленного порога, не могут быть влиты.
