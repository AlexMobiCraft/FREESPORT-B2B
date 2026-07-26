-- Инициализация базы данных FREESPORT
-- Этот скрипт выполняется автоматически при первом запуске PostgreSQL

-- Пароль пользователя postgres задаётся переменной POSTGRES_PASSWORD в docker-compose

-- Создание базы данных (если не создана через POSTGRES_DB)
SELECT 'CREATE DATABASE freesport'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'freesport')\gexec

-- Подключение к базе freesport
\c freesport

-- Установка кодировки по умолчанию
SET client_encoding = 'UTF8';
