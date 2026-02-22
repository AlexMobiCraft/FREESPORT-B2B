# 12. Стратегия Обработки Ошибок

## Обзор

FREESPORT платформа использует комплексную стратегию обработки ошибок для обеспечения надежности системы и хорошего пользовательского опыта. Особое внимание уделяется обработке ошибок интеграции с 1С ERP и других внешних сервисов.

---

## 1. Архитектура обработки ошибок

### 1.1. Иерархия исключений

**Базовые классы исключений:**
```python
from django.utils.translation import gettext as _
import logging

logger = logging.getLogger(__name__)

class FreeSportException(Exception):
    """
    Базовый класс для всех пользовательских исключений FREESPORT
    """
    default_message = _("Произошла ошибка в системе")
    default_code = "FREESPORT_ERROR" 
    default_status = 500
    
    def __init__(self, message=None, code=None, status=None, details=None):
        self.message = message or self.default_message
        self.code = code or self.default_code
        self.status = status or self.default_status
        self.details = details or {}
        super().__init__(self.message)
    
    def to_dict(self):
        return {
            'error': True,
            'code': self.code,
            'message': str(self.message),
            'details': self.details,
            'status': self.status
        }

class ValidationException(FreeSportException):
    """Ошибки валидации данных"""
    default_code = "VALIDATION_ERROR"
    default_message = _("Ошибка валидации данных")
    default_status = 400

class BusinessLogicException(FreeSportException):
    """Нарушение бизнес-правил"""
    default_code = "BUSINESS_LOGIC_ERROR"
    default_message = _("Нарушение бизнес-правил")
    default_status = 422

class InsufficientStockException(BusinessLogicException):
    """Недостаточно товара в наличии"""
    default_code = "INSUFFICIENT_STOCK"
    default_message = _("Недостаточно товара в наличии")
    default_status = 409

class PaymentException(FreeSportException):
    """Ошибки платежных систем"""
    default_code = "PAYMENT_FAILED"
    default_message = _("Ошибка при обработке платежа")
    default_status = 402

class IntegrationException(FreeSportException):
    """Ошибки внешних интеграций"""
    default_code = "INTEGRATION_ERROR"
    default_message = _("Ошибка внешней интеграции")
    default_status = 503

class OneCIntegrationException(IntegrationException):
    """Ошибки интеграции с 1С"""
    default_code = "ONEC_INTEGRATION_ERROR"  
    default_message = _("Ошибка интеграции с 1С")
    default_status = 503
```

### 1.2. Глобальный обработчик исключений

