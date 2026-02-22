"""
Unit тесты для Django Admin конфигурации пользователей
Покрывает UserAdmin, admin actions, custom display methods и AuditLog интеграцию
"""

import pytest
from django.contrib.admin.sites import AdminSite
from django.contrib.auth import get_user_model
from django.test import RequestFactory, TestCase
from django.utils.html import strip_tags

from apps.common.models import AuditLog
from apps.users.admin import CompanyAdmin, UserAdmin
from apps.users.models import Address, Company

User = get_user_model()


@pytest.mark.django_db
class TestUserAdmin(TestCase):
    """Тесты для UserAdmin класса"""

    def setUp(self):
        """Настройка тестовых данных"""
        self.site = AdminSite()
        self.admin = UserAdmin(User, self.site)
        self.factory = RequestFactory()

        # Создаем суперпользователя для запросов
        self.superuser = User.objects.create_superuser(
            email="admin@test.com",
            password="testpass123",
            first_name="Admin",
            last_name="User",
        )

        # Создаем тестовых пользователей
        self.retail_user = User.objects.create_user(
            email="retail@test.com",
            password="testpass123",
            first_name="Retail",
            last_name="User",
            role="retail",
            phone="+79001234567",
        )

        self.b2b_user = User.objects.create_user(
            email="b2b@test.com",
            password="testpass123",
            first_name="B2B",
            last_name="User",
            role="wholesale_level1",
            company_name="Test Company",
            tax_id="1234567890",
            is_verified=False,
            verification_status="pending",
        )

        # Создаем компанию для B2B пользователя
        self.company = Company.objects.create(
            user=self.b2b_user,
            legal_name="Test Company LLC",
            tax_id="1234567890",
            legal_address="Test Address",
        )

    def test_list_display_fields(self):
        """Тест конфигурации list_display"""
        expected_fields = [
            "email",
            "full_name",
            "role_display",
            "verification_status_display",
            "phone",
            "created_at",
        ]
        self.assertEqual(self.admin.list_display, expected_fields)

    def test_list_filter_fields(self):
        """Тест конфигурации list_filter"""
        expected_filters = [
            "role",
            "is_verified",
            "verification_status",
            "created_at",
            "is_active",
            "is_staff",
        ]
        self.assertEqual(self.admin.list_filter, expected_filters)

    def test_search_fields(self):
        """Тест конфигурации search_fields"""
        expected_fields = [
            "email",
            "first_name",
            "last_name",
            "phone",
            "company_name",
            "tax_id",
        ]
        self.assertEqual(self.admin.search_fields, expected_fields)

    def test_readonly_fields(self):
        """Тест readonly_fields для integration данных"""
        expected_readonly = [
            "onec_id",
            "onec_guid",
            "last_sync_at",
            "last_sync_from_1c",
            "created_at",
            "updated_at",
            "company_legal_address",
        ]
        self.assertEqual(self.admin.readonly_fields, expected_readonly)

    def test_list_select_related(self):
        """Тест оптимизации N+1 queries"""
        self.assertEqual(self.admin.list_select_related, ["company"])

    def test_full_name_display(self):
        """Тест метода full_name"""
        result = self.admin.full_name(self.retail_user)
        self.assertEqual(result, "Retail User")

        # Тест с пустым именем
        empty_user = User.objects.create_user(email="empty@test.com", password="testpass123")
        result = self.admin.full_name(empty_user)
        self.assertEqual(result, "-")

    def test_role_display_with_colors(self):
        """Тест метода role_display с цветовой индикацией"""
        result = self.admin.role_display(self.retail_user)
        self.assertIn("●", result)
        self.assertIn("Розничный покупатель", result)
        self.assertIn("#6c757d", result)  # серый цвет для retail

        result = self.admin.role_display(self.b2b_user)
        self.assertIn("●", result)
        self.assertIn("Оптовик уровень 1", result)
        self.assertIn("#0dcaf0", result)  # голубой цвет для wholesale_level1

    def test_verification_status_display_verified(self):
        """Тест отображения верифицированного статуса"""
        self.b2b_user.is_verified = True
        self.b2b_user.verification_status = "verified"
        self.b2b_user.save()

        result = self.admin.verification_status_display(self.b2b_user)
        self.assertIn("✓", result)
        self.assertIn("Верифицирован", result)
        self.assertIn("green", result)

    def test_verification_status_display_pending(self):
        """Тест отображения ожидающего статуса"""
        result = self.admin.verification_status_display(self.b2b_user)
        self.assertIn("⏳", result)
        self.assertIn("Ожидает", result)
        self.assertIn("orange", result)

    def test_verification_status_display_unverified(self):
        """Тест отображения неверифицированного статуса"""
        self.b2b_user.verification_status = "unverified"
        self.b2b_user.save()

        result = self.admin.verification_status_display(self.b2b_user)
        self.assertIn("○", result)
        self.assertIn("Не верифицирован", result)
        self.assertIn("gray", result)

    def test_company_legal_address_display(self):
        """Тест отображения юридического адреса компании"""
        result = self.admin.company_legal_address(self.b2b_user)
        self.assertEqual(result, "Test Address")

        # Тест для пользователя без компании
        result = self.admin.company_legal_address(self.retail_user)
        self.assertEqual(result, "-")

    def test_approve_b2b_users_action(self):
        """Тест массовой верификации B2B пользователей"""
        # Создаем request
        request = self.factory.post("/admin/users/user/")
        request.user = self.superuser
        request.META["REMOTE_ADDR"] = "127.0.0.1"
        request.META["HTTP_USER_AGENT"] = "Test Browser"
        # Mock messages framework
        from django.contrib.messages.storage.cookie import CookieStorage

        setattr(request, "session", "session")
        setattr(request, "_messages", CookieStorage(request))

        # Создаем queryset
        queryset = User.objects.filter(id=self.b2b_user.id)

        # Выполняем action
        self.admin.approve_b2b_users(request, queryset)

        # Проверяем результат
        self.b2b_user.refresh_from_db()
        self.assertTrue(self.b2b_user.is_verified)
        self.assertEqual(self.b2b_user.verification_status, "verified")

        # Проверяем AuditLog
        audit_log = AuditLog.objects.filter(
            action="approve_b2b",
            resource_type="User",
            resource_id=str(self.b2b_user.id),
        ).first()
        self.assertIsNotNone(audit_log)
        self.assertEqual(audit_log.user, self.superuser)
        self.assertEqual(audit_log.changes["email"], "b2b@test.com")
        self.assertTrue(audit_log.changes["verified"])

    def test_approve_b2b_users_filters_non_b2b(self):
        """Тест что approve_b2b_users не затрагивает retail пользователей"""
        request = self.factory.post("/admin/users/user/")
        request.user = self.superuser
        request.META["REMOTE_ADDR"] = "127.0.0.1"
        request.META["HTTP_USER_AGENT"] = "Test Browser"
        from django.contrib.messages.storage.cookie import CookieStorage

        setattr(request, "session", "session")
        setattr(request, "_messages", CookieStorage(request))

        # Включаем retail пользователя в queryset
        queryset = User.objects.filter(id__in=[self.retail_user.id, self.b2b_user.id])

        # Выполняем action
        self.admin.approve_b2b_users(request, queryset)

        # Проверяем что retail не изменился
        self.retail_user.refresh_from_db()
        self.assertFalse(self.retail_user.is_verified)

        # Проверяем что B2B изменился
        self.b2b_user.refresh_from_db()
        self.assertTrue(self.b2b_user.is_verified)

    def test_approve_b2b_users_empty_queryset_validation(self):
        """Тест input validation при пустом queryset для approve"""
        request = self.factory.post("/admin/users/user/")
        request.user = self.superuser
        request.META["REMOTE_ADDR"] = "127.0.0.1"
        request.META["HTTP_USER_AGENT"] = "Test Browser"
        from django.contrib.messages.storage.cookie import CookieStorage

        setattr(request, "session", "session")
        setattr(request, "_messages", CookieStorage(request))

        # Только retail пользователи (не B2B)
        queryset = User.objects.filter(id=self.retail_user.id)

        # Выполняем action
        self.admin.approve_b2b_users(request, queryset)

        # Проверяем что AuditLog не создан
        audit_count = AuditLog.objects.filter(action="approve_b2b").count()
        self.assertEqual(audit_count, 0)

    def test_approve_b2b_users_superuser_validation(self):
        """Тест что approve_b2b_users не верифицирует суперпользователей"""
        # Создаем B2B суперпользователя
        b2b_super = User.objects.create_superuser(
            email="b2bsuper@test.com",
            password="testpass123",
        )
        b2b_super.role = "wholesale_level1"
        b2b_super.save()

        request = self.factory.post("/admin/users/user/")
        request.user = self.superuser
        request.META["REMOTE_ADDR"] = "127.0.0.1"
        request.META["HTTP_USER_AGENT"] = "Test Browser"
        from django.contrib.messages.storage.cookie import CookieStorage

        setattr(request, "session", "session")
        setattr(request, "_messages", CookieStorage(request))

        queryset = User.objects.filter(id=b2b_super.id)

        # Выполняем action
        self.admin.approve_b2b_users(request, queryset)

        # Проверяем что AuditLog не создан
        audit_count = AuditLog.objects.filter(action="approve_b2b", resource_id=str(b2b_super.id)).count()
        self.assertEqual(audit_count, 0)

    def test_reject_b2b_users_action(self):
        """Тест массового отказа в верификации B2B пользователей"""
        # Сначала верифицируем
        self.b2b_user.is_verified = True
        self.b2b_user.verification_status = "verified"
        self.b2b_user.save()

        # Создаем request
        request = self.factory.post("/admin/users/user/")
        request.user = self.superuser
        request.META["REMOTE_ADDR"] = "127.0.0.1"
        request.META["HTTP_USER_AGENT"] = "Test Browser"
        from django.contrib.messages.storage.cookie import CookieStorage

        setattr(request, "session", "session")
        setattr(request, "_messages", CookieStorage(request))

        # Создаем queryset
        queryset = User.objects.filter(id=self.b2b_user.id)

        # Выполняем action
        self.admin.reject_b2b_users(request, queryset)

        # Проверяем результат
        self.b2b_user.refresh_from_db()
        self.assertFalse(self.b2b_user.is_verified)
        self.assertEqual(self.b2b_user.verification_status, "unverified")

        # Проверяем AuditLog
        audit_log = AuditLog.objects.filter(
            action="reject_b2b", resource_type="User", resource_id=str(self.b2b_user.id)
        ).first()
        self.assertIsNotNone(audit_log)
        self.assertFalse(audit_log.changes["verified"])

    def test_block_users_action(self):
        """Тест массовой блокировки пользователей"""
        # Создаем request
        request = self.factory.post("/admin/users/user/")
        request.user = self.superuser
        request.META["REMOTE_ADDR"] = "127.0.0.1"
        request.META["HTTP_USER_AGENT"] = "Test Browser"
        from django.contrib.messages.storage.cookie import CookieStorage

        setattr(request, "session", "session")
        setattr(request, "_messages", CookieStorage(request))

        # Создаем queryset
        queryset = User.objects.filter(id=self.retail_user.id)

        # Выполняем action
        self.admin.block_users(request, queryset)

        # Проверяем результат
        self.retail_user.refresh_from_db()
        self.assertFalse(self.retail_user.is_active)

        # Проверяем AuditLog
        audit_log = AuditLog.objects.filter(
            action="block_user",
            resource_type="User",
            resource_id=str(self.retail_user.id),
        ).first()
        self.assertIsNotNone(audit_log)
        self.assertTrue(audit_log.changes["blocked"])

    def test_block_users_skips_superusers(self):
        """Тест что block_users не блокирует суперпользователей"""
        request = self.factory.post("/admin/users/user/")
        request.user = self.superuser
        request.META["REMOTE_ADDR"] = "127.0.0.1"
        request.META["HTTP_USER_AGENT"] = "Test Browser"
        from django.contrib.messages.storage.cookie import CookieStorage

        setattr(request, "session", "session")
        setattr(request, "_messages", CookieStorage(request))

        # Пытаемся заблокировать суперпользователя
        queryset = User.objects.filter(id=self.superuser.id)

        # Выполняем action
        self.admin.block_users(request, queryset)

        # Проверяем что суперпользователь остался активным
        self.superuser.refresh_from_db()
        self.assertTrue(self.superuser.is_active)

        # Проверяем что AuditLog не создан
        audit_log = AuditLog.objects.filter(action="block_user", resource_id=str(self.superuser.id)).first()
        self.assertIsNone(audit_log)

    def test_block_users_empty_queryset_validation(self):
        """Тест input validation при пустом queryset для block"""
        request = self.factory.post("/admin/users/user/")
        request.user = self.superuser
        request.META["REMOTE_ADDR"] = "127.0.0.1"
        request.META["HTTP_USER_AGENT"] = "Test Browser"
        from django.contrib.messages.storage.cookie import CookieStorage

        setattr(request, "session", "session")
        setattr(request, "_messages", CookieStorage(request))

        # Пустой queryset
        queryset = User.objects.none()

        # Выполняем action
        self.admin.block_users(request, queryset)

        # Проверяем что AuditLog не создан
        audit_count = AuditLog.objects.filter(action="block_user").count()
        self.assertEqual(audit_count, 0)

    def test_reject_b2b_users_empty_queryset_validation(self):
        """Тест input validation при пустом queryset для reject"""
        request = self.factory.post("/admin/users/user/")
        request.user = self.superuser
        request.META["REMOTE_ADDR"] = "127.0.0.1"
        request.META["HTTP_USER_AGENT"] = "Test Browser"
        from django.contrib.messages.storage.cookie import CookieStorage

        setattr(request, "session", "session")
        setattr(request, "_messages", CookieStorage(request))

        # Только retail пользователи (не B2B)
        queryset = User.objects.filter(id=self.retail_user.id)

        # Выполняем action
        self.admin.reject_b2b_users(request, queryset)

        # Проверяем что AuditLog не создан
        audit_count = AuditLog.objects.filter(action="reject_b2b").count()
        self.assertEqual(audit_count, 0)

    def test_get_client_ip_with_x_forwarded_for(self):
        """Тест получения IP из X-Forwarded-For заголовка"""
        request = self.factory.get("/admin/")
        request.META["HTTP_X_FORWARDED_FOR"] = "192.168.1.1, 10.0.0.1"

        ip = self.admin._get_client_ip(request)
        self.assertEqual(ip, "192.168.1.1")

    def test_get_client_ip_with_remote_addr(self):
        """Тест получения IP из REMOTE_ADDR"""
        request = self.factory.get("/admin/")
        request.META["REMOTE_ADDR"] = "127.0.0.1"

        ip = self.admin._get_client_ip(request)
        self.assertEqual(ip, "127.0.0.1")

    def test_get_client_ip_fallback(self):
        """Тест fallback для IP адреса"""
        request = self.factory.get("/admin/")
        # RequestFactory устанавливает REMOTE_ADDR в 127.0.0.1 по умолчанию
        # Удаляем его для теста fallback
        if "REMOTE_ADDR" in request.META:
            del request.META["REMOTE_ADDR"]

        ip = self.admin._get_client_ip(request)
        self.assertEqual(ip, "0.0.0.0")

    def test_company_inline_configuration(self):
        """Тест конфигурации CompanyInline"""
        from apps.users.admin import CompanyInline

        inline = CompanyInline(User, self.site)
        self.assertEqual(inline.model, Company)
        self.assertFalse(inline.can_delete)

    def test_address_inline_configuration(self):
        """Тест конфигурации AddressInline"""
        from apps.users.admin import AddressInline

        inline = AddressInline(User, self.site)
        self.assertEqual(inline.model, Address)
        self.assertEqual(inline.extra, 0)

    def test_admin_actions_list(self):
        """Тест списка доступных admin actions"""
        expected_actions = [
            "approve_b2b_users",
            "reject_b2b_users",
            "block_users",
        ]
        self.assertEqual(self.admin.actions, expected_actions)

    def test_fieldsets_structure(self):
        """Тест структуры fieldsets"""
        fieldsets = self.admin.fieldsets

        # Проверяем количество секций (Story 9.1: 6 секций)
        self.assertEqual(len(fieldsets), 6)

        # Проверяем названия секций
        section_names = [fs[0] for fs in fieldsets]
        self.assertIn("Основная информация", section_names)
        self.assertIn("B2B данные", section_names)
        self.assertIn("Роль и статус", section_names)
        self.assertIn("Интеграция с 1С", section_names)
        self.assertIn("Временные метки", section_names)

    def test_add_fieldsets_structure(self):
        """Тест структуры add_fieldsets для создания пользователя"""
        add_fieldsets = self.admin.add_fieldsets

        # Проверяем наличие обязательных полей
        fields = add_fieldsets[0][1]["fields"]
        self.assertIn("email", fields)
        self.assertIn("password1", fields)
        self.assertIn("password2", fields)
        self.assertIn("role", fields)


