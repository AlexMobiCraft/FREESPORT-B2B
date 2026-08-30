"""
Unit тесты для Django Admin интерфейса товаров

Story 13.2: Проверка отображения onec_brand_id в Django Admin
"""

import pytest
from django.contrib import messages
from django.contrib.admin.sites import AdminSite
from django.test import RequestFactory, TestCase

from apps.products.admin import Brand1CMappingAdmin, Brand1CMappingInline, BrandAdmin, PriceTypeAdmin, ProductAdmin
from apps.products.forms import PriceTypeAdminForm
from apps.products.models import Brand, Brand1CMapping, PriceType, Product
from tests.factories import Brand1CMappingFactory, BrandFactory, CategoryFactory, ProductFactory, UserFactory


@pytest.mark.django_db
class TestProductAdmin(TestCase):
    """Тесты для ProductAdmin"""

    def setUp(self):
        """Настройка тестового окружения"""
        self.site = AdminSite()
        self.admin = ProductAdmin(Product, self.site)
        self.factory = RequestFactory()
        self.superuser = UserFactory.create(is_staff=True, is_superuser=True, email="admin@test.com")

    def test_onec_brand_id_in_readonly_fields(self):
        """
        AC3: Проверка что onec_brand_id находится в readonly_fields

        Given: ProductAdmin настроен
        When: Проверяем readonly_fields
        Then: onec_brand_id присутствует в списке readonly полей
        """
        readonly_fields = self.admin.get_readonly_fields(request=None, obj=None)

        assert "onec_brand_id" in readonly_fields, "onec_brand_id должен быть в readonly_fields"

    def test_onec_brand_id_in_search_fields(self):
        """
        AC3: Проверка что onec_brand_id доступен для поиска

        Given: ProductAdmin настроен
        When: Проверяем search_fields
        Then: onec_brand_id присутствует в списке полей для поиска
        """
        search_fields = self.admin.search_fields

        assert "onec_brand_id" in search_fields, "onec_brand_id должен быть в search_fields"

    def test_onec_brand_id_in_fieldsets(self):
        """
        AC3: Проверка что onec_brand_id отображается в fieldsets

        Given: ProductAdmin настроен с fieldsets
        When: Проверяем структуру fieldsets
        Then: onec_brand_id присутствует в секции "Интеграция с 1С"
        """
        fieldsets = self.admin.get_fieldsets(request=None, obj=None)

        # Ищем секцию "Интеграция с 1С" или аналогичную
        onec_section_found = False
        onec_brand_id_found = False

        for section_name, section_data in fieldsets:
            if section_name and "1С" in section_name:
                onec_section_found = True
                fields = section_data.get("fields", [])

                # Проверяем что onec_brand_id в этой секции
                for field in fields:
                    if isinstance(field, (list, tuple)):
                        if "onec_brand_id" in field:
                            onec_brand_id_found = True
                            break
                    elif field == "onec_brand_id":
                        onec_brand_id_found = True
                        break

        assert onec_section_found, "Должна существовать секция с 1С данными в fieldsets"
        assert onec_brand_id_found, "onec_brand_id должен быть в секции 1С данных"

    def test_onec_brand_id_readonly_in_form(self):
        """
        AC3: Проверка что onec_brand_id нельзя редактировать через форму

        Given: Товар с заполненным onec_brand_id
        When: Открываем форму редактирования в админке
        Then: Поле onec_brand_id доступно только для чтения
        """
        # Создаем товар с onec_brand_id
        brand = BrandFactory.create(name="Test Brand")
        category = CategoryFactory.create(name="Test Category")
        product = ProductFactory.create(
            name="Test Product",
            brand=brand,
            category=category,
            onec_brand_id="fb3f263e-dfd0-11ef-8361-fa163ea88911",
        )

        # Получаем readonly поля для конкретного объекта
        request = self.factory.get("/admin/products/product/")
        request.user = self.superuser

        readonly_fields = self.admin.get_readonly_fields(request, obj=product)

        assert "onec_brand_id" in readonly_fields, "onec_brand_id должен быть readonly при редактировании товара"

    def test_onec_brand_id_display_in_list(self):
        """
        AC3: Проверка что onec_brand_id может отображаться в list_display

        Given: ProductAdmin настроен
        When: Проверяем list_display (опционально)
        Then: onec_brand_id может быть в списке отображаемых полей
        """
        list_display = self.admin.list_display

        # onec_brand_id опционально может быть в list_display
        # Это не обязательное требование, но проверяем если есть
        if "onec_brand_id" in list_display:
            # Создаем товар для проверки отображения
            product = ProductFactory.create(onec_brand_id="fb3f263e-dfd0-11ef-8361-fa163ea88911")

            # Проверяем что значение можно получить
            assert product.onec_brand_id == "fb3f263e-dfd0-11ef-8361-fa163ea88911"

    def test_onec_brand_id_search_functionality(self):
        """
        AC3: Проверка функциональности поиска по onec_brand_id

        Given: Товары с разными onec_brand_id
        When: Выполняем поиск по onec_brand_id через админку
        Then: Находим правильные товары
        """
        # Создаем товары с разными brand_id
        brand = BrandFactory.create(name="Test Brand")
        category = CategoryFactory.create(name="Test Category")

        product1 = ProductFactory.create(
            name="Product 1",
            brand=brand,
            category=category,
            onec_brand_id="aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
        )
        product2 = ProductFactory.create(
            name="Product 2",
            brand=brand,
            category=category,
            onec_brand_id="bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
        )
        product3 = ProductFactory.create(
            name="Product 3",
            brand=brand,
            category=category,
            onec_brand_id=None,  # Товар без brand_id
        )

        # Создаем запрос с поиском
        request = self.factory.get("/admin/products/product/", {"q": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"})
        request.user = self.superuser

        # Получаем queryset с примененным поиском
        changelist = self.admin.get_changelist_instance(request)
        queryset = changelist.get_queryset(request)

        # Проверяем что нашли правильный товар
        assert queryset.filter(id=product1.id).exists(), "Поиск должен найти товар с указанным onec_brand_id"

        # Проверяем что другие товары не найдены
        assert not queryset.filter(id=product2.id).exists(), "Поиск не должен найти товар с другим onec_brand_id"

    def test_onec_brand_id_null_display(self):
        """
        AC3: Проверка отображения NULL значения onec_brand_id в админке

        Given: Товар без onec_brand_id (NULL)
        When: Открываем товар в админке
        Then: Поле корректно отображает отсутствие значения
        """
        # Создаем товар без brand_id
        product = ProductFactory.create(onec_brand_id=None)

        # Получаем readonly поля
        request = self.factory.get("/admin/products/product/")
        request.user = self.superuser

        readonly_fields = self.admin.get_readonly_fields(request, obj=product)

        assert "onec_brand_id" in readonly_fields
        assert product.onec_brand_id is None, "onec_brand_id должен быть None для товара без бренда"


@pytest.mark.django_db
class TestBrandAdmin(TestCase):
    """Тесты для BrandAdmin"""

    def setUp(self):
        self.site = AdminSite()
        self.admin = BrandAdmin(Brand, self.site)
        self.factory = RequestFactory()
        self.superuser = UserFactory.create(is_staff=True, is_superuser=True, email="admin@test.com")

    def test_brand_admin_inline(self):
        """AC1: Проверка наличия Brand1CMappingInline"""
        assert Brand1CMappingInline in self.admin.inlines

    def test_mappings_count_annotation(self):
        """AC2: Проверка подсчета маппингов"""
        brand = BrandFactory()
        Brand1CMappingFactory(brand=brand)
        Brand1CMappingFactory(brand=brand)

        request = self.factory.get("/admin/products/brand/")
        request.user = self.superuser

        qs = self.admin.get_queryset(request)
        obj = qs.get(pk=brand.pk)

        assert hasattr(obj, "mappings_count")
        assert obj.mappings_count == 2

    def _setup_request(self, request):
        from django.contrib.messages.storage.fallback import FallbackStorage

        setattr(request, "session", "session")
        messages = FallbackStorage(request)
        setattr(request, "_messages", messages)
        return request

    def test_merge_brands_action_rendering(self):
        """Task 2: Тест рендеринга страницы объединения"""
        brand1 = BrandFactory()
        brand2 = BrandFactory()

        request = self.factory.post(
            "/admin/products/brand/merge_brands/",
            {"action": "merge_brands", "_selected_action": [brand1.pk, brand2.pk]},
        )
        request.user = self.superuser
        self._setup_request(request)

        # Вызов действия без apply
        response = self.admin.merge_brands(request, Brand.objects.all())
        assert response.status_code == 200

    def test_merge_brands_action_execution(self):
        """AC3, AC4, AC7: Тест выполнения объединения"""
        target_brand = BrandFactory(name="Target")
        source_brand = BrandFactory(name="Source")

        # Маппинги
        m1 = Brand1CMappingFactory(brand=source_brand, onec_id="id1")

        # Продукты
        p1 = ProductFactory(brand=source_brand)

        request = self.factory.post(
            "/admin/products/brand/",
            {
                "action": "merge_brands",
                "apply": "1",
                "target_brand": target_brand.pk,
                "_selected_action": [source_brand.pk],
            },
        )
        request.user = self.superuser
        self._setup_request(request)

        self.admin.merge_brands(request, Brand.objects.filter(pk__in=[source_brand.pk]))

        # Проверки
        assert not Brand.objects.filter(pk=source_brand.pk).exists()
        assert Product.objects.get(pk=p1.pk).brand == target_brand
        assert Brand1CMapping.objects.get(pk=m1.pk).brand == target_brand

    def test_merge_brands_multiple_mappings(self):
        """AC3: Тест переноса нескольких маппингов"""
        target_brand = BrandFactory(name="Target")
        source_brand = BrandFactory(name="Source")

        m1 = Brand1CMappingFactory(brand=source_brand, onec_id="id1")
        m2 = Brand1CMappingFactory(brand=source_brand, onec_id="id2")

        request = self.factory.post(
            "/admin/products/brand/",
            {
                "action": "merge_brands",
                "apply": "1",
                "target_brand": target_brand.pk,
                "_selected_action": [source_brand.pk],
            },
        )
        request.user = self.superuser
        self._setup_request(request)

        self.admin.merge_brands(request, Brand.objects.filter(pk__in=[source_brand.pk]))

        # Проверки
        m1.refresh_from_db()
        m2.refresh_from_db()
        assert m1.brand == target_brand
        assert m2.brand == target_brand
        assert not Brand.objects.filter(pk=source_brand.pk).exists()


@pytest.mark.django_db
class TestBrand1CMappingAdmin(TestCase):
    def setUp(self):
        self.site = AdminSite()
        self.admin = Brand1CMappingAdmin(Brand1CMapping, self.site)
        self.factory = RequestFactory()
        self.superuser = UserFactory.create(is_staff=True, is_superuser=True)

    def _setup_request(self, request):
        from django.contrib.messages.storage.fallback import FallbackStorage

        setattr(request, "session", "session")
        messages = FallbackStorage(request)
        setattr(request, "_messages", messages)
        return request

    def test_transfer_action(self):
        """AC6: Тест переноса маппинга"""
        brand1 = BrandFactory()
        brand2 = BrandFactory()
        mapping = Brand1CMappingFactory(brand=brand1)

        request = self.factory.post(
            "/",
            {
                "action": "transfer_to_brand",
                "apply": "1",
                "target_brand": brand2.pk,
                "_selected_action": [mapping.pk],
            },
        )
        request.user = self.superuser
        self._setup_request(request)

        self.admin.transfer_to_brand(request, Brand1CMapping.objects.all())

        mapping.refresh_from_db()
        assert mapping.brand == brand2


@pytest.mark.django_db
class TestPriceTypeAdmin(TestCase):
    """Стори 40.2: справочник видов цен правится менеджером из админки"""

    def setUp(self):
        self.site = AdminSite()
        self.admin = PriceTypeAdmin(PriceType, self.site)

    GUID_OPT1 = "90d2c899-b3f2-11ea-81c3-00155d3cae02"

    def _form_data(self, user_role: str, onec_id: str | None = None) -> dict:
        return {
            "onec_id": onec_id if onec_id is not None else self.GUID_OPT1,
            "onec_name": "Опт 1 (300-600 тыс.руб в квартал)",
            "product_field": "opt1_price",
            "user_role": user_role,
            "is_active": True,
        }

    def _create_price_type(self, onec_id: str, user_role: str = "wholesale_level1") -> PriceType:
        return PriceType.objects.create(
            onec_id=onec_id,
            onec_name="Опт 1 (300-600 тыс.руб в квартал)",
            product_field="opt1_price",
            user_role=user_role,
        )

    def test_model_is_registered_in_admin(self):
        """AC3: модель зарегистрирована на стандартном сайте админки"""
        from django.contrib import admin as django_admin

        assert django_admin.site.is_registered(PriceType), "PriceType должен быть зарегистрирован в админке"

    def test_list_display_contains_required_columns(self):
        """AC3: список показывает вид цен, поле товара, роль и активность"""
        for field in ("onec_name", "product_field", "user_role", "is_active"):
            assert field in self.admin.list_display, f"{field} должен быть в list_display"

    def test_user_role_is_editable(self):
        """AC3: роль правится менеджером, значит не readonly"""
        readonly_fields = self.admin.get_readonly_fields(request=None, obj=None)

        assert "user_role" not in readonly_fields

    def test_search_by_onec_id_and_name(self):
        """AC3: справочник ищется по наименованию и GUID"""
        assert "onec_name" in self.admin.search_fields
        assert "onec_id" in self.admin.search_fields

    def test_list_editable_not_used(self):
        """
        Мина: ModelAdmin.get_changelist_form игнорирует self.form и строит
        форму списка через modelform_factory — в changelist user_role стал бы
        свободным текстовым полем, и AC4 был бы обойдён.
        """
        assert not getattr(self.admin, "list_editable", ())

    def test_form_limits_user_role_to_choice_field(self):
        """AC4: свободный ввод роли запрещён"""
        from django import forms as django_forms

        form = PriceTypeAdminForm()

        assert isinstance(form.fields["user_role"], django_forms.ChoiceField)

    def test_form_offers_empty_choice(self):
        """AC4: пустое значение остаётся допустимым (РРЦ, МРЦ)"""
        form = PriceTypeAdminForm()
        values = [value for value, _label in form.fields["user_role"].choices]

        assert "" in values
        assert "wholesale_level1" in values

    def test_form_rejects_typo_in_role(self):
        """AC4: опечатка «wholesale_level_2» не должна доехать до аккаунта"""
        form = PriceTypeAdminForm(data=self._form_data("wholesale_level_2"))

        assert not form.is_valid()
        assert "user_role" in form.errors

    def test_form_accepts_existing_role(self):
        form = PriceTypeAdminForm(data=self._form_data("wholesale_level1"))

        assert form.is_valid(), form.errors

    def test_form_accepts_empty_role(self):
        form = PriceTypeAdminForm(data=self._form_data(""))

        assert form.is_valid(), form.errors

    def test_form_lowercases_onec_id(self):
        """
        Review-находка 40.2: резолвер ищет роль по GUID в нижнем регистре.

        Нормализация на записи не даёт завести регистрового двойника, из-за
        которого роль стала бы зависеть от порядка выборки.
        """
        form = PriceTypeAdminForm(data=self._form_data("wholesale_level1", onec_id=self.GUID_OPT1.upper()))

        assert form.is_valid(), form.errors
        assert form.cleaned_data["onec_id"] == self.GUID_OPT1

    def test_form_strips_whitespace_in_onec_id(self):
        """GUID из 1С копируют вручную — пробелы по краям не должны сохраняться."""
        form = PriceTypeAdminForm(data=self._form_data("wholesale_level1", onec_id=f"  {self.GUID_OPT1}  "))

        assert form.is_valid(), form.errors
        assert form.cleaned_data["onec_id"] == self.GUID_OPT1

    def test_form_rejects_case_variant_of_existing_guid(self):
        """Review-находка 40.2: двойник в другом регистре — ошибка валидации."""
        self._create_price_type(self.GUID_OPT1)

        form = PriceTypeAdminForm(data=self._form_data("wholesale_level2", onec_id=self.GUID_OPT1.upper()))

        assert not form.is_valid()
        assert "onec_id" in form.errors

    def test_form_allows_resaving_the_same_record(self):
        """Проверка дублей не должна ловить саму редактируемую запись."""
        record = self._create_price_type(self.GUID_OPT1)

        form = PriceTypeAdminForm(data=self._form_data("wholesale_level2"), instance=record)

        assert form.is_valid(), form.errors
