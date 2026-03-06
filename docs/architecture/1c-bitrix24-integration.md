# Архитектура интеграции FREESPORT с 1С данными через протокол Битрикс24

## 1. Анализ текущей архитектуры

### 1.1 Архитектура FREESPORT
- **Backend**: Django 4.2 LTS + PostgreSQL 15+
- **API**: Django REST Framework с drf-spectacular (OpenAPI 3.1.0)
- **Аутентификация**: JWT токены с роловой системой (7 ролей)
- **Асинхронные задачи**: Celery + Redis
- **Кэширование**: Redis для сессий и кэша запросов

### 1.2 Модели данных FREESPORT
```python
# Основные модели для интеграции
apps/products/models.py:
  - Product: товары с многоуровневым ценообразованием
  - Category: иерархические категории 
  - Brand: бренды товаров

apps/orders/models.py:
  - Order: заказы B2B/B2C
  - OrderItem: позиции заказа

apps/users/models.py:
  - CustomUser: 6 ролей покупателей с разным ценообразованием + админ
```

### 1.3 Роли пользователей и ценообразование
**6 типов покупателей с разными ценами:**
1. **retail** - Розничные покупатели
2. **wholesale_level1** - Оптовики уровень 1
3. **wholesale_level2** - Оптовики уровень 2  
4. **wholesale_level3** - Оптовики уровень 3
5. **trainer** - Тренеры/спорт.клубы/фитнес
6. **federation_rep** - Представители федераций
7. **admin** - Администраторы (не покупатели, внутренняя роль)

### 1.4 Точки интеграции с 1С

1. **Синхронизация товаров** - каталог с категориями, цены и остатки
2. **Обмен заказами** - отправка новых заказов в 1С и получение статусов
3. **Клиенты** - синхронизация данных пользователей B2B с модерацией
4. **Цены** - получение 6 типов цен из 1С
5. **Статусы заказов** - получение обновлений статусов из 1С

## 2. Протокол Битрикс24 REST API

### 2.1 Ключевые модули API
- **catalog.product.*** - управление товарами
- **catalog.price.*** - управление ценами  
- **catalog.storeproduct.*** - остатки на складах
- **sale.order.*** - управление заказами
- **crm.orderentity.*** - связь заказов с CRM

### 2.2 Структуры данных Битрикс24
```typescript
// Товар
interface Bitrix24Product {
  id: number;
  name: string;
  xmlId: string;
  active: 'Y' | 'N';
  code: string;
  categoryId: number;  // Связь с категорией
  description?: string;
  detailText?: string;
  previewPicture?: number;
  detailPicture?: number;
  // Свойства товара
  propertyN?: {
    valueId?: number;
    value: string;
  };
}

// Цена товара (6 типов цен для покупателей)
interface Bitrix24Price {
  productId: number;
  catalogGroupId: number;  // ID типа цены
  price: string;
  currency: string;
  // Типы цен: retail, wholesale_level1-3, trainer, federation_rep
}

// Остатки товара - только доступное количество
interface Bitrix24Stock {
  productId: number;
  availableQuantity: string;  // Доступно для заказа
}

// Контакт (физическое лицо)
interface Bitrix24Contact {
  id: number;
  honorific?: string;
  name?: string;        // Имя
  secondName?: string;  // Отчество
  lastName?: string;    // Фамилия
  photo?: number;
  // Для B2B: ФИО контактного лица компании
  birthdate?: string;
  typeId?: string;
  sourceId?: string;
  post?: string;
  comments?: string;
  opened: 'Y' | 'N';
  assignedById?: number;
  companyId?: number;
  companyIds?: number[];
  phone?: Array<{
    id: string;
    value: string;
    valueType: string;
  }>;
  email?: Array<{
    id: string;
    value: string;
    valueType: string;
  }>;
  // UTM поля для аналитики
  utmSource?: string;
  utmMedium?: string;
  utmCampaign?: string;
  utmContent?: string;
  utmTerm?: string;
}

// Компания (юридическое лицо)
interface Bitrix24Company {
  id: number;
  title: string;
  companyType?: string;
  logoId?: number;
  address?: string;
  addressLegal?: string;
  bankingDetails?: string;
  industry?: string;
  employees?: number;
  revenue?: number;
  currency?: string;
  comments?: string;
  opened: 'Y' | 'N';
  assignedById?: number;
  contactIds?: number[];
  phone?: Array<{
    id: string;
    value: string;
    valueType: string;
  }>;
  email?: Array<{
    id: string;
    value: string;
    valueType: string;
  }>;
  web?: Array<{
    id: string;
    value: string;
    valueType: string;
  }>;
}

// Заказ
interface Bitrix24Order {
  id: number;
  lid: string;
  accountNumber: string;
  orderTopicId: number;
  userId: number;
  price: number;
  currency: string;
  discountValue: number;
  statusId: string;
  dateInsert: string;
  paySystemId: number;
  deliveryId: number;
  // Связи с CRM
  contactId?: number;
  companyId?: number;
}

// Связь заказа с CRM сущностью
interface Bitrix24OrderEntity {
  orderId: number;
  ownerId: number;
  ownerTypeId: number; // 2 - сделка, 31 - счет
}

// Позиция заказа
interface Bitrix24OrderItem {
  id: number;
  orderId: number;
  productId: number;
  productName: string;
  price: number;
  quantity: number;
  currency: string;
  discount: number;
  vatRate?: number;
}
```

