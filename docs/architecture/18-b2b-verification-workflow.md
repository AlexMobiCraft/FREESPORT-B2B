# 18. B2B Verification Workflow

## Обзор

Документ детализирует процесс верификации B2B пользователей в FREESPORT на основе существующей архитектуры и кодовой базы.

## Существующая B2B Инфраструктура

### Ролевая модель пользователей (apps/users/models.py)

```python
ROLE_CHOICES = [
    ("retail", "Розничный покупатель"),
    ("wholesale_level1", "Оптовик уровень 1"),
    ("wholesale_level2", "Оптовик уровень 2"), 
    ("wholesale_level3", "Оптовик уровень 3"),
    ("trainer", "Тренер/Фитнес-клуб"),
    ("federation_rep", "Представитель федерации"),
    ("admin", "Администратор"),
]
```

### Поля верификации в User модели

```python
# B2B поля
company_name = models.CharField(max_length=200, blank=True)
tax_id = models.CharField(max_length=12, blank=True)

# Статус верификации для B2B
is_verified = models.BooleanField(default=False)
```

### Company модель для расширенных B2B данных

```python
class Company(models.Model):
    user = models.OneToOneField(User, related_name="company")
    legal_name = models.CharField(max_length=255)
    tax_id = models.CharField(max_length=12, unique=True)
    kpp = models.CharField(max_length=9, blank=True)
    legal_address = models.TextField()
    # Банковские реквизиты
    bank_name = models.CharField(max_length=200, blank=True)
    bank_bik = models.CharField(max_length=9, blank=True) 
    account_number = models.CharField(max_length=20, blank=True)
```

## Процесс Регистрации B2B

### 1. Регистрация через UserRegistrationSerializer

**Автоматическая валидация (apps/users/serializers.py:59-78):**

```python
def validate(self, attrs):
    role = attrs.get("role", "retail")
    if role != "retail":
        # Для B2B пользователей требуется название компании
        if not attrs.get("company_name"):
            raise serializers.ValidationError({
                "company_name": "Название компании обязательно для B2B пользователей."
            })
        
        # Для оптовиков и представителей федерации требуется ИНН
        if role.startswith("wholesale") or role == "federation_rep":
            if not attrs.get("tax_id"):
                raise serializers.ValidationError({
                    "tax_id": "ИНН обязателен для оптовых покупателей и представителей федерации."
                })
```

**Автоматическая установка статуса (apps/users/serializers.py:92-95):**

```python
# B2B пользователи требуют верификации
if user.role != "retail":
    user.is_verified = False
    user.save()
```

### 2. Статусы верификации

#### Определение статуса (apps/users/views/personal_cabinet.py:60)

```python
verification_status = "verified" if user.is_verified else "pending"
```

#### Отображение в дашборде

B2B пользователи видят `verification_status` в персональном дашборде:

```python
# personal_cabinet.py:57-60
if user.is_b2b_user:
    verification_status = "verified" if user.is_verified else "pending"
```

## Детализированный Workflow

### Этап 1: Регистрация B2B пользователя

1. **Frontend форма регистрации** отправляет данные:

   ```json
   {
     "email": "company@example.com",
     "password": "password123",
     "password_confirm": "password123",
     "first_name": "Иван",
     "last_name": "Иванов",
     "phone": "+79001234567",
     "role": "wholesale_level1",
     "company_name": "ООО Спорт Компани",
     "tax_id": "1234567890"
   }
   ```

2. **UserRegistrationSerializer валидация:**
   - Проверка уникальности email
   - Валидация обязательных B2B полей
   - Создание пользователя с `is_verified = False`

3. **Автоматические действия системы:**
   - Создание User записи
   - Установка `is_verified = False` для B2B ролей
   - Отправка welcome email (TODO: реализовать)

### Этап 2: Автоматические проверки

#### Проверка дубликатов ИНН

```sql
-- Существующий индекс (apps/users/migrations/0003_add_performance_indexes.py:64-67)
CREATE INDEX IF NOT EXISTS companies_tax_id_idx ON companies (tax_id);
```

**Реализация проверки:**
```python
# В UserRegistrationSerializer.validate()
if attrs.get("tax_id"):
    if User.objects.filter(tax_id=attrs["tax_id"]).exists():
        raise serializers.ValidationError({
            "tax_id": "Компания с данным ИНН уже зарегистрирована."
        })
```

#### Валидация формата ИНН