**Централизованная обработка ошибок:**
```python
from django.http import JsonResponse
from rest_framework.views import exception_handler
from rest_framework import status
import traceback
import sys

def custom_exception_handler(exc, context):
    """
    Глобальный обработчик исключений для DRF
    """
    # Получаем стандартную обработку ошибок
    response = exception_handler(exc, context)
    
    # Получаем информацию о запросе
    request = context.get('request')
    view = context.get('view')
    
    # Создаем контекст ошибки для логирования
    error_context = {
        'view': view.__class__.__name__ if view else 'Unknown',
        'method': request.method if request else 'Unknown',
        'path': request.path if request else 'Unknown',
        'user_id': getattr(request.user, 'id', None) if request and hasattr(request, 'user') else None,
        'ip_address': get_client_ip(request) if request else None
    }
    
    if isinstance(exc, FreeSportException):
        # Обработка пользовательских исключений
        logger.warning(
            f"Business exception in {error_context['view']}: {exc.code} - {exc.message}",
            extra={
                'exception_type': type(exc).__name__,
                'exception_code': exc.code,
                'exception_details': exc.details,
                **error_context
            }
        )
        
        return JsonResponse(
            exc.to_dict(),
            status=exc.status
        )
    
    elif response is not None:
        # Обработка стандартных DRF ошибок
        custom_response_data = {
            'error': True,
            'code': get_error_code_from_status(response.status_code),
            'message': get_user_friendly_message(response.status_code, response.data),
            'details': response.data if response.status_code < 500 else {},
            'status': response.status_code
        }
        
        # Логирование в зависимости от уровня ошибки
        if response.status_code >= 500:
            logger.error(
                f"Server error in {error_context['view']}: {exc}",
                extra={
                    'exception_type': type(exc).__name__,
                    'traceback': traceback.format_exception(*sys.exc_info()),
                    **error_context
                }
            )
        else:
            logger.warning(
                f"Client error in {error_context['view']}: {exc}",
                extra={
                    'exception_type': type(exc).__name__,
                    **error_context
                }
            )
        
        response.data = custom_response_data
        return response
    
    else:
        # Необработанные исключения (500 ошибки)
        logger.error(
            f"Unhandled exception in {error_context['view']}: {exc}",
            extra={
                'exception_type': type(exc).__name__,
                'traceback': traceback.format_exception(*sys.exc_info()),
                **error_context
            }
        )
        
        return JsonResponse({
            'error': True,
            'code': 'INTERNAL_SERVER_ERROR',
            'message': _('Внутренняя ошибка сервера'),
            'details': {},
            'status': 500
        }, status=500)

def get_error_code_from_status(status_code):
    """Получение кода ошибки по HTTP статусу"""
    codes = {
        400: 'BAD_REQUEST',
        401: 'UNAUTHORIZED', 
        403: 'FORBIDDEN',
        404: 'NOT_FOUND',
        405: 'METHOD_NOT_ALLOWED',
        409: 'CONFLICT',
        422: 'UNPROCESSABLE_ENTITY',
        429: 'TOO_MANY_REQUESTS',
        500: 'INTERNAL_SERVER_ERROR',
        502: 'BAD_GATEWAY',
        503: 'SERVICE_UNAVAILABLE',
        504: 'GATEWAY_TIMEOUT'
    }
    return codes.get(status_code, 'UNKNOWN_ERROR')

def get_user_friendly_message(status_code, data):
    """Получение понятного пользователю сообщения"""
    friendly_messages = {
        400: _('Некорректные данные в запросе'),
        401: _('Необходимо войти в систему'),
        403: _('Недостаточно прав для выполнения операции'),
        404: _('Запрашиваемый ресурс не найден'),
        405: _('Метод не поддерживается'),
        409: _('Конфликт данных'),
        422: _('Ошибка валидации данных'),
        429: _('Слишком много запросов'),
        500: _('Внутренняя ошибка сервера'),
        502: _('Ошибка внешнего сервиса'),
        503: _('Сервис временно недоступен'),
        504: _('Превышено время ожидания')
    }
    return friendly_messages.get(status_code, _('Произошла ошибка'))
```

---

## 2. Обработка ошибок интеграции с 1С

### 2.1. Специфичные исключения для 1С

**Детализированные ошибки интеграции:**
```python
class OneCConnectionException(OneCIntegrationException):
    """Ошибка подключения к 1С"""
    default_code = "ONEC_CONNECTION_ERROR"
    default_message = _("Не удается подключиться к системе 1С")

class OneCAuthenticationException(OneCIntegrationException):
    """Ошибка аутентификации в 1С"""
    default_code = "ONEC_AUTH_ERROR"
    default_message = _("Ошибка аутентификации в системе 1С")

class OneCDataFormatException(OneCIntegrationException):
    """Ошибка формата данных от 1С"""
    default_code = "ONEC_DATA_FORMAT_ERROR"
    default_message = _("Неверный формат данных от системы 1С")

class OneCBusinessLogicException(OneCIntegrationException):
    """Бизнес-ошибки от 1С"""
    default_code = "ONEC_BUSINESS_ERROR"
    default_message = _("Бизнес-ошибка в системе 1С")

class OneCTimeoutException(OneCIntegrationException):
    """Превышение времени ожидания 1С"""
    default_code = "ONEC_TIMEOUT_ERROR"
    default_message = _("Превышено время ожидания ответа от 1С")
```

