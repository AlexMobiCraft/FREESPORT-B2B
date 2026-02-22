# Analysis of `orders.xml` (CommerceML 3.1)

> [!NOTE]
> This document is based on the CommerceML 3.1 standard specification. Real 1C configurations may vary (custom fields, different hierarchy).
> **Status:** Pending real examples from client's 1C.

## File Structure

The standard `orders.xml` (often sent as `documents.xml` or within a ZIP) for CommerceML 3.1 follows a container-based structure:

```xml
<КоммерческаяИнформация ВерсияСхемы="3.1" ДатаФормирования="...">
    <Контейнер>
        <Документ>
            <Ид>ORDER_ID</Ид>
            <Номер>ORDER_NUMBER</Номер>
            <Дата>DATE</Дата>
            <ХозОперация>Заказ товара</ХозОперация>
            <Роль>Продавец</Роль>
            <Валюта>руб</Валюта>
            <Курс>1</Курс>
            <Сумма>TOTAL_AMOUNT</Сумма>
            <Контрагенты>
                <Контрагент>
                    <Ид>USER_ID</Ид>
                    <Роль>Покупатель</Роль>
                    <Наименование>User Name</Наименование>
                </Контрагент>
            </Контрагенты>
            <Товары>
                <Товар>
                    <Ид>PRODUCT_ID</Ид>
                    <Наименование>Product Name</Наименование>
                    <БазоваяЕдиница ...>шт</БазоваяЕдиница>
                    <ЦенаЗаЕдиницу>PRICE</ЦенаЗаЕдиницу>
                    <Количество>QTY</Количество>
                    <Сумма>TOTAL</Сумма>
                    <ЗначенияРеквизитов>
                         <ЗначениеРеквизита>
                            <Наименование>ВидНоменклатуры</Наименование>
                            <Значение>Товар</Значение>
                        </ЗначениеРеквизита>
                        <ЗначениеРеквизита>
                            <Наименование>ТипНоменклатуры</Наименование>
                            <Значение>Товар</Значение>
                        </ЗначениеРеквизита>
                    </ЗначенияРеквизитов>
                </Товар>
            </Товары>
            <ЗначенияРеквизитов>
                <ЗначениеРеквизита>
                    <Наименование>Статус заказа</Наименование>
                    <Значение>Reserved</Значение> <!-- This is what we need to map -->
                </ЗначениеРеквизита>
                <ЗначениеРеквизита>
                    <Наименование>Отменено</Наименование>
                    <Значение>false</Значение>
                </ЗначениеРеквизита>
            </ЗначенияРеквизитов>
        </Документ>
    </Контейнер>
</КоммерческаяИнформация>
```

## Key Elements for Mapping (Story 5.1/5.2)

For **Importing Statuses** (1C -> Site), we rely on:

1.  **Identification**: `<Номер>` or `<Ид>` to match the Order on our side.
2.  **Status**: Look for `<ЗначениеРеквизита>` with `Наименование="Статус заказа"` (or similar, depends on 1C config).
3.  **Payment/Shipment Dates**: Look for separate documents in the container or requsites like "Дата оплаты", "Дата отгрузки".

## Next Steps

1.  Obtain a real `orders.xml` export from the specific 1C instance to verify:
    *   Exact name of the status field.
    *   How dates are passed.
    *   If `<Контейнер>` is strictly used (it is in 3.1, but sometimes strictness varies).