@pytest.mark.django_db
class TestCompanyAdmin(TestCase):
    """Тесты для CompanyAdmin"""

    def setUp(self):
        """Настройка тестовых данных"""
        self.site = AdminSite()
        self.admin = CompanyAdmin(Company, self.site)

        self.user = User.objects.create_user(email="test@test.com", password="testpass123")

        self.company = Company.objects.create(
            user=self.user,
            legal_name="Test Company",
            tax_id="1234567890",
            legal_address="Test Address",
        )

    def test_list_display_fields(self):
        """Тест конфигурации list_display"""
        expected_fields = ["legal_name", "tax_id", "user", "created_at"]
        self.assertEqual(self.admin.list_display, expected_fields)

    def test_search_fields(self):
        """Тест конфигурации search_fields"""
        expected_fields = ["legal_name", "tax_id", "user__email"]
        self.assertEqual(self.admin.search_fields, expected_fields)


@pytest.mark.django_db
class TestAuditLogIntegration(TestCase):
    """Тесты интеграции с AuditLog"""

    def setUp(self):
        """Настройка тестовых данных"""
        self.site = AdminSite()
        self.admin = UserAdmin(User, self.site)
        self.factory = RequestFactory()

        self.superuser = User.objects.create_superuser(email="admin@test.com", password="testpass123")

        self.b2b_user = User.objects.create_user(
            email="b2b@test.com",
            password="testpass123",
            role="wholesale_level1",
            verification_status="pending",
        )

    def test_audit_log_created_on_approve(self):
        """Тест создания AuditLog при верификации"""
        initial_count = AuditLog.objects.count()

        request = self.factory.post("/admin/users/user/")
        request.user = self.superuser
        request.META["REMOTE_ADDR"] = "127.0.0.1"
        request.META["HTTP_USER_AGENT"] = "Test Browser"
        from django.contrib.messages.storage.cookie import CookieStorage

        setattr(request, "session", "session")
        setattr(request, "_messages", CookieStorage(request))

        queryset = User.objects.filter(id=self.b2b_user.id)
        self.admin.approve_b2b_users(request, queryset)

        # Проверяем что создана одна запись
        self.assertEqual(AuditLog.objects.count(), initial_count + 1)

        # Проверяем содержимое записи
        log = AuditLog.objects.latest("created_at")
        self.assertEqual(log.action, "approve_b2b")
        self.assertEqual(log.resource_type, "User")
        self.assertEqual(log.user, self.superuser)
        self.assertEqual(log.ip_address, "127.0.0.1")

    def test_audit_log_contains_changes(self):
        """Тест что AuditLog содержит детали изменений"""
        request = self.factory.post("/admin/users/user/")
        request.user = self.superuser
        request.META["REMOTE_ADDR"] = "127.0.0.1"
        request.META["HTTP_USER_AGENT"] = "Mozilla/5.0"
        from django.contrib.messages.storage.cookie import CookieStorage

        setattr(request, "session", "session")
        setattr(request, "_messages", CookieStorage(request))

        queryset = User.objects.filter(id=self.b2b_user.id)
        self.admin.approve_b2b_users(request, queryset)

        log = AuditLog.objects.latest("created_at")
        self.assertIn("email", log.changes)
        self.assertIn("role", log.changes)
        self.assertIn("verified", log.changes)
        self.assertEqual(log.changes["email"], "b2b@test.com")
        self.assertEqual(log.changes["role"], "wholesale_level1")
        self.assertTrue(log.changes["verified"])
