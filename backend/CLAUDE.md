# Backend — CLAUDE.md

## Изоляция тестов (специфика проекта)

Решены проблемы с constraint violations через:

- **Автоочистка БД:** `@pytest.fixture(autouse=True)` с `TRUNCATE CASCADE` перед каждым тестом.
- **Уникальные данные:** `get_unique_suffix()` (timestamp + счетчик + UUID).
- **Factory Boy:** `LazyFunction` вместо статических значений и `Sequence`.
- **Pytest:** `--create-db --nomigrations` для быстрой изоляции.

Детальные правила: `backend/docs/testing-standards.md` (раздел 8.5).
