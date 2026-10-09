# Мультистадийная сборка для Django backend
# Стадия 1: Сборка зависимостей
FROM python:3.12-slim AS builder

# Установка системных зависимостей для сборки
RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Создание виртуального окружения
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Копирование файла зависимостей
COPY requirements.txt .

# Установка Python зависимостей в виртуальном окружении
RUN pip install --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# Стадия 2: Production образ
FROM python:3.12-slim AS production

# Метаданные образа
LABEL maintainer="FREESPORT Dev Team"
LABEL version="1.0"
LABEL description="Django backend для FREESPORT Platform"

# Аргумент для настроек Django
ARG DJANGO_SETTINGS_MODULE=freesport.settings.production

# Создание пользователя приложения (не root)
RUN groupadd -r freesport && useradd -r -g freesport freesport

# Установка runtime зависимостей
RUN apt-get update && apt-get install -y \
    libpq5 \
    gettext \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Копирование виртуального окружения из builder стадии
COPY --from=builder /opt/venv /opt/venv

# Установка переменных окружения
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PATH="/opt/venv/bin:$PATH"
ENV DJANGO_SETTINGS_MODULE=${DJANGO_SETTINGS_MODULE}

# Создание рабочей директории
WORKDIR /app

# Копирование исходного кода
COPY --chown=freesport:freesport . .

# Создание директорий для статических файлов и медиа
RUN mkdir -p /app/staticfiles /app/media \
    && chown -R freesport:freesport /app

# Установка pg_dump для резервного копирования
RUN apt-get update && \
    apt-get install -y --no-install-recommends postgresql-client && \
    rm -rf /var/lib/apt/lists/*

# Переключение на пользователя приложения
USER freesport

# Открытие порта для Django
EXPOSE 8000

# Проверка работоспособности
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD python manage.py check --deploy || exit 1

# Запуск приложения через Gunicorn
# timeout=300 (5 минут) для длительных операций импорта
# graceful-timeout=300 для корректного завершения worker'ов
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--workers", "4", "--worker-class", "sync", "--timeout", "300", "--graceful-timeout", "300", "--max-requests", "1000", "--max-requests-jitter", "100", "--preload", "--access-logfile", "-", "--error-logfile", "-", "freesport.wsgi:application"]
