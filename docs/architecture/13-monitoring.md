# 13. Мониторинг и Наблюдаемость

## System Health Monitoring

**Key Metrics:**

- API response time (SLA: < 2 секунды)
- Database query time (SLA: < 1 секунда)
- Error rate (SLA: < 5%)
- System uptime (SLA: 99.9%)
- Resource utilization (CPU < 75%, Memory < 80%, Disk < 85%)

## Health Check Endpoints

### Публичный health check

`GET /api/v1/health/` — базовая проверка доступности API (без авторизации).

### Мониторинг интеграций (требуется admin)

| Эндпоинт | Описание |
|---|---|
| `GET /api/v1/monitoring/health/` | Общий статус здоровья системы интеграций (200 или 503) |
| `GET /api/v1/monitoring/metrics/business/` | Бизнес-метрики синхронизации за период |
| `GET /api/v1/monitoring/metrics/realtime/` | Метрики в реальном времени (последние 5 минут) |
| `GET /api/v1/monitoring/metrics/operations/` | Операционные метрики |

Все monitoring-эндпоинты требуют авторизацию (JWT, роль admin).

## Реализованные компоненты

- **CustomerSyncMonitor** (`apps/common/services/customer_sync_monitor.py`) — мониторинг синхронизации 1С
- **Alerting** (`apps/common/services/alerting.py`) — отправка уведомлений через `NotificationRecipient`
- **Monitoring Dashboard** — Django Admin template (`monitoring_dashboard.html`)

## Планируемые компоненты

- Sentry (error tracking) — не подключён
- Grafana + Prometheus (метрики) — не подключены
- Автоматический дашборд инфраструктурных метрик
