# FREESPORT Knowledge Base (BMAD V6)

Добро пожаловать в базу знаний проекта FREESPORT. Эта документация была актуализирована в ходе **Exhaustive Scan** и соответствует текущему состоянию кодовой базы.

## 🚀 Быстрый старт (Quick Reference)

- **[Обзор проекта](./project-overview.md)** — цели, архитектура и ключевые возможности.
- **[Анализ структуры кода](./source-tree-analysis.md)** — где что лежит и как устроено.
- **[Руководство по разработке](./development-guide.md)** — запуск, команды, тестирование.

## 🏗️ Архитектура и Технологии

- **[Архитектура Бэкенда](./architecture-backend.md)** — Django, DRF и бизнес-логика.
- **[Архитектура Фронтенда](./architecture-frontend.md)** — Next.js, App Router и состояние.
- **[Модели данных](./data-models.md)** — таблицы, связи, `customer_code` и каноническая нумерация заказов.
- **[Архитектурные решения](./decisions/README.md)** — ADR по устойчивым архитектурным контрактам, включая публичную проекцию дерева категорий 1С.
- **[Контракты API](./api-contracts.md)** — описание REST эндпоинтов, включая актуальный contract `/orders/`.

## 📦 Интеграции и Модули

- **[Интеграция с 1С](./integrations/1c/architecture.md)** — CommerceML, sub-orders и канонические номера заказов.
- **[Руководство по командам импорта](./integrations/1c/commands-guide.md)** — `import_products_from_1c`, `import_customers_from_1c`, примеры использования.
- **[VAT-split и складской routing заказов для 1С](./integrations/1c/order-vat-warehouse-routing.md)** — НДС, склады, master/sub-orders и экспорт CommerceML.
- **[Анализ порядка статусов заказов](./integrations/1c/analysis-orders-xml.md)** — маппинг статусов между 1С и платформой.
- **[Инвентаризация UI компонентов](./component-inventory-frontend.md)** — библиотека визуальных элементов.
- **[Система развертывания](./deploy/README.md)** — Docker, Nginx и скрипты деплоя.

---

## 📈 Прогресс проекта

Актуальный статус спринта находится в **[_bmad-output/implementation-artifacts/sprint-status.yaml](../_bmad-output/implementation-artifacts/sprint-status.yaml)** и **[_bmad-output/implementation-artifacts/sprint-completion-report-2026-05-18.md](../_bmad-output/implementation-artifacts/sprint-completion-report-2026-05-18.md)**.

---

_Документация обновлена: 07.05.2026. Агент: Codex_
