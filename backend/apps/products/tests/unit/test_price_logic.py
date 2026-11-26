import importlib
from decimal import Decimal

import pytest
from django.apps import apps as django_apps
from django.contrib.auth import get_user_model
from django.db import IntegrityError, connection, transaction
from django.db.migrations.executor import MigrationExecutor

from apps.products.models import Brand, Category, ImportSession, PriceType, Product, ProductVariant
from apps.products.services.parser import XMLDataParser
from apps.products.services.variant_import import VariantImportProcessor

User = get_user_model()


@pytest.fixture
def product():
    brand = Brand.objects.create(name="TestBrand", slug="test-brand")
    category = Category.objects.create(name="TestCat", slug="test-cat")
    return Product.objects.create(
        name="Test Product",
        slug="test-product",
        brand=brand,
        category=category,
        onec_id="prod1",
    )


@pytest.fixture
def variant(product):
    return ProductVariant.objects.create(
        product=product,
        sku="SKU-1",
        onec_id="var1",
        retail_price=Decimal("100.00"),
        stock_quantity=10,
    )


@pytest.fixture
def import_session():
    return ImportSession.objects.create(import_type="prices")


@pytest.fixture
def processor(import_session):
    return VariantImportProcessor(session_id=import_session.id)


@pytest.mark.django_db
class TestPriceImportLogic:
    def test_unmapped_rrp_price_type_is_remapped_to_retail(self, processor, variant):
        """
        Состояние после миграции 0061: вид цен «РРЦ» без маппинга. Следующая загрузка
        priceLists прогоняет название через маппер, вид уходит в retail_price,
        и цена предложения этого вида пишется в розницу.
        """
        onec_name = "РРЦ рекомендованная"
        price_type = PriceType.objects.create(onec_id="price-rrp-id", onec_name=onec_name, product_field="")

        processor.process_price_types(
            [
                {
                    "onec_id": "price-rrp-id",
                    "onec_name": onec_name,
                    "product_field": XMLDataParser()._map_price_type_to_field(onec_name),
                    "is_deleted": False,
                }
            ]
        )
        price_type.refresh_from_db()
        assert price_type.product_field == "retail_price"

        processor.update_variant_prices(
            {"id": variant.onec_id, "prices": [{"price_type_id": "price-rrp-id", "value": Decimal("2530.00")}]}
        )

        variant.refresh_from_db()
        assert variant.retail_price == Decimal("2530.00")

    def test_msrp_import(self, processor, variant):
        """Test AC3: msrp is imported correctly"""

        PriceType.objects.create(onec_id="price-msrp-id", onec_name="МРЦ", product_field="msrp")

        price_data = {
            "id": variant.onec_id,
            "prices": [{"price_type_id": "price-msrp-id", "value": Decimal("200.00")}],
        }

        processor.update_variant_prices(price_data)

        variant.refresh_from_db()
        assert variant.msrp == Decimal("200.00")


@pytest.mark.django_db
class TestPriceFallbackLogic:
    def test_federation_rep_fallback(self, variant):
        """Test AC4: federation_rep sees retail_price if federation_price is missing"""

        # Setup user
        user = User.objects.create_user(
            email="fed@example.com", password="password", role="federation_rep", is_verified=True
        )

        # Case 1: No federation price
        variant.retail_price = Decimal("100.00")
        variant.federation_price = None
        variant.save()

        price = variant.get_price_for_user(user)
        assert price == Decimal("100.00")

        # Case 2: Federation price exists
        variant.federation_price = Decimal("80.00")
        variant.save()

        price = variant.get_price_for_user(user)
        assert price == Decimal("80.00")

    def test_unregistered_1c_contragent_sees_retail_price(self, variant):
        """
        Контрагент 1С без портального аккаунта получает розничную цену.

        Роль unregistered отсутствует в role_price_mapping, поэтому цена
        берётся из fallback — оптовые цены такому пользователю недоступны.
        """
        # Импорт 1С создаёт запись без пароля — воспроизводим её форму,
        # а не аккаунт с паролем, которого у контрагента быть не может
        user = User.objects.create(
            email="unregistered@example.com",
            role="unregistered",
            created_in_1c=True,
            verification_status="unverified",
        )
        variant.retail_price = Decimal("100.00")
        variant.opt1_price = Decimal("60.00")
        variant.trainer_price = Decimal("70.00")
        variant.save()

        assert variant.get_price_for_user(user) == Decimal("100.00")
        assert user.is_b2b_user is False

    def test_promo_price_below_role_price_overrides_it_and_keeps_regular(self, variant):
        """Акция ниже цены роли — платит акцию; цена по роли без акции остаётся доступной."""
        user = User.objects.create_user(
            email="fed-promo@example.com", password="password", role="federation_rep", is_verified=True
        )
        variant.federation_price = Decimal("80.00")
        variant.promo_price = Decimal("70.00")
        variant.save()

        assert variant.get_price_for_user(user) == Decimal("70.00")
        assert variant.get_regular_price_for_user(user) == Decimal("80.00")
        assert variant.get_price_for_user(None) == Decimal("70.00")
        assert variant.get_regular_price_for_user(None) == Decimal("100.00")

    def test_promo_price_above_role_price_does_not_raise_the_price(self, variant):
        """Акция выше цены роли клиенту не выгодна: он платит свою цену, розница платит акцию."""
        user = User.objects.create_user(
            email="fed-promo-high@example.com", password="password", role="federation_rep", is_verified=True
        )
        variant.federation_price = Decimal("80.00")
        variant.promo_price = Decimal("90.00")
        variant.save()

        assert variant.get_price_for_user(user) == Decimal("80.00")
        assert variant.get_price_for_user(None) == Decimal("90.00")

    def test_zero_promo_price_is_ignored(self, variant):
        variant.promo_price = Decimal("0")
        variant.save()

        assert variant.get_price_for_user(None) == Decimal("100.00")


