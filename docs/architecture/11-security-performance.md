# 11. Безопасность и Производительность

## Обзор

FREESPORT платформа обеспечивает высокий уровень безопасности и производительности через многослойную архитектуру защиты, оптимизацию производительности и мониторинг. Особое внимание уделяется безопасности интеграций с внешними системами, включая 1С ERP.

---

## 1. Архитектура безопасности

### 1.1. Многослойная система аутентификации

**JWT Token Authentication:**
```python
class JWTAuthentication:
    """
    JWT аутентификация с поддержкой refresh токенов
    """
    
    ACCESS_TOKEN_LIFETIME = 15  # минут
    REFRESH_TOKEN_LIFETIME = 7  # дней
    
    def authenticate(self, request):
        header = self.get_header(request)
        if header is None:
            return None
            
        raw_token = self.get_raw_token(header)
        if raw_token is None:
            return None
            
        validated_token = self.get_validated_token(raw_token)
        return self.get_user(validated_token), validated_token

# Middleware для rate limiting
class RateLimitingMiddleware:
    """
    Ограничение частоты запросов
    """
    
    LIMITS = {
        'api_public': '100/hour',      # Публичные API
        'api_auth': '1000/hour',       # Аутентифицированные пользователи  
        'api_b2b': '2000/hour',        # B2B клиенты
        'auth_login': '10/minute',     # Попытки входа
        'password_reset': '5/hour'     # Сброс пароля
    }
```

### 1.2. Ролевая модель доступа (7 уровней)

**Иерархия ролей:**
```python
class UserRole(models.TextChoices):
    RETAIL = 'retail', 'Розничный покупатель'
    WHOLESALE_LEVEL1 = 'wholesale_level1', 'Оптовый покупатель 1 уровня'
    WHOLESALE_LEVEL2 = 'wholesale_level2', 'Оптовый покупатель 2 уровня'
    WHOLESALE_LEVEL3 = 'wholesale_level3', 'Оптовый покупатель 3 уровня'
    TRAINER = 'trainer', 'Тренер'
    FEDERATION_REP = 'federation_rep', 'Представитель федерации'
    ADMIN = 'admin', 'Администратор'

class RoleBasedPermissionMixin:
    """
    Миксин для проверки разрешений на основе ролей
    """
    
    def has_price_access(self, user, price_type):
        role_permissions = {
            'retail': ['retail_price'],
            'wholesale_level1': ['retail_price', 'wholesale_level1_price'],
            'wholesale_level2': ['retail_price', 'wholesale_level1_price', 'wholesale_level2_price'],
            'wholesale_level3': ['retail_price', 'wholesale_level1_price', 'wholesale_level2_price', 'wholesale_level3_price'],
            'trainer': ['retail_price', 'trainer_price'],
            'federation_rep': ['retail_price', 'federation_price'],
            'admin': ['all_prices']
        }
        
        allowed_prices = role_permissions.get(user.role, [])
        return price_type in allowed_prices or 'all_prices' in allowed_prices
```

### 1.3. Безопасность интеграций с 1С

**Защищенный обмен данными:**
```python
class OneCSecurityManager:
    """
    Менеджер безопасности для интеграции с 1С
    """
    
    def __init__(self):
        self.api_key = settings.ONEC_API_KEY
        self.secret_key = settings.ONEC_SECRET_KEY
        self.encryption_key = settings.ONEC_ENCRYPTION_KEY
        
    def create_secure_request(self, data: dict) -> dict:
        """
        Создание защищенного запроса к 1С
        """
        # 1. Подпись данных HMAC
        signature = self._create_hmac_signature(data)
        
        # 2. Шифрование чувствительных данных
        encrypted_data = self._encrypt_sensitive_data(data)
        
        # 3. Создание временного токена
        timestamp = int(time.time())
        token = self._create_request_token(timestamp)
        
        return {
            'data': encrypted_data,
            'signature': signature,
            'timestamp': timestamp,
            'token': token,
            'api_version': '2.0'
        }
    
    def validate_webhook(self, request) -> bool:
        """
        Валидация входящих webhook от 1С
        """
        try:
            signature = request.META.get('HTTP_X_ONEC_SIGNATURE')
            timestamp = request.META.get('HTTP_X_ONEC_TIMESTAMP')
            
            # Проверка временной метки (не старше 5 минут)
            if abs(int(time.time()) - int(timestamp)) > 300:
                return False
                
            # Проверка подписи
            expected_signature = self._create_hmac_signature({
                'body': request.body.decode(),
                'timestamp': timestamp
            })
            
            return hmac.compare_digest(signature, expected_signature)
            
        except (ValueError, TypeError):
            return False
    
    def _encrypt_sensitive_data(self, data: dict) -> dict:
        """
        Шифрование чувствительных полей
        """
        sensitive_fields = ['inn', 'phone', 'email', 'company_name']
        cipher = Fernet(self.encryption_key)
        
        for field in sensitive_fields:
            if field in data:
                encrypted_value = cipher.encrypt(data[field].encode())
                data[field] = base64.b64encode(encrypted_value).decode()
                
        return data
```