## 3. Слой адаптации данных

### 3.1 Архитектурная схема
```
FREESPORT (Django)  <->  Adapter Layer  <->  1C (Битрикс24 API)
     ↓                       ↓                       ↓
PostgreSQL Models    Data Transformation      1C:Управление торговлей
```

### 3.2 Компоненты адаптера
```python
# backend/apps/integration/adapters/bitrix24_adapter.py
class Bitrix24Adapter:
    """Адаптер для работы с API Битрикс24"""
    
    def __init__(self, webhook_url: str):
        self.webhook_url = webhook_url
        self.client = Bitrix24Client(webhook_url)
    
    # Клиенты - с модерацией для B2B
    def sync_customer_with_1c(self, user: CustomUser) -> Dict:
        """Синхронизация клиента с 1С"""
        
    def get_existing_customers_from_1c(self) -> List[Dict]:
        """Получение существующих клиентов из 1С для автоматического присвоения роли"""
        
    def moderate_b2b_customer(self, user: CustomUser, approved_role: str) -> Dict:
        """Модерация B2B клиента администратором с присвоением типа ценообразования"""
        
    def transform_product_to_bitrix24(self, product: Product) -> Dict:
        """Трансформация товара FREESPORT -> Битрикс24"""
        
    def transform_product_from_bitrix24(self, data: Dict) -> Product:
        """Трансформация товара Битрикс24 -> FREESPORT"""
    
    # Заказы - только новые заказы в статусе 'new'
    def send_new_order_to_1c(self, order: Order) -> Dict:
        """Отправка нового заказа в 1С (только статус 'new')"""
        
    def transform_order_to_bitrix24(self, order: Order) -> Dict:
        """Трансформация нового заказа FREESPORT -> Битрикс24"""
        
    # Цены для 6 типов покупателей
    def get_prices_for_customer_types(self) -> Dict:
        """Получение цен для 6 типов покупателей (без admin)"""
        
    def get_product_available_quantity(self, product: Product) -> Dict:
        """Получение доступного количества товара из 1С"""
        
    def sync_available_quantity(self) -> Dict:
        """Синхронизация доступного количества товаров"""

# Маппинг полей
class FieldMapper:
    """Маппинг полей между FREESPORT и Битрикс24"""
    
    PRODUCT_MAPPING = {
        'name': 'name',
        'slug': 'code', 
        'description': 'description',
        'retail_price': 'price',
        'category__name': 'sectionId',
        'brand__name': 'property_brand',
    }
    
    ORDER_MAPPING = {
        'id': 'xmlId',
        'user_email': 'email',
        'total_amount': 'price',
        'status': 'statusId',
        'created_at': 'dateInsert',
    }
```