### 2.2. Обработчик ошибок интеграции

**Специализированный обработчик для 1С:**
```python
class OneCErrorHandler:
    """
    Обработчик ошибок интеграции с 1С
    """
    
    def __init__(self):
        self.circuit_breaker = OneCCircuitBreaker()
        self.retry_policy = RetryPolicy()
        
    def handle_integration_error(self, error: Exception, context: dict) -> dict:
        """
        Основной метод обработки ошибок интеграции
        """
        error_type = self._classify_error(error)
        
        # Логирование ошибки
        self._log_error(error, error_type, context)
        
        # Определение стратегии восстановления
        recovery_strategy = self._determine_recovery_strategy(error_type, context)
        
        # Выполнение стратегии восстановления
        recovery_result = self._execute_recovery_strategy(recovery_strategy, context)
        
        # Уведомления при необходимости
        if error_type in ['connection_error', 'authentication_error']:
            self._send_admin_notification(error, context)
        
        return {
            'error_handled': True,
            'error_type': error_type,
            'recovery_strategy': recovery_strategy,
            'recovery_result': recovery_result,
            'timestamp': datetime.now().isoformat()
        }
    
    def _classify_error(self, error: Exception) -> str:
        """
        Классификация типа ошибки
        """
        if isinstance(error, (ConnectionError, requests.exceptions.ConnectionError)):
            return 'connection_error'
        elif isinstance(error, requests.exceptions.Timeout):
            return 'timeout_error'
        elif isinstance(error, requests.exceptions.HTTPError):
            if error.response.status_code == 401:
                return 'authentication_error'
            elif error.response.status_code >= 500:
                return 'server_error'
            else:
                return 'client_error'
        elif isinstance(error, (ValueError, KeyError, TypeError)):
            return 'data_format_error'
        elif isinstance(error, OneCBusinessLogicException):
            return 'business_logic_error'
        else:
            return 'unknown_error'
    
    def _determine_recovery_strategy(self, error_type: str, context: dict) -> str:
        """
        Определение стратегии восстановления
        """
        strategies = {
            'connection_error': 'fallback_to_file_exchange',
            'timeout_error': 'retry_with_backoff',
            'authentication_error': 'refresh_credentials',
            'server_error': 'circuit_breaker_fallback',
            'data_format_error': 'log_and_skip',
            'business_logic_error': 'create_manual_task',
            'unknown_error': 'escalate_to_admin'
        }
        
        return strategies.get(error_type, 'escalate_to_admin')
    
    def _execute_recovery_strategy(self, strategy: str, context: dict) -> dict:
        """
        Выполнение стратегии восстановления
        """
        if strategy == 'fallback_to_file_exchange':
            return self._fallback_to_file_exchange(context)
        elif strategy == 'retry_with_backoff':
            return self._retry_with_backoff(context)
        elif strategy == 'refresh_credentials':
            return self._refresh_credentials(context)
        elif strategy == 'circuit_breaker_fallback':
            return self._circuit_breaker_fallback(context)
        elif strategy == 'log_and_skip':
            return self._log_and_skip(context)
        elif strategy == 'create_manual_task':
            return self._create_manual_task(context)
        else:
            return self._escalate_to_admin(context)
    
    def _fallback_to_file_exchange(self, context: dict) -> dict:
        """
        Переход к файловому обмену при недоступности API
        """
        try:
            file_exchange_service = OneCFileExchangeService()
            result = file_exchange_service.export_to_xml(
                context.get('operation'),
                context.get('data')
            )
            
            return {
                'strategy': 'file_exchange',
                'status': 'success',
                'result': result
            }
        except Exception as e:
            return {
                'strategy': 'file_exchange', 
                'status': 'failed',
                'error': str(e)
            }
    
    def _log_error(self, error: Exception, error_type: str, context: dict):
        """
        Логирование ошибки интеграции
        """
        OneCIntegrationLog.objects.create(
            operation_type=context.get('operation', 'unknown'),
            error_type=error_type,
            error_message=str(error),
            error_details={
                'exception_type': type(error).__name__,
                'traceback': traceback.format_exc(),
                'context': context
            },
            status='error',
            retry_count=context.get('retry_count', 0)
        )

class OneCIntegrationLog(models.Model):
    """
    Журнал ошибок интеграции с 1С
    """
    operation_type = models.CharField(max_length=50, choices=[
        ('import_products', 'Импорт товаров'),
        ('import_customers', 'Импорт покупателей'),
        ('export_orders', 'Экспорт заказов'),
        ('import_stock', 'Импорт остатков'),
        ('webhook_processing', 'Обработка webhook')
    ])
    
    error_type = models.CharField(max_length=50)
    error_message = models.TextField()
    error_details = models.JSONField(default=dict)
    
    status = models.CharField(max_length=20, choices=[
        ('error', 'Ошибка'),
        ('recovered', 'Восстановлено'),
        ('manual_required', 'Требует ручного вмешательства')
    ])
    
    retry_count = models.IntegerField(default=0)
    recovery_strategy = models.CharField(max_length=50, blank=True)
    recovery_result = models.JSONField(default=dict)
    
    created_at = models.DateTimeField(auto_now_add=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['operation_type', 'status', 'created_at']),
            models.Index(fields=['error_type', 'created_at']),
        ]
```