**Аудиторский след интеграций:**
```python
class OneCSecurityLog(models.Model):
    """
    Журнал безопасности для интеграций с 1С
    """
    
    operation_type = models.CharField(max_length=50, choices=[
        ('api_request', 'API запрос к 1С'),
        ('webhook_received', 'Получен webhook от 1С'),
        ('file_exchange', 'Файловый обмен'),
        ('auth_attempt', 'Попытка аутентификации'),
        ('security_violation', 'Нарушение безопасности')
    ])
    
    status = models.CharField(max_length=20, choices=[
        ('success', 'Успешно'),
        ('failed', 'Ошибка'),
        ('blocked', 'Заблокировано'),
        ('suspicious', 'Подозрительно')
    ])
    
    source_ip = models.GenericIPAddressField()
    user_agent = models.TextField(blank=True)
    request_signature = models.CharField(max_length=128)
    response_code = models.IntegerField(null=True, blank=True)
    security_context = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['operation_type', 'status', 'created_at']),
            models.Index(fields=['source_ip', 'created_at']),
        ]
```

### 1.4. Защита от основных угроз

**OWASP Top 10 Defense:**
```python
# 1. SQL Injection Protection
class SecureQuerySet(models.QuerySet):
    def secure_filter(self, **kwargs):
        # Валидация параметров перед фильтрацией
        validated_params = self._validate_filter_params(kwargs)
        return self.filter(**validated_params)

# 2. XSS Protection  
class XSSProtectionMiddleware:
    def process_response(self, request, response):
        response['X-XSS-Protection'] = '1; mode=block'
        response['X-Content-Type-Options'] = 'nosniff'
        response['X-Frame-Options'] = 'DENY'
        return response

# 3. CSRF Protection для API
class CSRFExemptMixin:
    """
    Освобождение от CSRF только для API с JWT токенами
    """
    @method_decorator(csrf_exempt)
    def dispatch(self, request, *args, **kwargs):
        # Проверка наличия валидного JWT токена
        if not self._has_valid_jwt(request):
            raise PermissionDenied("Invalid JWT token")
        return super().dispatch(request, *args, **kwargs)

# 4. Sensitive Data Exposure Prevention
class DataMaskingMixin:
    """
    Маскировка чувствительных данных в логах
    """
    
    SENSITIVE_FIELDS = ['password', 'inn', 'phone', 'email', 'api_key']
    
    def mask_sensitive_data(self, data):
        if isinstance(data, dict):
            return {k: self._mask_value(k, v) for k, v in data.items()}
        return data
    
    def _mask_value(self, key, value):
        if key.lower() in self.SENSITIVE_FIELDS:
            return f"{str(value)[:2]}***{str(value)[-2:]}"
        return value
```

---

## 2. Производительность и оптимизация

### 2.1. Кэширование данных

