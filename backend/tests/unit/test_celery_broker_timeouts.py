"""
CAP-2: недоступный или зависший брокер не держит запрос оформления заказа.

Берём настройки Celery проекта (`CELERY_*` из `settings/base.py`), направляем
брокер и бэкенд результатов на локальный сокет, который принимает соединения и
молчит, и проверяем, что `.delay` заканчивается исключением быстрее таймаута
gunicorn. Без настроек проекта такой вызов висит больше 170 с.
"""

import socket
import threading
import time

import pytest
from celery import Celery
from kombu.exceptions import OperationalError


@pytest.fixture
def silent_redis_port():
    """Сокет, который принимает соединения и ничего не отвечает."""
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind(("127.0.0.1", 0))
    server.listen(16)
    server.settimeout(0.2)
    connections = []
    stop = threading.Event()

    def accept_loop():
        while not stop.is_set():
            try:
                connections.append(server.accept()[0])
            except OSError:
                continue

    thread = threading.Thread(target=accept_loop, daemon=True)
    thread.start()
    yield server.getsockname()[1]
    stop.set()
    thread.join(timeout=2)
    for connection in connections:
        connection.close()
    server.close()


@pytest.mark.unit
def test_delay_fails_fast_when_broker_accepts_connection_and_stays_silent(silent_redis_port, monkeypatch):
    # set_as_current=False: приложение теста не должно стать текущим для остальных тестов
    app = Celery("broker_timeouts_test", set_as_current=False)
    app.config_from_object("django.conf:settings", namespace="CELERY")
    url = f"redis://127.0.0.1:{silent_redis_port}/0"
    # Адрес брокера Celery сначала берёт из окружения (в контейнере оно задано),
    # поэтому подменяем переменные, а не только конфиг.
    monkeypatch.setenv("CELERY_BROKER_URL", url)
    monkeypatch.setenv("CELERY_RESULT_BACKEND", url)
    assert app.conf.broker_url == url
    assert app.conf.result_backend == url
    # Таймауты и повторы — из настроек проекта, а не значения Celery по умолчанию
    assert app.conf.redis_socket_timeout == 3
    assert app.conf.task_publish_retry_policy["max_retries"] == 1

    @app.task(name="broker_timeouts_test.noop")
    def noop():
        return None

    started = time.monotonic()
    with pytest.raises(OperationalError):
        noop.delay()
    elapsed = time.monotonic() - started

    assert elapsed < 15, f".delay завис на {elapsed:.1f} с"