---

## 3. Frontend обработка ошибок

### 3.1. React Error Boundaries

**Глобальные границы ошибок:**
```typescript
import React, { Component, ErrorInfo, ReactNode } from 'react';
import { logger } from '@/utils/logger';

interface Props {
  children: ReactNode;
  fallback?: ReactNode;
}

interface State {
  hasError: boolean;
  error?: Error;
  errorInfo?: ErrorInfo;
}

class ErrorBoundary extends Component<Props, State> {
  public state: State = {
    hasError: false
  };

  public static getDerivedStateFromError(error: Error): State {
    // Обновляет состояние для отображения fallback UI
    return { hasError: true, error };
  }

  public componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    this.setState({ errorInfo });
    
    // Отправка ошибки в систему мониторинга
    logger.error('React Error Boundary caught an error', {
      error: error.message,
      stack: error.stack,
      componentStack: errorInfo.componentStack,
      errorBoundary: this.constructor.name
    });
    
    // Отправка в внешнюю систему мониторинга (например, Sentry)
    if (typeof window !== 'undefined' && window.Sentry) {
      window.Sentry.captureException(error, {
        contexts: { react: { componentStack: errorInfo.componentStack } }
      });
    }
  }

  public render() {
    if (this.state.hasError) {
      return this.props.fallback || (
        <div className="error-boundary">
          <h2>Что-то пошло не так</h2>
          <details style={{ whiteSpace: 'pre-wrap' }}>
            <summary>Детали ошибки</summary>
            <p>Ошибка: {this.state.error?.message}</p>
            <p>Стек: {this.state.error?.stack}</p>
            {this.state.errorInfo && (
              <p>Стек компонентов: {this.state.errorInfo.componentStack}</p>
            )}
          </details>
          <button 
            onClick={() => this.setState({ hasError: false, error: undefined, errorInfo: undefined })}
          >
            Попробовать снова
          </button>
        </div>
      );
    }

    return this.props.children;
  }
}

export default ErrorBoundary;
```

### 3.2. API Error Handling

