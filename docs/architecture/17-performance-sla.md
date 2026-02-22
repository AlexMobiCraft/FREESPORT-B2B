# 17. Performance SLA и Метрики

## Обзор

Этот документ определяет Service Level Agreements (SLA) для производительности платформы FREESPORT, основанный на существующих performance тестах и мониторинге.

## Существующая Инфраструктура Производительности

### Performance тесты (backend/tests/performance/)

Проект уже содержит комплексные тесты производительности:

- **test_catalog_performance.py**: каталог товаров, фильтрация, пагинация
- **test_search_performance.py**: поиск и индексирование  
- **test_order_creation_performance.py**: создание заказов

### Индексы БД (apps/users/migrations/0003_add_performance_indexes.py)

Оптимизированные индексы для критических запросов:
- B2B пользователи: `users_b2b_users_idx`
- Email + статус: `users_email_active_idx`  
- Адреса по умолчанию: `addresses_default_idx`
- ИНН компаний: `companies_tax_id_idx`

### Кэширование (Redis)

Настроенное в `settings/base.py` и `docker-compose.yml`:
- Redis 7.0+ с persistence
- Django-redis backend
- Session и cache storage

## SLA Метрики

### Базовые SLA (из docs/architecture/13-monitoring.md)

| Метрика | SLA | Источник |
|---------|-----|----------|
| API response time | < 2 сек | Мониторинг |
| Database query time | < 1 сек | Мониторинг |
| Error rate | < 5% | Мониторинг |
| System uptime | 99.9% | Мониторинг |
| CPU usage | < 75% | Мониторинг |
| Memory usage | < 80% | Мониторинг |
| Disk usage | < 85% | Мониторинг |

### Детализированные Performance SLA (из тестов)

#### Каталог товаров
```python
# Основанные на test_catalog_performance.py
```

| Endpoint | SLA | Тест |
|----------|-----|------|
| `GET /api/v1/products/` | < 1.0 сек | `test_catalog_list_performance` |
| `GET /api/v1/products/?filters` | < 1.5 сек | `test_catalog_with_filters_performance` |
| `GET /api/v1/products/{id}/` | < 0.5 сек | `test_product_detail_performance` |
| `GET /api/v1/categories-tree/` | < 0.3 сек | `test_categories_tree_performance` |
| `GET /api/v1/brands/` | < 0.2 сек | `test_brands_list_performance` |

#### Пагинация и производительность
| Метрика | SLA | Описание |
|---------|-----|----------|
| Страница каталога (20 товаров) | < 1.0 сек | Стандартная пагинация |
| Ролевое ценообразование | < 1.2 сек | Каталог с ролевыми ценами |
| DB queries за запрос | < 10 запросов | Контроль N+1 проблемы |
| Использование памяти | < 50MB | Per request memory usage |

#### Стресс-тесты
| Метрика | SLA | Условие |
|---------|-----|---------|
| Среднее время ответа | < 1.0 сек | 10 последовательных запросов |
| Максимальное время ответа | < 2.0 сек | Пиковая нагрузка |
| Деградация производительности | < 20% | При увеличении нагрузки |

## Мониторинг и Алертинг

### Логирование (settings/production.py)

Структурированное логирование для анализа производительности:

```python
LOGGING = {
    "handlers": {
        "file": {
            "class": "logging.handlers.RotatingFileHandler",
            "filename": BASE_DIR / "logs" / "django.log",
            "maxBytes": 15MB,  # 15MB лог-файлы
            "backupCount": 10,
        }
    }
}
```

### Health Check Endpoints

Health checks для мониторинга доступности (docker-compose.yml):

```yaml
healthcheck:
  test: ["CMD-SHELL", "pg_isready -U postgres -d freesport"]
  interval: 30s
  timeout: 10s  
  retries: 5
```

### Метрики для Dashboard

#### Основные KPI
- **Response Time P50/P95/P99**: медианное, 95-й и 99-й перцентили
- **Throughput**: запросов в секунду (RPS)
- **Error Rate**: процент ошибочных ответов
- **Apdex Score**: Application Performance Index

#### Бизнес-метрики
- **Conversion Rate**: корзина → заказ
- **Page Load Time**: время загрузки каталога
- **Search Performance**: время поиска товаров
- **B2B Response Time**: ролевое ценообразование