```python
import re

def validate_tax_id(self, value):
    """Валидация российского ИНН"""
    if not value:
        return value
        
    # Удаляем пробелы и дефисы
    inn = re.sub(r'[^\d]', '', value)
    
    # ИНН может быть 10 или 12 цифр
    if len(inn) not in [10, 12]:
        raise serializers.ValidationError(
            "ИНН должен содержать 10 или 12 цифр."
        )
    
    # TODO: Добавить контрольную сумму ИНН
    return inn
```

### Этап 3: Ручная верификация администратором

#### Django Admin Interface (ОТСУТСТВУЕТ - нужно создать)

**Требуемый функционал:**

```python
# apps/users/admin.py (СОЗДАТЬ)
from django.contrib import admin
from django.utils.html import format_html
from .models import User, Company

@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ['email', 'full_name', 'role', 'company_name', 
                   'verification_status_display', 'created_at']
    list_filter = ['role', 'is_verified', 'is_active', 'created_at']
    search_fields = ['email', 'first_name', 'last_name', 'company_name', 'tax_id']
    
    # B2B пользователи, ожидающие верификации
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        # Добавить quick filter для pending verification
        return qs
    
    def verification_status_display(self, obj):
        if obj.role == 'retail':
            return '-'
        
        if obj.is_verified:
            return format_html(
                '<span style="color: green; font-weight: bold;">✓ Верифицирован</span>'
            )
        else:
            return format_html(
                '<span style="color: orange; font-weight: bold;">⏳ Ожидает верификации</span>'
            )
    
    verification_status_display.short_description = 'Статус верификации'
    
    # Bulk actions для верификации
    actions = ['verify_users', 'reject_verification']
    
    def verify_users(self, request, queryset):
        """Верифицировать выбранных пользователей"""
        count = queryset.filter(role__in=[
            'wholesale_level1', 'wholesale_level2', 'wholesale_level3',
            'trainer', 'federation_rep'
        ]).update(is_verified=True)
        
        self.message_user(request, f'Верифицировано {count} пользователей.')
    
    verify_users.short_description = 'Верифицировать выбранных пользователей'
```

#### Процесс ручной верификации

1. **Администратор заходит в Django Admin**
2. **Фильтрует пользователей:** 
   - Role ≠ 'retail'
   - is_verified = False
3. **Проверяет документы** (вне системы)
4. **Принимает решение:**
   - ✅ Верифицировать: `is_verified = True`
   - ❌ Отклонить: статус остается False + комментарий

#### Уведомления о результатах (TODO)

```python
# После изменения is_verified
from django.db.models.signals import post_save
from django.dispatch import receiver

@receiver(post_save, sender=User)
def handle_verification_status_change(sender, instance, **kwargs):
    """Отправка уведомлений при изменении статуса верификации"""
    if instance.is_b2b_user and instance.is_verified:
        # Отправить email об успешной верификации
        send_verification_success_email.delay(instance.id)
```

### Этап 4: Влияние верификации на функциональность

#### Ограничения для неверифицированных B2B

**В каталоге товаров (products/serializers.py):**

```python
def get_current_price(self, obj):
    """Получить цену с учетом верификации"""
    user = self.context['request'].user
    
    if user.is_authenticated and user.is_b2b_user:
        if not user.is_verified:
            # Неверифицированные B2B видят только розничную цену
            return obj.retail_price
        # Верифицированные получают B2B цены
        return obj.get_price_for_user(user)
    
    return obj.retail_price
```

**В корзине (cart/serializers.py):**

```python
def validate_quantity(self, value):
    """Валидация количества с учетом верификации"""
    user = self.context['request'].user
    product = self.initial_data.get('product')
    
    if user.is_b2b_user and not user.is_verified:
        # Неверифицированные B2B не могут заказывать оптом
        if value > 10:  # Лимит для неверифицированных
            raise serializers.ValidationError(
                "Для заказа больших объемов требуется верификация компании."
            )
```

**В заказах (orders/serializers.py):**

```python
def validate_payment_method(self, value):
    """Валидация способа оплаты"""
    user = self.context['request'].user
    
    if user.is_b2b_user and not user.is_verified:
        # Неверифицированные B2B не могут использовать безналичный расчет
        if value == 'bank_transfer':
            raise serializers.ValidationError(
                "Безналичный расчет доступен только верифицированным компаниям."
            )
```

### Этап 5: Интеграция с существующими тестами

#### Дополнения к B2B workflow тестам

**Расширение test_b2b_workflow.py:**