**Централизованная обработка API ошибок:**
```typescript
import { toast } from 'react-toastify';

export interface ApiError {
  error: boolean;
  code: string;
  message: string;
  details: Record<string, any>;
  status: number;
}

export class ApiErrorHandler {
  static handle(error: any): ApiError {
    // Проверяем, является ли ошибка нашим стандартным форматом
    if (error.response?.data?.error === true) {
      const apiError: ApiError = error.response.data;
      this.showUserNotification(apiError);
      return apiError;
    }
    
    // Обрабатываем network errors
    if (error.code === 'NETWORK_ERROR' || !error.response) {
      const networkError: ApiError = {
        error: true,
        code: 'NETWORK_ERROR',
        message: 'Проблемы с подключением к интернету',
        details: {},
        status: 0
      };
      this.showUserNotification(networkError);
      return networkError;
    }
    
    // Обрабатываем остальные HTTP ошибки
    const httpError: ApiError = {
      error: true,
      code: `HTTP_${error.response?.status || 'UNKNOWN'}`,
      message: this.getHttpErrorMessage(error.response?.status),
      details: error.response?.data || {},
      status: error.response?.status || 500
    };
    
    this.showUserNotification(httpError);
    return httpError;
  }
  
  private static getHttpErrorMessage(status?: number): string {
    const messages: Record<number, string> = {
      400: 'Некорректные данные в запросе',
      401: 'Необходимо войти в систему',
      403: 'Недостаточно прав для выполнения операции',
      404: 'Запрашиваемый ресурс не найден',
      409: 'Конфликт данных',
      422: 'Ошибка валидации данных',
      429: 'Слишком много запросов, попробуйте позже',
      500: 'Внутренняя ошибка сервера',
      502: 'Ошибка внешнего сервиса',
      503: 'Сервис временно недоступен'
    };
    
    return messages[status || 500] || 'Произошла неизвестная ошибка';
  }
  
  private static showUserNotification(error: ApiError) {
    // Определяем тип уведомления по коду ошибки
    const errorType = this.getNotificationType(error.code);
    
    // Показываем соответствующее уведомление
    switch (errorType) {
      case 'error':
        toast.error(error.message);
        break;
      case 'warning':
        toast.warn(error.message);
        break;
      case 'info':
        toast.info(error.message);
        break;
      default:
        toast.error(error.message);
    }
  }
  
  private static getNotificationType(code: string): 'error' | 'warning' | 'info' {
    const warningCodes = ['INSUFFICIENT_STOCK', 'VALIDATION_ERROR'];
    const infoCodes = ['NETWORK_ERROR'];
    
    if (warningCodes.includes(code)) return 'warning';
    if (infoCodes.includes(code)) return 'info';
    return 'error';
  }
}

// Hook для обработки ошибок в компонентах
export function useApiErrorHandler() {
  return {
    handleError: (error: any) => ApiErrorHandler.handle(error),
    
    // Обертка для async функций с автоматической обработкой ошибок
    withErrorHandling: <T extends any[], R>(
      fn: (...args: T) => Promise<R>
    ) => {
      return async (...args: T): Promise<R | null> => {
        try {
          return await fn(...args);
        } catch (error) {
          ApiErrorHandler.handle(error);
          return null;
        }
      };
    }
  };
}
```

---

## 4. Стратегии восстановления

### 4.1. Retry Policies