### 3.3 Celery задачи для интеграции
```python
# backend/apps/integration/tasks.py
from celery import shared_task
from .adapters.bitrix24_adapter import Bitrix24Adapter

@shared_task(bind=True, max_retries=3)
def sync_products_task(self):
    """Задача синхронизации товаров"""
    adapter = Bitrix24Adapter(settings.BITRIX24_WEBHOOK_URL)
    return adapter.sync_products()

@shared_task(bind=True, max_retries=3)
def send_order_to_1c_task(self, order_id: int):
    """Задача отправки заказа в 1С"""
    adapter = Bitrix24Adapter(settings.BITRIX24_WEBHOOK_URL)
    order = Order.objects.get(id=order_id)
    return adapter.send_order_to_1c(order)

@shared_task(bind=True, max_retries=3)
def sync_prices_task(self):
    """Задача синхронизации цен"""
    adapter = Bitrix24Adapter(settings.BITRIX24_WEBHOOK_URL)
    return adapter.sync_prices()

@shared_task(bind=True, max_retries=3)
def sync_quantity_in_stock_task(self):
    """Задача синхронизации остатков товаров"""
    adapter = Bitrix24Adapter(settings.BITRIX24_WEBHOOK_URL)
    return adapter.sync_quantity_in_stock()

@shared_task(bind=True, max_retries=3)
def sync_customer_with_1c_task(self, user_id: int):
    """Задача синхронизации клиента с 1С"""
    adapter = Bitrix24Adapter(settings.BITRIX24_WEBHOOK_URL)
    user = CustomUser.objects.get(id=user_id)
    return adapter.sync_customer_with_1c(user)

@shared_task(bind=True, max_retries=3)
def update_order_status_task(self, order_id: int, new_status: str):
    """Задача обновления статуса заказа из 1С"""
    try:
        order = Order.objects.get(id=order_id)
        order.status_1c = new_status
        order.sync_status_from_1c(new_status)
        order.save()
        return f"Order {order_id} status updated to {new_status}"
    except Order.DoesNotExist:
        return f"Order {order_id} not found"
```

## 4. API Endpoints

### 4.1 Новые endpoints для интеграции
```python
# backend/apps/integration/urls.py
urlpatterns = [
    # Webhook endpoints для получения данных от 1С
    path('webhook/bitrix24/products/', Bitrix24ProductWebhookView.as_view()),
    path('webhook/bitrix24/orders/', Bitrix24OrderWebhookView.as_view()),
    path('webhook/bitrix24/prices/', Bitrix24PriceWebhookView.as_view()),
    path('webhook/bitrix24/order-status/', Bitrix24OrderStatusWebhookView.as_view()),
    path('webhook/bitrix24/quantity-in-stock/', Bitrix24QuantityInStockWebhookView.as_view()),
    path('webhook/bitrix24/customers/', Bitrix24CustomerWebhookView.as_view()),
    
    # Admin endpoints для управления интеграцией
    path('admin/sync-products/', AdminSyncProductsView.as_view()),
    path('admin/sync-orders/', AdminSyncOrdersView.as_view()),
    path('admin/sync-quantity-in-stock/', AdminSyncQuantityInStockView.as_view()),
    path('admin/sync-customers/', AdminSyncCustomersView.as_view()),
    path('admin/integration-status/', AdminIntegrationStatusView.as_view()),
]

# Views
class Bitrix24ProductWebhookView(APIView):
    """Webhook для получения товаров от 1С"""
    permission_classes = [IsAuthenticated]  # Добавить специальную аутентификацию
    
    def post(self, request):
        serializer = Bitrix24ProductSerializer(data=request.data)
        if serializer.is_valid():
            # Обработка данных товара
            sync_products_task.delay()
            return Response({'status': 'accepted'})
        return Response(serializer.errors, status=400)

class Bitrix24PriceWebhookView(APIView):
    """Webhook для получения цен от 1С"""
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        serializer = Bitrix24PriceSerializer(data=request.data)
        if serializer.is_valid():
            # Обработка данных цен
            sync_prices_task.delay()
            return Response({'status': 'accepted'})
        return Response(serializer.errors, status=400)

class Bitrix24OrderStatusWebhookView(APIView):
    """Webhook для получения статуса заказа от 1С"""
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        serializer = Bitrix24OrderStatusSerializer(data=request.data)
        if serializer.is_valid():
            # Обработка статуса заказа
            update_order_status_task.delay(
                request.data.get('order_id'),
                request.data.get('status')
            )
            return Response({'status': 'accepted'})
        return Response(serializer.errors, status=400)

class Bitrix24QuantityInStockWebhookView(APIView):
    """Webhook для получения остатков от 1С"""
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        serializer = Bitrix24QuantityInStockSerializer(data=request.data)
        if serializer.is_valid():
            # Обработка данных остатков
            sync_quantity_in_stock_task.delay()
            return Response({'status': 'accepted'})
        return Response(serializer.errors, status=400)

class Bitrix24CustomerWebhookView(APIView):
    """Webhook для получения данных клиентов от 1С"""
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        serializer = Bitrix24CustomerSerializer(data=request.data)
        if serializer.is_valid():
            # Обработка данных клиентов
            sync_customers_task.delay()
            return Response({'status': 'accepted'})
        return Response(serializer.errors, status=400)
```

