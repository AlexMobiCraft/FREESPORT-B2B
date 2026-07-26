# Стандарты тестирования Backend (FREESPORT)

## Сценарии тестирования: Master / Suborder flow

### Order Numbering

| Сценарий | Ожидаемый результат | Тип теста |
|----------|---------------------|-----------|
| Генерация master-номера при валидном `customer_code` | Канонический номер `CCCCCYYNNN` создан, счётчик инкрементирован | Unit |
| Отсутствие `customer_code` у пользователя | `OrderNumberError` → `ValidationError` (400) | Integration |
| Переполнение sequence (999 → 1000) | `OrderNumberSequenceExhausted` → 400, rollback | Unit |
| Форматирование master / suborder | UI-формат `CCCC-YYNNN` и `CCCCC-YYNNN-S` | Unit |
| Нормализация поиска | UI-ввод `4620-26007` → канонический `0462026007` | Unit |

### Email и Notifications

| Сценарий | Ожидаемый результат | Тип теста |
|----------|---------------------|-----------|
| Checkout с 2 suborders | Ровно 1 customer email + 1 admin email (master only) | Integration |
| Items в customer email | Все items из обоих suborders агрегированы через helper | Unit |
| Suborder save | Не ставит email задачи в очередь | Unit |

### Permissions

| Сценарий | Ожидаемый результат | Тип теста |
|----------|---------------------|-----------|
| Anonymous `POST /api/orders/` | **401 Unauthorized** | Integration |

### Admin

| Сценарий | Ожидаемый результат | Тип теста |
|----------|---------------------|-----------|
| `items_count` для master с suborders | Сумма позиций из всех suborders | Unit |
| `total_items_quantity` для master | Сумма количеств из всех suborders | Unit |
| N+1 prevention | `prefetch_related("sub_orders__items")` используется | Unit |