**Гибкая система повторных попыток:**
```python
import time
import random
from typing import Callable, Any, Optional
from functools import wraps

class RetryPolicy:
    """
    Политика повторных попыток с различными стратегиями
    """
    
    def __init__(self, 
                 max_attempts: int = 3,
                 base_delay: float = 1.0,
                 max_delay: float = 60.0,
                 backoff_factor: float = 2.0,
                 jitter: bool = True):
        self.max_attempts = max_attempts
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.backoff_factor = backoff_factor
        self.jitter = jitter
    
    def exponential_backoff(self, attempt: int) -> float:
        """
        Экспоненциальная задержка с опциональным jitter
        """
        delay = min(self.base_delay * (self.backoff_factor ** attempt), self.max_delay)
        
        if self.jitter:
            # Добавляем случайность ±25% для предотвращения thundering herd
            jitter_range = delay * 0.25
            delay += random.uniform(-jitter_range, jitter_range)
        
        return max(0, delay)
    
    def should_retry(self, exception: Exception, attempt: int) -> bool:
        """
        Определение необходимости повторной попытки
        """
        if attempt >= self.max_attempts:
            return False
        
        # Список исключений, при которых стоит повторить попытку
        retryable_exceptions = (
            ConnectionError,
            TimeoutError,
            OneCConnectionException,
            OneCTimeoutException,
            requests.exceptions.ConnectionError,
            requests.exceptions.Timeout
        )
        
        # Не повторяем попытки для бизнес-ошибок
        non_retryable_exceptions = (
            OneCAuthenticationException,
            OneCDataFormatException,
            ValidationException,
            BusinessLogicException
        )
        
        if isinstance(exception, non_retryable_exceptions):
            return False
        
        return isinstance(exception, retryable_exceptions)

def retry(policy: Optional[RetryPolicy] = None):
    """
    Декоратор для автоматических повторных попыток
    """
    if policy is None:
        policy = RetryPolicy()
    
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            last_exception = None
            
            for attempt in range(policy.max_attempts):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    
                    if not policy.should_retry(e, attempt):
                        logger.warning(f"Not retrying {func.__name__} after {attempt + 1} attempts: {e}")
                        raise
                    
                    if attempt < policy.max_attempts - 1:  # Не ждем после последней попытки
                        delay = policy.exponential_backoff(attempt)
                        logger.info(f"Retrying {func.__name__} in {delay:.2f}s (attempt {attempt + 1}/{policy.max_attempts})")
                        time.sleep(delay)
            
            # Если все попытки исчерпаны
            logger.error(f"All retry attempts failed for {func.__name__}")
            raise last_exception
        
        return wrapper
    return decorator

# Применение политики повторов к интеграции с 1С
@retry(RetryPolicy(max_attempts=3, base_delay=2.0, max_delay=30.0))
def sync_with_onec(operation: str, data: dict) -> dict:
    """
    Синхронизация с 1С с автоматическими повторными попытками
    """
    try:
        response = onec_api_client.call(operation, data)
        return response
    except OneCConnectionException:
        logger.warning("1C connection failed, will retry")
        raise
    except OneCAuthenticationException:
        logger.error("1C authentication failed, will not retry")
        raise  # Не повторяем попытки для ошибок аутентификации
```

### 4.2. Circuit Breaker Implementation