**Многоуровневая стратегия кэширования:**
```python
class CacheManager:
    """
    Централизованное управление кэшированием
    """
    
    CACHE_TIMEOUTS = {
        'product_list': 300,        # 5 минут
        'product_detail': 1800,     # 30 минут  
        'category_tree': 3600,      # 1 час
        'user_permissions': 900,    # 15 минут
        'price_data': 600,          # 10 минут (частые обновления из 1С)
        'stock_data': 120,          # 2 минуты (критично для заказов)
        'onec_integration': 60      # 1 минута (частая синхронизация)
    }
    
    def get_or_set_cache(self, cache_key: str, callable_func, timeout: int = None):
        """
        Универсальный метод для работы с кэшем
        """
        cached_data = cache.get(cache_key)
        if cached_data is not None:
            return cached_data
            
        fresh_data = callable_func()
        cache_timeout = timeout or self.CACHE_TIMEOUTS.get(cache_key.split(':')[0], 300)
        cache.set(cache_key, fresh_data, cache_timeout)
        return fresh_data
    
    def invalidate_related_cache(self, model_name: str, instance_id: int = None):
        """
        Инвалидация связанного кэша при обновлении данных
        """
        patterns_to_clear = {
            'product': [
                f'product_detail:{instance_id}',
                'product_list:*',
                'category_tree:*',
                'price_data:*'
            ],
            'user': [
                f'user_permissions:{instance_id}',
                'user_dashboard:*'
            ],
            'order': [
                f'user_orders:{instance_id}',
                'stock_data:*'
            ]
        }
        
        for pattern in patterns_to_clear.get(model_name, []):
            cache.delete_pattern(pattern)

# Декоратор для автоматического кэширования API responses
def cache_api_response(timeout=300, vary_on_user=False):
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(self, request, *args, **kwargs):
            cache_key_parts = [
                f"{self.__class__.__name__}",
                f"{view_func.__name__}",
                hashlib.md5(str(sorted(request.GET.items())).encode()).hexdigest()
            ]
            
            if vary_on_user and request.user.is_authenticated:
                cache_key_parts.append(f"user_{request.user.id}")
                
            cache_key = ":".join(cache_key_parts)
            
            cached_response = cache.get(cache_key)
            if cached_response:
                return cached_response
                
            response = view_func(self, request, *args, **kwargs)
            cache.set(cache_key, response, timeout)
            return response
            
        return wrapper
    return decorator
```

### 2.2. Оптимизация базы данных

**Индексирование и оптимизация запросов:**
```python
class OptimizedProductQuerySet(models.QuerySet):
    """
    Оптимизированные запросы для товаров
    """
    
    def with_prices_for_user(self, user):
        """
        Загрузка только необходимых цен для пользователя
        """
        price_fields = self._get_price_fields_for_user(user)
        return self.select_related('category', 'brand').only(
            'id', 'name', 'article', 'image_url', 'is_active', 
            'stock_quantity', *price_fields
        )
    
    def available_only(self):
        """
        Только товары в наличии
        """
        return self.filter(is_active=True, stock_quantity__gt=0)
    
    def with_prefetched_relations(self):
        """
        Предварительная загрузка связанных данных
        """
        return self.select_related(
            'category', 
            'brand'
        ).prefetch_related(
            'specifications',
            'images'
        )

# Индексы для высокой производительности
class ProductMeta:
    indexes = [
        models.Index(fields=['category', 'is_active', 'stock_quantity']),
        models.Index(fields=['brand', 'is_active']),
        models.Index(fields=['article']),
        models.Index(fields=['name']),
        models.Index(fields=['-created_at']),
        
        # Составные индексы для сложных запросов
        models.Index(fields=['category', 'brand', 'is_active']),
        models.Index(fields=['is_active', 'stock_quantity', '-created_at']),
        
        # Индексы для интеграции с 1С
        models.Index(fields=['onec_id']),
        models.Index(fields=['onec_id', 'is_active']),
    ]
```

### 2.3. Оптимизация 1С интеграций