```python
def test_unverified_b2b_limitations(self):
    """Ограничения для неверифицированных B2B пользователей"""
    unverified_user = User.objects.create_user(
        email="unverified@example.com",
        role="wholesale_level1",
        company_name="Unverified Company",
        is_verified=False
    )
    
    self.client.force_authenticate(user=unverified_user)
    
    # 1. Видят только розничные цены
    response = self.client.get(f"/api/v1/products/{self.product.id}/")
    self.assertEqual(float(response.data["current_price"]), 1000.00)  # retail_price
    
    # 2. Ограничения по количеству
    cart_data = {"product": self.product.id, "quantity": 15}
    response = self.client.post("/api/v1/cart/items/", cart_data)
    self.assertEqual(response.status_code, 400)
    
    # 3. Ограничения по способу оплаты
    self.client.post("/api/v1/cart/items/", {"product": self.product.id, "quantity": 5})
    order_data = {
        "delivery_address": "Address",
        "payment_method": "bank_transfer"
    }
    response = self.client.post("/api/v1/orders/", order_data)
    self.assertEqual(response.status_code, 400)

def test_verification_workflow_complete(self):
    """Полный цикл верификации"""
    # 1. Регистрация B2B пользователя
    registration_data = {
        "email": "newcompany@example.com",
        "password": "password123",
        "password_confirm": "password123",
        "role": "wholesale_level1",
        "company_name": "New Company",
        "tax_id": "9876543210"
    }
    response = self.client.post("/api/v1/auth/register/", registration_data)
    self.assertEqual(response.status_code, 201)
    
    user = User.objects.get(email="newcompany@example.com")
    self.assertFalse(user.is_verified)  # Автоматически неверифицирован
    
    # 2. Верификация администратором
    user.is_verified = True
    user.save()
    
    # 3. Проверка доступности B2B функций
    self.client.force_authenticate(user=user)
    response = self.client.get(f"/api/v1/products/{self.product.id}/")
    self.assertEqual(float(response.data["current_price"]), 800.00)  # B2B цена
```

## Метрики и Мониторинг

### KPI верификации

1. **Conversion Rate**: регистрация → верификация
2. **Verification Time**: среднее время обработки заявки
3. **Rejection Rate**: процент отклоненных заявок
4. **User Satisfaction**: обратная связь после верификации

### Dashboard для администраторов

```sql
-- Статистика верификации
SELECT 
    role,
    COUNT(*) as total_users,
    COUNT(CASE WHEN is_verified = true THEN 1 END) as verified_users,
    COUNT(CASE WHEN is_verified = false THEN 1 END) as pending_users,
    ROUND(
        COUNT(CASE WHEN is_verified = true THEN 1 END) * 100.0 / COUNT(*), 2
    ) as verification_rate
FROM users 
WHERE role != 'retail'
GROUP BY role
ORDER BY total_users DESC;
```

## Улучшения и Roadmap

### Краткосрочные улучшения (1-2 недели)

1. **Создать Django Admin интерфейс** для управления верификацией
2. **Добавить валидацию ИНН** с контрольной суммой  
3. **Реализовать email уведомления** о результатах верификации
4. **Расширить тестовое покрытие** для всех сценариев

### Среднесрочные улучшения (1-2 месяца)

1. **Автоматизация проверок:**
   - Интеграция с API ФНС для проверки ИНН
   - Проверка статуса компании (активная/ликвидирована)
   - Blacklist проверка

2. **Workflow для документов:**
   - Загрузка документов (ОГРН, выписка из ЕГРЮЛ)
   - Электронная подпись документов
   - Автоматическое распознавание реквизитов

3. **Уведомления и коммуникации:**
   - SMS уведомления о статусе
   - In-app уведомления
   - Чат с поддержкой для вопросов по верификации

### Долгосрочные улучшения (3-6 месяцев)

1. **Полная автоматизация:**
   - ML модель для оценки рисков
   - Интеграция с внешними KYC сервисами  
   - Автоматическая верификация для низкорисковых компаний

2. **Advanced функциональность:**
   - Уровни доверия (не только verified/unverified)
   - Кредитные лимиты на основе верификации
   - Персональные менеджеры для крупных клиентов

## Заключение

B2B verification workflow в FREESPORT основан на надежной существующей архитектуре:

- ✅ **Ролевая модель** с четким разделением B2B/B2C
- ✅ **Автоматическая валидация** обязательных полей при регистрации  
- ✅ **Статус верификации** с влиянием на функциональность
- ✅ **Тестовое покрытие** для основных сценариев
- ✅ **Performance индексы** для быстрых запросов

**Следующий шаг:** создание Django Admin интерфейса для управления процессом верификации администраторами.