**Улучшенный Circuit Breaker для 1С:**
```python
from enum import Enum
from datetime import datetime, timedelta
from threading import Lock
import time

class CircuitState(Enum):
    CLOSED = "closed"      # Нормальная работа
    OPEN = "open"          # Блокировка запросов
    HALF_OPEN = "half_open"  # Тестирование восстановления

class OneCCircuitBreaker:
    """
    Circuit Breaker для защиты от отказов 1С
    """
    
    def __init__(self,
                 failure_threshold: int = 5,
                 recovery_timeout: int = 60,
                 success_threshold: int = 3,
                 timeout: int = 30):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.success_threshold = success_threshold
        self.timeout = timeout
        
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time = None
        self.state = CircuitState.CLOSED
        self._lock = Lock()
    
    def call(self, func: Callable, *args, **kwargs) -> Any:
        """
        Выполнение функции через Circuit Breaker
        """
        with self._lock:
            if self.state == CircuitState.OPEN:
                if self._should_attempt_reset():
                    self.state = CircuitState.HALF_OPEN
                    logger.info("Circuit breaker transitioning to HALF_OPEN")
                else:
                    raise OneCConnectionException(
                        "Circuit breaker is OPEN - 1C service unavailable"
                    )
            
            try:
                # Выполняем функцию с таймаутом
                result = self._execute_with_timeout(func, args, kwargs)
                self._on_success()
                return result
                
            except Exception as e:
                self._on_failure(e)
                raise
    
    def _execute_with_timeout(self, func: Callable, args: tuple, kwargs: dict) -> Any:
        """
        Выполнение функции с таймаутом
        """
        import signal
        
        def timeout_handler(signum, frame):
            raise OneCTimeoutException(f"Operation timed out after {self.timeout}s")
        
        # Устанавливаем обработчик таймаута
        old_handler = signal.signal(signal.SIGALRM, timeout_handler)
        signal.alarm(self.timeout)
        
        try:
            return func(*args, **kwargs)
        finally:
            signal.alarm(0)  # Отменяем таймаут
            signal.signal(signal.SIGALRM, old_handler)  # Восстанавливаем обработчик
    
    def _should_attempt_reset(self) -> bool:
        """
        Проверка возможности перехода в HALF_OPEN
        """
        if self.last_failure_time is None:
            return False
        
        return (datetime.now() - self.last_failure_time).seconds >= self.recovery_timeout
    
    def _on_success(self):
        """
        Обработка успешного выполнения
        """
        self.failure_count = 0
        
        if self.state == CircuitState.HALF_OPEN:
            self.success_count += 1
            if self.success_count >= self.success_threshold:
                self.state = CircuitState.CLOSED
                self.success_count = 0
                logger.info("Circuit breaker reset to CLOSED")
    
    def _on_failure(self, exception: Exception):
        """
        Обработка неудачного выполнения
        """
        self.failure_count += 1
        self.last_failure_time = datetime.now()
        
        if self.state == CircuitState.HALF_OPEN:
            self.state = CircuitState.OPEN
            logger.warning("Circuit breaker returned to OPEN after failure in HALF_OPEN")
        elif self.failure_count >= self.failure_threshold:
            self.state = CircuitState.OPEN
            logger.error(f"Circuit breaker opened after {self.failure_count} failures")
        
        # Сохраняем статистику
        CircuitBreakerLog.objects.create(
            service_name='onec_integration',
            state=self.state.value,
            failure_count=self.failure_count,
            exception_type=type(exception).__name__,
            exception_message=str(exception)
        )

class CircuitBreakerLog(models.Model):
    """
    Лог состояний Circuit Breaker
    """
    service_name = models.CharField(max_length=50)
    state = models.CharField(max_length=20)
    failure_count = models.IntegerField()
    exception_type = models.CharField(max_length=100, blank=True)
    exception_message = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['service_name', 'state', 'created_at']),
        ]
```

---

## 5. Мониторинг и алертинг ошибок

### 5.1. Система агрегации ошибок