### 4.2 Расширение существующих endpoints
```python
# Расширение ProductViewSet для поддержки Битрикс24
class ProductViewSet(viewsets.ModelViewSet):
    # ... существующий код ...
    
    @action(detail=True, methods=['post'])
    def sync_with_1c(self, request, pk=None):
        """Синхронизировать товар с 1С"""
        product = self.get_object()
        adapter = Bitrix24Adapter(settings.BITRIX24_WEBHOOK_URL)
        result = adapter.sync_single_product(product)
        return Response(result)
    
    @action(detail=True, methods=['get'])
    def quantity_in_stock_status(self, request, pk=None):
        """Получить статус остатков товара"""
        product = self.get_object()
        adapter = Bitrix24Adapter(settings.BITRIX24_WEBHOOK_URL)
        result = adapter.get_product_quantity_in_stock(product)
        return Response(result)

# Расширение OrderViewSet  
class OrderViewSet(viewsets.ModelViewSet):
    # ... существующий код ...
    
    @action(detail=True, methods=['post'])
    def send_to_1c(self, request, pk=None):
        """Отправить заказ в 1С"""
        order = self.get_object()
        send_order_to_1c_task.delay(order.id)
        return Response({'status': 'queued'})
    
    @action(detail=True, methods=['get'])
    def status_from_1c(self, request, pk=None):
        """Получить статус заказа из 1С"""
        order = self.get_object()
        adapter = Bitrix24Adapter(settings.BITRIX24_WEBHOOK_URL)
        result = adapter.get_order_status_from_1c(order)
        return Response(result)

# Расширение UserViewSet для B2B клиентов
class UserViewSet(viewsets.ModelViewSet):
    # ... существующий код ...
    
    @action(detail=True, methods=['post'])
    def sync_with_1c(self, request, pk=None):
        """Синхронизировать B2B клиента с 1С"""
        user = self.get_object()
        if user.role in ['wholesale_level1', 'wholesale_level2', 'wholesale_level3']:
            sync_customer_with_1c_task.delay(user.id)
            return Response({'status': 'queued'})
        return Response({'error': 'Only B2B customers can be synced'}, status=400)
```

## 5. Модели данных интеграции

### 5.1 Новые модели
```python
# backend/apps/integration/models.py
class IntegrationSettings(models.Model):
    """Настройки интеграции с 1С"""
    webhook_url = models.URLField()
    api_token = models.CharField(max_length=255)
    sync_interval_minutes = models.IntegerField(default=30)
    active = models.BooleanField(default=True)
    last_sync = models.DateTimeField(null=True, blank=True)

class SyncLog(models.Model):
    """Лог синхронизации"""
    sync_type = models.CharField(max_length=50)  # products, orders, prices
    status = models.CharField(max_length=20)  # success, error, in_progress
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    duration_seconds = models.IntegerField(null=True)

class ProductMapping(models.Model):
    """Связь товаров FREESPORT <-> 1С"""
    freesport_product = models.OneToOneField(Product, on_delete=models.CASCADE)
    bitrix24_id = models.IntegerField()
    onec_product_id = models.CharField(max_length=255)
    last_sync = models.DateTimeField(auto_now=True)

class OrderMapping(models.Model):  
    """Связь заказов FREESPORT <-> 1С"""
    freesport_order = models.OneToOneField(Order, on_delete=models.CASCADE)
    bitrix24_id = models.IntegerField(null=True)
    onec_order_id = models.CharField(max_length=255)
    status_1c = models.CharField(max_length=50)
    last_sync = models.DateTimeField(auto_now=True)
```