# Вид цен «Опт 4» — реквизиты из справочника 1С (см. story 39.1)
OPT4_ONEC_ID = "4c1962d2-f8ed-11eb-81f3-00155d3cae02"
OPT4_ONEC_NAME = "Опт 4 (до 50 тыс.руб в квартал)"


@pytest.mark.unit
@pytest.mark.django_db
class TestOpt4PriceForUser:
    """Цена четвёртого оптового уровня в get_price_for_user (AC7, AC8)."""

    def test_wholesale_level4_gets_opt4_price(self, variant):
        """Роль wholesale_level4 с заполненной opt4_price получает её."""
        user = User.objects.create_user(
            email="opt4-filled@example.com",
            password="password",
            role="wholesale_level4",
            is_verified=True,
        )
        variant.retail_price = Decimal("100.00")
        variant.opt4_price = Decimal("85.00")
        variant.save()

        assert variant.get_price_for_user(user) == Decimal("85.00")

    def test_wholesale_level4_falls_back_to_retail(self, variant):
        """Пустая opt4_price → откат сразу на retail_price, без каскада opt3→opt2→opt1."""
        user = User.objects.create_user(
            email="opt4-empty@example.com",
            password="password",
            role="wholesale_level4",
            is_verified=True,
        )
        variant.retail_price = Decimal("100.00")
        variant.opt4_price = None
        # Заполненные цены соседних уровней не должны участвовать в fallback
        variant.opt1_price = Decimal("60.00")
        variant.opt3_price = Decimal("70.00")
        variant.save()

        assert variant.get_price_for_user(user) == Decimal("100.00")


@pytest.mark.unit
@pytest.mark.django_db
class TestOpt4PriceConstraint:
    """CheckConstraint products_opt4_price_positive на ProductVariant (AC2)."""

    def test_negative_opt4_price_rejected_by_db(self, product):
        """Отрицательная opt4_price отклоняется на уровне БД."""
        with pytest.raises(IntegrityError):
            with transaction.atomic():
                ProductVariant.objects.create(
                    product=product,
                    sku="SKU-OPT4-NEG",
                    onec_id="var-opt4-neg",
                    retail_price=Decimal("100.00"),
                    opt4_price=Decimal("-1"),
                    stock_quantity=0,
                )

    def test_null_and_zero_opt4_price_allowed(self, product):
        """NULL и 0 — валидные значения, constraint их пропускает."""
        with transaction.atomic():
            null_variant = ProductVariant.objects.create(
                product=product,
                sku="SKU-OPT4-NULL",
                onec_id="var-opt4-null",
                retail_price=Decimal("100.00"),
                opt4_price=None,
                stock_quantity=0,
            )
            zero_variant = ProductVariant.objects.create(
                product=product,
                sku="SKU-OPT4-ZERO",
                onec_id="var-opt4-zero",
                retail_price=Decimal("100.00"),
                opt4_price=Decimal("0"),
                stock_quantity=0,
            )

        assert null_variant.opt4_price is None
        assert zero_variant.opt4_price == Decimal("0")