#### Инфраструктурные метрики
- **Database Query Time**: среднее время запросов к БД
- **Cache Hit Ratio**: эффективность Redis кэша  
- **Memory Usage**: per-process память
- **Active Connections**: подключения к БД

## Инструменты Мониторинга

### Существующие возможности

1. **Django Debug Toolbar** (development)
   - Профилирование запросов
   - Анализ использования памяти
   - SQL запросы и их время

2. **Performance Tests** (автоматизированные)
   - Регулярные измерения производительности
   - Regression testing
   - Memory profiling с tracemalloc

3. **Redis Monitoring**
   - Cache hit/miss rates
   - Memory usage
   - Connection stats

### Рекомендуемые расширения

1. **APM Solution** (Application Performance Monitoring)
   - Sentry для error tracking
   - New Relic или DataDog для APM
   - Custom metrics через StatsD

2. **Database Monitoring**
   - PostgreSQL статистики
   - Slow query logging
   - Connection pooling metrics

3. **Infrastructure Monitoring**
   - Docker container metrics
   - System resources (CPU, Memory, Disk)
   - Network latency

## Escalation и Response

### Критичность инцидентов

#### P1 - Critical (< 15 минут response)
- API downtime > 1 минута
- Error rate > 25%
- Response time > 5 секунд

#### P2 - High (< 1 час response)  
- Error rate 10-25%
- Response time 2-5 секунд
- Database connection issues

#### P3 - Medium (< 4 часа response)
- Error rate 5-10% 
- Response time превышает SLA на 20%
- Cache miss rate > 30%

#### P4 - Low (< 1 день response)
- Performance degradation < 20%
- Non-critical feature issues
- Optimization opportunities

### Автоматические действия

1. **Auto-scaling** при превышении CPU/Memory лимитов
2. **Circuit breaker** для внешних API
3. **Rate limiting** при аномальной нагрузке
4. **Cache warming** для критических данных

## Performance Optimization Plan

### Краткосрочные улучшения (1-2 недели)

1. **Database optimization**
   - Добавить недостающие индексы на основе slow query log
   - Настроить connection pooling
   - Включить query optimization

2. **Caching enhancement**  
   - Расширить кэширование для каталога
   - Implement cache warming
   - Template fragment caching

3. **Static assets optimization**
   - CDN для статики
   - Image optimization
   - Asset compression

### Среднесрочные улучшения (1-2 месяца)

1. **API optimization**
   - Implement GraphQL для complex queries
   - API response compression
   - Pagination optimization

2. **Background processing**
   - Celery task optimization
   - Async processing для non-critical tasks
   - Queue monitoring

3. **Frontend performance**
   - Next.js optimization
   - Code splitting
   - Lazy loading

### Долгосрочные улучшения (3-6 месяцев)

1. **Architecture evolution**
   - Microservices для высоконагруженных компонентов
   - Read replicas для БД
   - Horizontal scaling

2. **Advanced monitoring**
   - Real User Monitoring (RUM)
   - Synthetic monitoring
   - Predictive alerting

## Тестирование и Валидация

### Performance Testing Pipeline

Интеграция с существующими тестами:

```bash
# Запуск performance тестов
pytest tests/performance/ -v

# Stress testing
pytest tests/performance/ -m slow

# Memory profiling  
pytest tests/performance/ --profile-memory
```

### Load Testing

Регулярные load тесты для валидации SLA:

1. **Baseline testing**: установка базовых метрик
2. **Regression testing**: проверка после деплоя  
3. **Stress testing**: поиск пределов производительности
4. **Endurance testing**: проверка на длительной нагрузке

### Continuous Performance Monitoring

1. **Pre-deployment testing**: обязательные performance тесты
2. **Post-deployment validation**: проверка SLA после релиза
3. **Continuous profiling**: мониторинг в продакшене  
4. **Performance budgets**: лимиты для CI/CD pipeline

## Заключение

Данный SLA документ основан на уже существующей инфраструктуре производительности FREESPORT:

- ✅ Комплексные performance тесты с четкими лимитами
- ✅ Оптимизированные индексы БД
- ✅ Redis кэширование и логирование  
- ✅ Health checks и мониторинг

Следующие шаги:
1. Внедрить автоматический мониторинг SLA метрик
2. Настроить alerting для критических нарушений  
3. Создать performance dashboard
4. Регулярно пересматривать и обновлять SLA на основе реальных данных