**Производительная синхронизация данных:**
```python
class OneCPerformanceOptimizer:
    """
    Оптимизация производительности интеграций с 1С
    """
    
    BATCH_SIZES = {
        'products': 100,     # товары небольшими пакетами
        'customers': 50,     # покупатели требуют больше обработки  
        'orders': 25,        # заказы с детализацией
        'stock': 200         # остатки можно большими пакетами
    }
    
    def __init__(self):
        self.connection_pool = self._create_connection_pool()
        self.circuit_breaker = OneCCircuitBreaker()
    
    def sync_products_optimized(self, products_data: List[dict]) -> dict:
        """
        Оптимизированная синхронизация товаров
        """
        batch_size = self.BATCH_SIZES['products']
        total_processed = 0
        errors = []
        
        # Подготовка данных для bulk операций
        products_to_update = []
        products_to_create = []
        
        for batch in self._chunks(products_data, batch_size):
            try:
                # Определяем какие товары нужно создать, а какие обновить
                existing_ids = set(
                    Product.objects.filter(
                        onec_id__in=[p['onec_id'] for p in batch]
                    ).values_list('onec_id', flat=True)
                )
                
                for product_data in batch:
                    if product_data['onec_id'] in existing_ids:
                        products_to_update.append(self._prepare_for_update(product_data))
                    else:
                        products_to_create.append(self._prepare_for_create(product_data))
                
                # Bulk операции каждые N товаров
                if len(products_to_create) >= batch_size:
                    Product.objects.bulk_create(products_to_create, batch_size=batch_size)
                    products_to_create.clear()
                    
                if len(products_to_update) >= batch_size:
                    Product.objects.bulk_update(
                        products_to_update, 
                        ['name', 'retail_price', 'stock_quantity', 'updated_at'],
                        batch_size=batch_size
                    )
                    products_to_update.clear()
                
                total_processed += len(batch)
                
            except Exception as e:
                errors.append(f"Batch error: {str(e)}")
                continue
        
        # Обработка оставшихся товаров
        if products_to_create:
            Product.objects.bulk_create(products_to_create, batch_size=batch_size)
        if products_to_update:
            Product.objects.bulk_update(
                products_to_update,
                ['name', 'retail_price', 'stock_quantity', 'updated_at'],
                batch_size=batch_size
            )
        
        # Инвалидация кэша после успешной синхронизации
        self._invalidate_product_cache()
        
        return {
            'total_processed': total_processed,
            'errors_count': len(errors),
            'errors': errors[:10]  # Только первые 10 ошибок
        }
    
    def _create_connection_pool(self):
        """
        Пул соединений для 1С API
        """
        return HTTPConnectionPool(
            host=settings.ONEC_HOST,
            port=settings.ONEC_PORT,
            maxsize=10,
            block=True
        )
    
    def _chunks(self, lst: List, chunk_size: int):
        """
        Разбивка списка на чанки
        """
        for i in range(0, len(lst), chunk_size):
            yield lst[i:i + chunk_size]
```

### 2.4. Мониторинг производительности

**Real-time метрики:**
```python
class PerformanceMonitor:
    """
    Мониторинг производительности системы
    """
    
    def __init__(self):
        self.metrics = defaultdict(list)
        self.thresholds = {
            'api_response_time': 500,     # мс
            'db_query_time': 100,         # мс  
            'cache_hit_ratio': 0.85,      # 85%
            'onec_sync_time': 30000,      # 30 сек
            'memory_usage': 0.8           # 80%
        }
    
    @contextmanager
    def measure_time(self, operation_name: str):
        """
        Измерение времени выполнения операций
        """
        start_time = time.time()
        try:
            yield
        finally:
            duration = (time.time() - start_time) * 1000  # в миллисекундах
            self._record_metric(operation_name, duration)
            
            # Проверка превышения порога
            threshold = self.thresholds.get(operation_name)
            if threshold and duration > threshold:
                self._alert_performance_issue(operation_name, duration, threshold)
    
    def get_performance_report(self) -> dict:
        """
        Генерация отчета о производительности
        """
        report = {}
        
        for metric_name, values in self.metrics.items():
            if values:
                report[metric_name] = {
                    'avg': sum(values) / len(values),
                    'min': min(values),
                    'max': max(values),
                    'count': len(values),
                    'threshold': self.thresholds.get(metric_name),
                    'violations': len([v for v in values if v > self.thresholds.get(metric_name, float('inf'))])
                }
        
        return report

# Middleware для мониторинга API performance
class APIPerformanceMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
        self.monitor = PerformanceMonitor()
    
    def __call__(self, request):
        with self.monitor.measure_time('api_response_time'):
            response = self.get_response(request)
        
        # Логирование медленных запросов
        if hasattr(response, '_duration') and response._duration > 1000:
            logger.warning(
                f"Slow API request: {request.path} took {response._duration}ms",
                extra={
                    'path': request.path,
                    'method': request.method,
                    'user_id': getattr(request.user, 'id', None),
                    'duration': response._duration
                }
            )
        
        return response
```