@pytest.mark.unit
@pytest.mark.django_db
class TestDealerPriceField:
    """Поле `dealer_price` (spec-role-dealer-price): CHECK ≥ 0 и choice вида цен."""

    def test_negative_dealer_price_rejected_by_db(self, product):
        with pytest.raises(IntegrityError):
            with transaction.atomic():
                ProductVariant.objects.create(
                    product=product,
                    sku="SKU-DEALER-NEG",
                    onec_id="var-dealer-neg",
                    retail_price=Decimal("100.00"),
                    dealer_price=Decimal("-1"),
                    stock_quantity=0,
                )

    def test_dealer_price_choice_present(self):
        field = PriceType._meta.get_field("product_field")
        assert field.choices is not None
        assert ("dealer_price", "Дилерская цена") in field.choices

    def test_unverified_dealer_pays_retail(self, variant):
        """Матрица I/O: роль `dealer` без верификации платит розницу."""
        user = User.objects.create_user(
            email="dealer-unverified@example.com", password="password", role="dealer", is_verified=False
        )
        variant.retail_price = Decimal("1000.00")
        variant.opt1_price = Decimal("570.00")
        variant.dealer_price = Decimal("520.00")
        # Полное сохранение `dealer_price` не пишет (её ведёт импорт 1С): поля — явно
        variant.save(update_fields=["retail_price", "opt1_price", "dealer_price"])
        variant.refresh_from_db()

        assert variant.get_price_for_user(user) == Decimal("1000.00")


@pytest.mark.unit
@pytest.mark.django_db
class TestRemoveRrpMigration:
    """Миграция 0061_remove_productvariant_rrp: колонки и выбора `rrp` больше нет."""

    migration = importlib.import_module("apps.products.migrations.0061_remove_productvariant_rrp")

    def test_rrp_price_type_loses_mapping(self):
        """Вид цен с маппингом rrp получает пустой маппинг, остальные не трогаются."""
        rrp_type = PriceType.objects.create(onec_id="rrp-pt", onec_name="РРЦ", product_field="rrp")
        msrp_type = PriceType.objects.create(onec_id="msrp-pt", onec_name="МРЦ", product_field="msrp")

        self.migration.unmap_rrp_price_types(django_apps, None)

        rrp_type.refresh_from_db()
        msrp_type.refresh_from_db()
        assert rrp_type.product_field == ""
        assert msrp_type.product_field == "msrp"

    def test_rrp_field_and_choice_removed(self):
        field_names = {field.name for field in ProductVariant._meta.get_fields()}
        assert "rrp" not in field_names
        assert "msrp" in field_names

        choices = dict(PriceType._meta.get_field("product_field").choices or [])
        assert "rrp" not in choices
        assert "msrp" in choices

        with connection.cursor() as cursor:
            columns = {col.name for col in connection.introspection.get_table_description(cursor, "product_variants")}
        assert "rrp" not in columns
        assert "msrp" in columns


BEFORE_RRP_MIGRATION = ("products", "0060_dealer_price")
RRP_MIGRATION = ("products", "0061_remove_productvariant_rrp")


def _migrate_schema_to(*targets: tuple[str, str]):
    """Переводит схему тестовой БД к узлам миграций; отдаёт исторические модели этого состояния."""
    MigrationExecutor(connection).migrate(list(targets))
    return MigrationExecutor(connection).loader.project_state(list(targets)).apps


@pytest.fixture
def catalog_before_rrp_migration(transactional_db):
    """
    Схема на миграции 0060 — с колонкой `rrp`: каталог так, как он лежит на проде перед деплоем.

    Выход возвращает схему к последним миграциям, даже если тест упал: иначе соседние тесты
    воркера пойдут по БД с колонкой `rrp` и старыми выборами `product_field`.
    """
    try:
        yield _migrate_schema_to(BEFORE_RRP_MIGRATION)
    finally:
        executor = MigrationExecutor(connection)
        executor.migrate(list(executor.loader.graph.leaf_nodes()))