**Интеллектуальная группировка ошибок:**
```python
import hashlib
from collections import defaultdict

class ErrorAggregator:
    """
    Агрегация и анализ ошибок для выявления паттернов
    """
    
    def __init__(self):
        self.error_stats = defaultdict(lambda: defaultdict(int))
        self.alert_thresholds = {
            'error_rate': 0.05,      # 5% от общего числа запросов
            'unique_errors': 10,      # 10 уникальных ошибок за период
            'critical_errors': 1      # Критические ошибки
        }
    
    def log_error(self, error: Exception, context: dict):
        """
        Логирование и анализ ошибки
        """
        error_hash = self._generate_error_hash(error, context)
        
        # Создаем запись об ошибке
        error_record = ErrorRecord.objects.create(
            error_hash=error_hash,
            error_type=type(error).__name__,
            error_message=str(error),
            error_context=context,
            stack_trace=traceback.format_exc(),
            severity=self._determine_severity(error),
            is_resolved=False
        )
        
        # Обновляем статистику
        self._update_error_stats(error_hash, error_record)
        
        # Проверяем необходимость алерта
        self._check_alert_conditions(error_record)
        
        return error_record
    
    def _generate_error_hash(self, error: Exception, context: dict) -> str:
        """
        Генерация хеша для группировки похожих ошибок
        """
        # Компоненты для хеширования
        error_signature = {
            'type': type(error).__name__,
            'message': str(error)[:100],  # Первые 100 символов
            'view': context.get('view', 'unknown'),
            'method': context.get('method', 'unknown')
        }
        
        signature_string = '|'.join(str(v) for v in error_signature.values())
        return hashlib.md5(signature_string.encode()).hexdigest()[:16]
    
    def _determine_severity(self, error: Exception) -> str:
        """
        Определение уровня критичности ошибки
        """
        critical_exceptions = (
            OneCAuthenticationException,
            PaymentException,
            IntegrationException
        )
        
        warning_exceptions = (
            ValidationException,
            BusinessLogicException,
            InsufficientStockException
        )
        
        if isinstance(error, critical_exceptions):
            return 'critical'
        elif isinstance(error, warning_exceptions):
            return 'warning'
        else:
            return 'error'
    
    def _check_alert_conditions(self, error_record: ErrorRecord):
        """
        Проверка условий для отправки алертов
        """
        # Алерт для критических ошибок
        if error_record.severity == 'critical':
            self._send_critical_error_alert(error_record)
        
        # Алерт для высокой частоты ошибок
        recent_errors = ErrorRecord.objects.filter(
            error_hash=error_record.error_hash,
            created_at__gte=datetime.now() - timedelta(minutes=15)
        ).count()
        
        if recent_errors >= 5:  # 5 одинаковых ошибок за 15 минут
            self._send_high_frequency_alert(error_record, recent_errors)
    
    def get_error_dashboard_data(self) -> dict:
        """
        Данные для dashboard мониторинга ошибок
        """
        last_24h = datetime.now() - timedelta(hours=24)
        
        return {
            'total_errors': ErrorRecord.objects.filter(
                created_at__gte=last_24h
            ).count(),
            
            'unique_errors': ErrorRecord.objects.filter(
                created_at__gte=last_24h
            ).values('error_hash').distinct().count(),
            
            'critical_errors': ErrorRecord.objects.filter(
                created_at__gte=last_24h,
                severity='critical'
            ).count(),
            
            'top_errors': self._get_top_errors(last_24h),
            'error_trends': self._get_error_trends(),
            'resolution_stats': self._get_resolution_stats()
        }
    
    def _get_top_errors(self, since: datetime) -> list:
        """
        Топ ошибок за период
        """
        from django.db.models import Count
        
        return list(
            ErrorRecord.objects.filter(created_at__gte=since)
            .values('error_hash', 'error_type', 'error_message')
            .annotate(count=Count('id'))
            .order_by('-count')[:10]
        )

class ErrorRecord(models.Model):
    """
    Запись об ошибке в системе
    """
    error_hash = models.CharField(max_length=16, db_index=True)
    error_type = models.CharField(max_length=100)
    error_message = models.TextField()
    error_context = models.JSONField(default=dict)
    stack_trace = models.TextField()
    
    severity = models.CharField(max_length=20, choices=[
        ('info', 'Информационная'),
        ('warning', 'Предупреждение'),
        ('error', 'Ошибка'),
        ('critical', 'Критическая')
    ])
    
    is_resolved = models.BooleanField(default=False)
    resolved_at = models.DateTimeField(null=True, blank=True)
    resolution_notes = models.TextField(blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['error_hash', 'created_at']),
            models.Index(fields=['severity', 'is_resolved', 'created_at']),
            models.Index(fields=['created_at']),
        ]
```

---

Обновленная стратегия обработки ошибок обеспечивает:

1. **Комплексную архитектуру исключений** с детализированной классификацией
2. **Специализированную обработку ошибок 1С интеграции** с fallback стратегиями
3. **Robust Frontend error handling** с React Error Boundaries
4. **Интеллектуальные стратегии восстановления** включая retry policies и circuit breaker
5. **Продвинутый мониторинг ошибок** с агрегацией и алертингом