---

## 3. Мониторинг и алертинг

### 3.1. Система мониторинга

**Комплексный мониторинг:**
```python
class SystemHealthMonitor:
    """
    Мониторинг здоровья системы
    """
    
    def __init__(self):
        self.health_checks = [
            self._check_database_health,
            self._check_redis_health,
            self._check_celery_health,
            self._check_onec_integration_health,
            self._check_disk_space,
            self._check_memory_usage
        ]
    
    def perform_health_check(self) -> dict:
        """
        Выполнение проверки здоровья системы
        """
        results = {}
        overall_status = 'healthy'
        
        for check in self.health_checks:
            try:
                check_name = check.__name__.replace('_check_', '').replace('_health', '')
                result = check()
                results[check_name] = result
                
                if result['status'] != 'healthy':
                    overall_status = 'degraded' if overall_status == 'healthy' else 'unhealthy'
                    
            except Exception as e:
                results[check_name] = {
                    'status': 'error',
                    'message': str(e),
                    'timestamp': datetime.now().isoformat()
                }
                overall_status = 'unhealthy'
        
        return {
            'overall_status': overall_status,
            'timestamp': datetime.now().isoformat(),
            'checks': results
        }
    
    def _check_onec_integration_health(self) -> dict:
        """
        Проверка здоровья интеграции с 1С
        """
        try:
            # Проверка последней синхронизации
            last_sync = ImportLog.objects.filter(
                operation_type='import_products'
            ).order_by('-created_at').first()
            
            if not last_sync:
                return {
                    'status': 'warning',
                    'message': 'No synchronization logs found',
                    'last_sync': None
                }
            
            time_since_last_sync = datetime.now() - last_sync.created_at.replace(tzinfo=None)
            
            # Проверка актуальности синхронизации (не старше 2 часов)
            if time_since_last_sync > timedelta(hours=2):
                return {
                    'status': 'unhealthy',
                    'message': f'Last sync was {time_since_last_sync} ago',
                    'last_sync': last_sync.created_at.isoformat()
                }
            
            # Проверка успешности последних синхронизаций
            recent_syncs = ImportLog.objects.filter(
                created_at__gte=datetime.now() - timedelta(hours=24)
            )
            
            failed_syncs = recent_syncs.filter(status='failed').count()
            total_syncs = recent_syncs.count()
            
            if total_syncs > 0:
                failure_rate = failed_syncs / total_syncs
                if failure_rate > 0.1:  # Более 10% неудачных синхронизаций
                    return {
                        'status': 'degraded',
                        'message': f'High failure rate: {failure_rate:.1%}',
                        'failed_syncs': failed_syncs,
                        'total_syncs': total_syncs
                    }
            
            return {
                'status': 'healthy',
                'message': 'Integration working normally',
                'last_sync': last_sync.created_at.isoformat(),
                'recent_success_rate': f'{((total_syncs - failed_syncs) / total_syncs * 100):.1f}%' if total_syncs > 0 else 'N/A'
            }
            
        except Exception as e:
            return {
                'status': 'error',
                'message': f'Health check failed: {str(e)}'
            }

class AlertManager:
    """
    Управление алертами и уведомлениями
    """
    
    ALERT_CHANNELS = ['email', 'slack', 'telegram']
    
    ALERT_THRESHOLDS = {
        'api_response_time': 1000,      # мс
        'error_rate': 0.05,             # 5%
        'memory_usage': 0.85,           # 85%
        'disk_usage': 0.9,              # 90%
        'failed_sync_rate': 0.1         # 10%
    }
    
    def send_alert(self, alert_type: str, message: str, severity: str = 'warning'):
        """
        Отправка алерта через настроенные каналы
        """
        alert_data = {
            'type': alert_type,
            'message': message,
            'severity': severity,
            'timestamp': datetime.now().isoformat(),
            'hostname': socket.gethostname()
        }
        
        for channel in self.ALERT_CHANNELS:
            try:
                self._send_to_channel(channel, alert_data)
            except Exception as e:
                logger.error(f"Failed to send alert to {channel}: {e}")
    
    def _send_to_channel(self, channel: str, alert_data: dict):
        """
        Отправка в конкретный канал уведомлений
        """
        if channel == 'email':
            self._send_email_alert(alert_data)
        elif channel == 'slack':
            self._send_slack_alert(alert_data)
        elif channel == 'telegram':
            self._send_telegram_alert(alert_data)
```