@pytest.mark.unit
@pytest.mark.django_db(transaction=True)
class TestMigration0061AppliedToExistingCatalog:
    """
    Переход 0060 → 0061 на заполненной БД настоящим исполнителем миграций.

    `TestRemoveRrpMigration` вызывает data-функцию напрямую и не заметит, что `RunPython`
    пропал из `Migration.operations`: вид цен с маппингом `rrp` остался бы с недопустимым выбором.
    Данные «до» создаются историческими моделями.
    """

    def test_rrp_price_types_unmapped_and_column_dropped(self, catalog_before_rrp_migration):
        historical = catalog_before_rrp_migration
        historical_price_type = historical.get_model("products", "PriceType")
        for onec_id, name, field in (
            ("rrp-pt", "РРЦ", "rrp"),
            ("msrp-pt", "МРЦ", "msrp"),
            ("retail-pt", "Розничная", "retail_price"),
        ):
            historical_price_type.objects.create(onec_id=onec_id, onec_name=name, product_field=field)

        brand = historical.get_model("products", "Brand").objects.create(name="Бренд РРЦ", slug="rrp-migration-brand")
        category = historical.get_model("products", "Category").objects.create(
            name="Категория РРЦ", slug="rrp-migration-category"
        )
        historical_product = historical.get_model("products", "Product").objects.create(
            name="Товар РРЦ",
            slug="rrp-migration-product",
            onec_id="rrp-migration-product",
            brand=brand,
            category=category,
        )
        historical.get_model("products", "ProductVariant").objects.create(
            product=historical_product,
            sku="RRP-MIGRATION-1",
            onec_id="rrp-migration-product#v1",
            retail_price=Decimal("2530.00"),
            msrp=Decimal("2150.00"),
            rrp=Decimal("2105.00"),
            stock_quantity=5,
        )

        _migrate_schema_to(RRP_MIGRATION)

        seeded_ids = ("rrp-pt", "msrp-pt", "retail-pt")
        fields = dict(PriceType.objects.filter(onec_id__in=seeded_ids).values_list("onec_id", "product_field"))
        assert fields == {"rrp-pt": "", "msrp-pt": "msrp", "retail-pt": "retail_price"}

        with connection.cursor() as cursor:
            columns = {col.name for col in connection.introspection.get_table_description(cursor, "product_variants")}
        assert "rrp" not in columns

        variant = ProductVariant.objects.get(onec_id="rrp-migration-product#v1")
        assert variant.retail_price == Decimal("2530.00")
        assert variant.msrp == Decimal("2150.00")


@pytest.mark.unit
class TestPriceTypeOpt4Choice:
    """Choice opt4_price в PriceType.product_field (AC3)."""

    def test_opt4_price_choice_present(self):
        field = PriceType._meta.get_field("product_field")
        assert field.choices is not None
        assert ("opt4_price", "Оптовая цена уровень 4") in field.choices


@pytest.mark.unit
@pytest.mark.django_db
class TestSeedOpt4PriceType:
    """Data-миграция 0053_seed_price_type_opt4 (AC4).

    Функции миграции вызываются напрямую: autouse-фикстура clear_db_before_test
    делает каждый тест транзакционным, поэтому данные, засеянные миграциями,
    из тестовой БД вычищаются — полагаться на них нельзя.
    """

    # Имя модуля начинается с цифры, поэтому только import_module
    migration = importlib.import_module("apps.products.migrations.0053_seed_price_type_opt4")

    def test_seed_creates_price_type(self):
        """forwards заводит запись «Опт 4» со всеми реквизитами."""
        self.migration.seed_opt4_price_type(django_apps, None)

        price_type = PriceType.objects.get(onec_id=OPT4_ONEC_ID)
        assert price_type.onec_name == OPT4_ONEC_NAME
        assert price_type.product_field == "opt4_price"
        assert price_type.user_role == "wholesale_level4"
        assert price_type.is_active is True

    def test_seed_is_idempotent(self):
        """Повторный прогон не создаёт дубля."""
        self.migration.seed_opt4_price_type(django_apps, None)
        self.migration.seed_opt4_price_type(django_apps, None)

        assert PriceType.objects.filter(onec_id=OPT4_ONEC_ID).count() == 1

    def test_reverse_removes_only_opt4(self):
        """backwards удаляет только «Опт 4», остальные виды цен не трогает."""
        PriceType.objects.create(
            onec_id="c05f0e2b-b3f2-11ea-81c3-00155d3cae02",
            onec_name="Опт 3 (50-150 тыс.руб в квартал)",
            product_field="opt3_price",
        )
        PriceType.objects.create(
            onec_id="3d1482c4-bd77-11e4-afc8-20cf3073dde3",
            onec_name="РРЦ",
            product_field="retail_price",
        )
        self.migration.seed_opt4_price_type(django_apps, None)

        self.migration.remove_opt4_price_type(django_apps, None)

        assert not PriceType.objects.filter(onec_id=OPT4_ONEC_ID).exists()
        assert PriceType.objects.count() == 2