### 5.2 Расширение существующих моделей
```python
# Расширение модели Product
class Product(BaseModel):
    # ... существующие поля ...
    
    # Поля для интеграции с 1С
    onec_product_id = models.CharField(max_length=255, blank=True)
    sync_with_1c = models.BooleanField(default=True)
    last_sync_1c = models.DateTimeField(null=True, blank=True)
    
    @property
    def bitrix24_data(self) -> Dict:
        """Данные для отправки в Битрикс24"""
        return {
            'name': self.name,
            'code': self.slug,
            'xmlId': self.onec_product_id or f"freesport_{self.id}",
            'active': 'Y' if self.is_active else 'N',
            'description': self.description,
        }

# Расширение модели Order
class Order(BaseModel):
    # ... существующие поля ...
    
    # Поля для интеграции с 1С  
    onec_order_id = models.CharField(max_length=255, blank=True)
    sent_to_1c = models.BooleanField(default=False)
    sent_to_1c_at = models.DateTimeField(null=True, blank=True)
    status_1c = models.CharField(max_length=100, blank=True)  # Статус из 1С
    
    # Маппинг статусов 1С на внутренние статусы FREESPORT
    STATUS_1C_MAPPING = {
        'Принят в обработку': 'processing',
        'Резервирование на складе': 'reserved', 
        'Готов к отгрузке': 'ready_to_ship',
        'Отгружен': 'shipped',
        'Доставлен': 'delivered',
        'Отменен': 'cancelled',
        'Возврат': 'returned',
    }
    
    def sync_status_from_1c(self, status_1c: str):
        """Синхронизация внутреннего статуса на основе статуса из 1С"""
        self.status_1c = status_1c
        
        # Маппинг статуса 1С на внутренний статус
        if status_1c in self.STATUS_1C_MAPPING:
            new_internal_status = self.STATUS_1C_MAPPING[status_1c]
            
            # Обновляем внутренний статус только если он изменился
            if self.status != new_internal_status:
                old_status = self.status
                self.status = new_internal_status
                self.save()
                
                # Логирование изменения статуса
                logger.info(
                    "Order status synchronized from 1C",
                    order_id=self.id,
                    old_status=old_status,
                    new_status=new_internal_status,
                    status_1c=status_1c
                )
        else:
            # Если статус из 1С неизвестен, только сохраняем его без изменения внутреннего
            self.save()
            logger.warning(
                "Unknown 1C status received",
                order_id=self.id,
                status_1c=status_1c,
                current_internal_status=self.status
            )
```

## 6. Диаграмма архитектуры интеграции

```
┌─────────────────────────────────────────────────────────────────────┐
│                          FREESPORT Platform                          │
├─────────────────────────────────────────────────────────────────────┤
│  Frontend (Next.js)           │         Backend (Django)            │
│                              │                                      │
│  - Product Catalog           │  ┌─────────────────────────────────┐ │
│  - Order Management          │  │        Django Apps              │ │
│  - User Dashboard            │  │  ┌─────────────────────────────┐ │ │
│                              │  │  │ apps/products/              │ │ │
│                              │  │  │ apps/orders/                │ │ │
│                              │  │  │ apps/users/                 │ │ │
│                              │  │  │ apps/integration/ (НОВЫЙ)   │ │ │
│                              │  │  └─────────────────────────────┘ │ │
│                              │  └─────────────────────────────────┘ │
└──────────────────┬───────────────────────────────────┬──────────────┘
                   │                                   │
                   │ HTTP/HTTPS                        │ API Calls
                   │                                   │
┌──────────────────▼───────────────────────────────────▼──────────────┐
│                    Integration Layer (НОВЫЙ)                         │
├─────────────────────────────────────────────────────────────────────┤
│  ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐  │
│  │ Bitrix24Adapter │    │   FieldMapper   │    │  DataValidator  │  │
│  │                 │    │                 │    │                 │  │
│  │ - sync_products         │    │ - product_map   │    │ - validate_data │  │
│  │ - sync_orders           │    │ - order_map     │    │ - clean_data    │  │
│  │ - sync_prices           │    │ - user_map      │    │                 │  │
│  │ - sync_quantity_in_stock│    │ - quantity_map  │    │                 │  │
│  │ - get_order_status_1c   │    │ - status_map    │    │                 │  │
│  └─────────────────┘    └─────────────────┘    └─────────────────┘  │
│                                   │                                  │
│  ┌─────────────────────────────────▼─────────────────────────────────┐  │
│  │                     Celery Tasks                                  │  │
│  │  - sync_products_task         - send_order_to_1c_task           │  │
│  │  - sync_prices_task           - sync_quantity_in_stock_task    │  │
│  │  - sync_customer_with_1c_task - update_order_status_task       │  │
│  └───────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────┬───────────────────────────────────────┘
                              │ Битрикс24 REST API
                              │ (JSON/HTTP)
┌─────────────────────────────▼───────────────────────────────────────┐
│                     1С:Управление торговлей                         │
├─────────────────────────────────────────────────────────────────────┤
│  ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐  │
│  │    Товары       │    │     Заказы      │    │   Контрагенты   │  │
│  │                 │    │                 │    │                 │  │
│  │ - Номенклатура  │    │ - Документы     │    │ - Организации   │  │
│  │ - Цены          │    │ - Проведение    │    │ - Физ.лица      │  │  
│  │ - Остатки       │    │ - Оплата        │    │                 │  │
│  └─────────────────┘    └─────────────────┘    └─────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
```