---

## 4. Резервное копирование и восстановление

### 4.1. Стратегия резервного копирования

**Автоматизированное резервное копирование:**
```python
class BackupManager:
    """
    Управление резервным копированием
    """
    
    BACKUP_TYPES = {
        'full': 'Полное резервное копирование',
        'incremental': 'Инкрементальное копирование',
        'differential': 'Дифференциальное копирование'
    }
    
    def __init__(self):
        self.storage_backends = [
            'local_storage',
            's3_storage',
            'ftp_storage'
        ]
    
    def create_database_backup(self, backup_type: str = 'full') -> dict:
        """
        Создание резервной копии базы данных
        """
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_filename = f"freesport_backup_{backup_type}_{timestamp}.sql.gz"
        
        try:
            # Создание дампа БД
            dump_command = [
                'pg_dump',
                f"--host={settings.DATABASES['default']['HOST']}",
                f"--port={settings.DATABASES['default']['PORT']}",
                f"--username={settings.DATABASES['default']['USER']}",
                f"--dbname={settings.DATABASES['default']['NAME']}",
                '--verbose',
                '--clean',
                '--no-owner',
                '--no-privileges'
            ]
            
            with tempfile.NamedTemporaryFile() as temp_file:
                # Выполнение pg_dump
                process = subprocess.run(
                    dump_command,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    env={'PGPASSWORD': settings.DATABASES['default']['PASSWORD']}
                )
                
                if process.returncode != 0:
                    raise Exception(f"pg_dump failed: {process.stderr.decode()}")
                
                # Сжатие дампа
                compressed_data = gzip.compress(process.stdout)
                
                # Сохранение в хранилища
                storage_results = []
                for backend in self.storage_backends:
                    try:
                        result = self._save_to_storage(backend, backup_filename, compressed_data)
                        storage_results.append({
                            'backend': backend,
                            'status': 'success',
                            'size': len(compressed_data),
                            'path': result['path']
                        })
                    except Exception as e:
                        storage_results.append({
                            'backend': backend,
                            'status': 'error',
                            'error': str(e)
                        })
            
            # Логирование резервной копии
            BackupLog.objects.create(
                backup_type=backup_type,
                filename=backup_filename,
                size=len(compressed_data),
                status='completed' if any(r['status'] == 'success' for r in storage_results) else 'failed',
                storage_results=storage_results
            )
            
            return {
                'status': 'success',
                'filename': backup_filename,
                'size': len(compressed_data),
                'storage_results': storage_results
            }
            
        except Exception as e:
            BackupLog.objects.create(
                backup_type=backup_type,
                filename=backup_filename,
                status='failed',
                error_message=str(e)
            )
            
            return {
                'status': 'error',
                'message': str(e)
            }

# Модель для логирования бэкапов
class BackupLog(models.Model):
    backup_type = models.CharField(max_length=20, choices=BackupManager.BACKUP_TYPES)
    filename = models.CharField(max_length=255)
    size = models.BigIntegerField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=[
        ('running', 'Выполняется'),
        ('completed', 'Завершено'),
        ('failed', 'Ошибка')
    ])
    storage_results = models.JSONField(default=list)
    error_message = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', 'created_at']),
            models.Index(fields=['backup_type', 'created_at'])
        ]
```

