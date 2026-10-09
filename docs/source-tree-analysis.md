# Анализ структуры исходного кода (Source Tree Analysis)

Этот документ содержит аннотированную структуру проекта FREESPORT, выделяя ключевые компоненты, точки входа и логику взаимодействия между частями.

## 📂 Общая структура (Monorepo)

```text
freesport/
├── backend/                # Django REST Framework API (Бэкенд)
├── frontend/               # Next.js 15.5 application (Фронтенд)
├── docker/                 # Конфигурации контейнеризации
├── docs/                   # Техническая документация (BMAD V6)
├── scripts/                # Скрипты автоматизации и развертывания
├── data/                   # Статические данные и файлы импорта
└── docker-compose.yml      # Оркестрация сервисов
```

---

## 🐍 Backend Architecture (`backend/`)

Бэкенд построен на **Django 5.2.7** и **Django REST Framework 3.14**. Используется модульная структура приложений.

### 🏛️ Основные приложения (`backend/apps/`)

| Приложение       | Описание                                             | Ключевые файлы                                   |
| :--------------- | :--------------------------------------------------- | :----------------------------------------------- |
| **users**        | Ролевая система (7 ролей), B2B верификация, профили. | `models.py` (User, Company, Address)             |
| **products**     | Каталог товаров, бренды, категории, ролевые цены.    | `models.py` (Product, ProductVariant, Attribute) |
| **cart**         | Управление корзиной (гости + авторизованные).        | `models.py` (Cart, CartItem)                     |
| **orders**       | Система заказов, транзакционная логика, история.     | `models.py` (Order, OrderItem), `serializers.py` |
| **integrations** | Обмен данными с 1С (CommerceML), Celery задачи.      | `tasks.py` (import logic), `models.py` (Session) |
| **banners**      | Управление Hero-секцией с таргетингом.               | `models.py` (Banner)                             |
| **common**       | Общие утилиты, новости, блог, подписки.              | `utils/`, `models.py` (News, BlogPost)           |

### ⚙️ Инфраструктура Бэкенда

- **`backend/freesport/`**: Настройки проекта Django.
- **`backend/tests/`**: Тестовое покрытие (Pytest).
- **`backend/manage.py`**: Точка входа CLI.

---

## ⚛️ Frontend Architecture (`frontend/`)

Фронтенд реализован на **Next.js 15.5** с использованием **App Router** и **TypeScript**.

### 🧩 Структура исходного кода (`frontend/src/`)

- **`app/`**: Маршрутизация и страницы (Next.js App Router).
  - `(blue)/`: Основная тема (Синяя).
  - `(electric)/`: Альтернативная тема (Electric Orange).
- **`components/`**: Библиотека UI-компонентов.
  - `ui/`: Атомарные и составные компоненты (Card, Button, ProductCard).
  - `layout/`: Компоненты разметки (Header, Footer).
- **`services/`**: Слой взаимодействия с API (Axios).
  - `api-client.ts`: Конфигурация клиента с поддержкой SSR и Refresh Token.
- **`stores/`**: Глобальное состояние (Zustand).
  - `authStore.ts`, `cartStore.ts` (с Optimistic Updates).
- **`hooks/`**: Кастомные React хуки.
- **`types/`**: TypeScript интерфейсы (включая автогенерируемые из OpenAPI).

---

## 🔄 Взаимодействие и интеграции

1.  **Frontend <-> Backend**: REST API запросы. В режиме разработки (Docker) фронтенд обращается к бэкенду по внутреннему адресу `http://backend:8000`, в браузере — через Nginx прокси.
2.  **Backend <-> 1C**: Асинхронный импорт XML-файлов через Celery. Точка входа — `backend/apps/integrations/tasks.py`.
3.  **Хранение изображений**: Гибридная система. Изображения из 1С копируются в `backend/media/products/` и обслуживаются через Nginx.

---

## 🚀 Точки входа и конфигурация

- **Backend API**: `backend/manage.py runserver` (порт 8001 локально).
- **Frontend Dev**: `npm run dev` (порт 3000 локально).
- **Docker Dev**: `docker compose -f docker/docker-compose.yml up`.
- **Конфигурация**: `.env` файлы в корне и подпапках.