## 7. Технические спецификации

### 7.1 Требования к производительности
- **Синхронизация товаров**: максимум 1000 товаров за запрос
- **Время ответа API**: не более 5 секунд для стандартных запросов  
- **Частота синхронизации**: каждые 30 минут (настраивается)
- **Обработка ошибок**: максимум 3 попытки повтора с экспоненциальной задержкой

### 7.2 Безопасность
```python
# Настройки безопасности для интеграции
BITRIX24_SETTINGS = {
    'WEBHOOK_URL': env('BITRIX24_WEBHOOK_URL'),
    'API_TOKEN': env('BITRIX24_API_TOKEN'),  # Хранить в переменных окружения
    'TIMEOUT': 30,  # Таймаут для HTTP запросов
    'MAX_RETRIES': 3,
    'VERIFY_SSL': True,
    'ALLOWED_IPS': ['ip1', 'ip2'],  # Белый список IP 1С
}

# Валидация webhook запросов
class Bitrix24WebhookAuthentication(BaseAuthentication):
    def authenticate(self, request):
        token = request.headers.get('X-Bitrix24-Token')
        if not token or token != settings.BITRIX24_API_TOKEN:
            raise AuthenticationFailed('Invalid Bitrix24 token')
        return (None, None)
```

### 7.3 Мониторинг и логирование
```python
# Структурированное логирование интеграции
import structlog

logger = structlog.get_logger(__name__)

class Bitrix24Adapter:
    def sync_products(self):
        logger.info(
            "Starting product sync",
            integration_type="bitrix24",
            operation="sync_products"
        )
        
        try:
            # Логика синхронизации
            result = self._perform_sync()
            
            logger.info(
                "Product sync completed",
                integration_type="bitrix24", 
                operation="sync_products",
                products_synced=result['count'],
                duration=result['duration']
            )
            
        except Exception as e:
            logger.error(
                "Product sync failed",
                integration_type="bitrix24",
                operation="sync_products", 
                error=str(e)
            )
            raise
```

## 8. План реализации

### Этап 1: Основа интеграции (1-2 недели)
1. Создание приложения `apps/integration/`
2. Базовый Bitrix24Adapter
3. Модели для маппинга данных
4. Основные Celery задачи

### Этап 2: Синхронизация товаров (1 неделя)
1. Трансформация данных товаров
2. Webhook endpoints для получения товаров
3. Синхронизация цен и остатков
4. Тестирование товарной интеграции

### Этап 3: Обмен заказами (1 неделя)  
1. Трансформация заказов FREESPORT -> Битрикс24
2. Отправка заказов в 1С
3. Получение статусов заказов
4. Тестирование заказной интеграции

### Этап 4: Тестирование и оптимизация (1 неделя)
1. Интеграционные тесты
2. Нагрузочное тестирование  
3. Мониторинг и алерты
4. Документация для пользователей

Общий срок реализации: **4-5 недель**