---

## 5. Соответствие стандартам безопасности

### 5.1. Compliance и аудит

**GDPR и защита персональных данных:**
```python
class GDPRComplianceManager:
    """
    Обеспечение соответствия GDPR
    """
    
    PERSONAL_DATA_FIELDS = [
        'email', 'phone', 'first_name', 'last_name',
        'company_name', 'tax_id', 'address'
    ]
    
    def anonymize_user_data(self, user_id: int) -> dict:
        """
        Анонимизация данных пользователя
        """
        try:
            user = User.objects.get(id=user_id)
            
            # Замена персональных данных на анонимные
            anonymized_data = {
                'email': f'deleted_{user_id}@deleted.local',
                'phone': '',
                'first_name': 'Deleted',
                'last_name': 'User',
                'company_name': '',
                'tax_id': '',
                'is_active': False
            }
            
            # Обновление пользователя
            for field, value in anonymized_data.items():
                setattr(user, field, value)
            user.save()
            
            # Анонимизация связанных заказов
            user.orders.update(
                customer_email=anonymized_data['email'],
                customer_phone=anonymized_data['phone'],
                customer_name=f"{anonymized_data['first_name']} {anonymized_data['last_name']}"
            )
            
            # Логирование GDPR операции
            GDPRLog.objects.create(
                user_id=user_id,
                operation='anonymize',
                status='completed',
                details={'anonymized_fields': list(anonymized_data.keys())}
            )
            
            return {'status': 'success', 'message': 'User data anonymized'}
            
        except User.DoesNotExist:
            return {'status': 'error', 'message': 'User not found'}
        except Exception as e:
            return {'status': 'error', 'message': str(e)}
    
    def export_user_data(self, user_id: int) -> dict:
        """
        Экспорт всех данных пользователя (право на портативность данных)
        """
        try:
            user = User.objects.get(id=user_id)
            
            export_data = {
                'user_profile': {
                    'id': user.id,
                    'email': user.email,
                    'first_name': user.first_name,
                    'last_name': user.last_name,
                    'phone': user.phone,
                    'role': user.role,
                    'created_at': user.created_at.isoformat(),
                    'last_login': user.last_login.isoformat() if user.last_login else None
                },
                'orders': list(user.orders.values(
                    'id', 'status', 'total_amount', 'created_at'
                )),
                'cart_items': list(user.cart_items.values(
                    'product__name', 'quantity', 'price'
                )),
                'sync_logs': list(CustomerSyncLog.objects.filter(
                    customer=user
                ).values('operation_type', 'status', 'created_at'))
            }
            
            # Логирование экспорта данных
            GDPRLog.objects.create(
                user_id=user_id,
                operation='export',
                status='completed'
            )
            
            return {
                'status': 'success',
                'data': export_data,
                'exported_at': datetime.now().isoformat()
            }
            
        except User.DoesNotExist:
            return {'status': 'error', 'message': 'User not found'}
        except Exception as e:
            return {'status': 'error', 'message': str(e)}

class GDPRLog(models.Model):
    """
    Журнал GDPR операций
    """
    user_id = models.IntegerField()
    operation = models.CharField(max_length=20, choices=[
        ('export', 'Экспорт данных'),
        ('anonymize', 'Анонимизация'),
        ('delete', 'Удаление'),
        ('consent_given', 'Согласие получено'),
        ('consent_withdrawn', 'Согласие отозвано')
    ])
    status = models.CharField(max_length=20, choices=[
        ('completed', 'Завершено'),
        ('failed', 'Ошибка')
    ])
    details = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['user_id', 'operation', 'created_at']),
        ]
```

---

Обновленная архитектура безопасности и производительности обеспечивает:

1. **Многослойную защиту** с JWT аутентификацией и ролевой моделью
2. **Безопасную интеграцию с 1С** через шифрование и подписи
3. **Высокую производительность** благодаря многоуровневому кэшированию
4. **Комплексный мониторинг** системы и интеграций
5. **Соответствие GDPR** и международным стандартам безопасности