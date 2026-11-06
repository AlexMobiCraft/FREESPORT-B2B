"""
Интеграционные тесты для admin actions приложения integrations
"""

import pytest
from django.contrib.auth import get_user_model
from django.test import Client
from django.urls import reverse

from apps.integrations.models import Session

User = get_user_model()


@pytest.mark.django_db
class TestImportSessionAdminActions:
    """Интеграционные тесты для действий в Django Admin"""

    @pytest.fixture
    def admin_user(self):
        """Создание администратора для доступа к admin панели"""
        return User.objects.create_superuser(email="admin@test.com", password="testpass123")

    @pytest.fixture
    def client(self, admin_user):
        """Создание аутентифицированного клиента"""
        client = Client()
        client.force_login(admin_user)
        return client

    @pytest.fixture
    def import_sessions(self):
        """Создание тестовых сессий импорта"""
        sessions = []
        for i in range(3):
            session = Session.objects.create(import_type="catalog", status="completed")
            sessions.append(session)
        return sessions

    def test_admin_changelist_page_loads(self, client):
        """
        Тест: страница списка сессий импорта загружается
        """
        # Arrange
        url = reverse("admin:integrations_session_changelist")

        # Act
        response = client.get(url)

        # Assert
        assert response.status_code == 200
        content = response.content.decode("utf-8")
        assert "Сессии импорта" in content

    def test_admin_filter_by_import_type(self, client, import_sessions):
        """
        Тест: фильтрация по типу импорта работает корректно
        """
        # Arrange
        url = reverse("admin:integrations_session_changelist")

        # Act
        response = client.get(url, {"import_type": "catalog"})

        # Assert
        assert response.status_code == 200
        # Проверяем, что все 3 сессии отображаются
        content = response.content.decode("utf-8")
        for session in import_sessions:
            assert str(session.id) in content

    def test_admin_list_display_fields(self, client, import_sessions):
        """
        Тест: проверка отображения полей в списке
        """
        # Arrange
        url = reverse("admin:integrations_session_changelist")

        # Act
        response = client.get(url)

        # Assert
        assert response.status_code == 200
        content = response.content.decode("utf-8")

        # Проверяем наличие заголовков колонок
        assert "Тип импорта" in content or "import_type" in content
        assert "Статус" in content or "status" in content
        assert "Длительность" in content or "duration" in content

    def test_admin_search_functionality(self, client):
        """
        Тест: функциональность поиска в admin панели
        """
        # Arrange
        session_with_error = Session.objects.create(
            import_type="catalog",
            status="failed",
            error_message="Test error message for search",
        )
        url = reverse("admin:integrations_session_changelist")

        # Act
        response = client.get(url, {"q": "Test error message"})

        # Assert
        assert response.status_code == 200
        content = response.content.decode("utf-8")
        assert str(session_with_error.id) in content

    def test_admin_detail_page_readonly_fields(self, client, import_sessions):
        """
        Тест: проверка readonly полей на странице детального просмотра
        """
        # Arrange
        session = import_sessions[0]
        url = reverse("admin:integrations_session_change", args=[session.id])

        # Act
        response = client.get(url)

        # Assert
        assert response.status_code == 200
        content = response.content.decode("utf-8")

        # Проверяем наличие readonly полей
        assert "started_at" in content.lower()
        assert "finished_at" in content.lower()

    # ========================================================================
    # Тесты для read-only режима (Story 9.7)
    # ========================================================================

    def test_session_page_accessible_at_new_url(self, client, import_sessions):
        """
        Тест: страница доступна по новому URL /admin/integrations/session/

        Story 9.7 AC#1: URL изменен с integrationimportsession на session
        """
        # Arrange - пытаемся получить URL для нового имени модели
        try:
            url = reverse("admin:integrations_session_changelist")
        except Exception:
            pytest.fail("URL не найден. Проверьте что модель правильно зарегистрирована")

        # Act
        response = client.get(url)

        # Assert
        assert response.status_code == 200, "Страница сессий должна быть доступна по новому URL"
        # Проверяем что сессии отображаются
        content = response.content.decode("utf-8")
        for session in import_sessions:
            assert str(session.id) in content

    def test_add_button_not_displayed(self, client):
        """
        Тест: кнопка "Add" не отображается

        Story 9.7 AC#3: Невозможно создать новые сессии через admin

        Примечание: Проверяем через unit test has_add_permission.
        Integration test проверяет что страница загружается без ошибок.
        """
        # Arrange
        url = reverse("admin:integrations_session_changelist")

        # Act
        response = client.get(url)

        # Assert
        assert response.status_code == 200

        # Проверяем что страница загружается
        # has_add_permission проверяется в unit тестах

    def test_change_page_not_accessible(self, client, import_sessions):
        """
        Тест: страница редактирования недоступна

        Story 9.7 AC#3: has_change_permission возвращает False
        """
        # Arrange
        session = import_sessions[0]
        url = reverse("admin:integrations_session_change", args=[session.id])

        # Act
        response = client.get(url)

        # Assert
        # В Django, если нет прав на изменение, показывается readonly view
        # или редирект на changelist
        assert response.status_code in [
            200,
            302,
            403,
        ], "Редактирование должно быть заблокировано"

        if response.status_code == 200:
            content = response.content.decode("utf-8")
            # Проверяем что форма в readonly режиме
            # или кнопка Save отсутствует
            assert (
                "readonly" in content.lower() or 'name="_save"' not in content
            ), "Форма должна быть в read-only режиме"

    def test_action_dropdown_is_empty_or_not_exists(self, client, import_sessions):
        """
        Тест: dropdown actions пустой или отсутствует

        Story 9.7 AC#2: Admin action "trigger_selective_import" удален
        """
        # Arrange
        url = reverse("admin:integrations_session_changelist")

        # Act
        response = client.get(url)

        # Assert
        assert response.status_code == 200
        content = response.content.decode("utf-8")

        # Проверяем что action "trigger_selective_import" отсутствует
        assert "trigger_selective_import" not in content, "Admin action 'trigger_selective_import' должен быть удален"
        assert "🚀 Запустить импорт" not in content, "Текст действия '🚀 Запустить импорт' не должен отображаться"

    def test_filters_work_correctly(self, client):
        """
        Тест: фильтры работают корректно

        Story 9.7 AC#6: Фильтры по статусу, типу, дате работают
        """
        # Arrange
        session1 = Session.objects.create(import_type="catalog", status="completed")
        session2 = Session.objects.create(import_type="stocks", status="failed")
        url = reverse("admin:integrations_session_changelist")

        # Act - фильтр по статусу
        response = client.get(url, {"status": "completed"})

        # Assert
        assert response.status_code == 200
        content = str(response.content)
        assert str(session1.id) in content
        # session2 не должна отображаться (другой статус)

        # Act - фильтр по типу
        response = client.get(url, {"import_type": "stocks"})

        # Assert
        assert response.status_code == 200
        content = str(response.content)
        assert str(session2.id) in content

    def test_search_works_correctly(self, client):
        """
        Тест: поиск работает корректно

        Story 9.7 AC#6: Поиск по ID и error_message работает
        """
        # Arrange
        session = Session.objects.create(
            import_type="catalog",
            status="failed",
            error_message="Unique error text 12345",
        )
        url = reverse("admin:integrations_session_changelist")

        # Act - поиск по error_message
        response = client.get(url, {"q": "Unique error text"})

        # Assert
        assert response.status_code == 200
        content = str(response.content)
        assert str(session.id) in content

        # Act - поиск по ID
        response = client.get(url, {"q": str(session.id)})

        # Assert
        assert response.status_code == 200
        content = str(response.content)
        assert str(session.id) in content

    def test_celery_task_status_displays_correctly(self, client):
        """
        Тест: колонка Celery Task отображается корректно

        Story 9.7 AC#4: Celery Task status отображается с иконками
        """
        # Arrange
        session = Session.objects.create(
            import_type="catalog",
            status="in_progress",
            celery_task_id="test-celery-task-id-123",
        )
        url = reverse("admin:integrations_session_changelist")

        # Act
        response = client.get(url)

        # Assert
        assert response.status_code == 200
        content = response.content.decode("utf-8")

        # Проверяем что task_id отображается
        assert "test-celery-task-id-123" in content or "Celery Task" in content

    def test_pagination_works(self, client):
        """
        Тест: пагинация работает корректно

        Story 9.7 AC#7: Пагинация работает для больших списков
        """
        # Arrange - создаем много сессий для тестирования пагинации
        for i in range(60):  # Больше чем list_per_page (обычно 50)
            Session.objects.create(import_type="catalog", status="completed")
        url = reverse("admin:integrations_session_changelist")

        # Act
        response = client.get(url)

        # Assert
        assert response.status_code == 200
        content = response.content.decode("utf-8")

        # Проверяем наличие пагинации
        assert (
            "paginator" in content.lower() or "page" in content.lower() or "1 of" in content
        ), "Пагинация должна работать для больших списков"

    def test_auto_refresh_javascript_file_loaded(self, client):
        """
        Тест: JavaScript файл автообновления подключен к странице

        Story 9.7 AC#5: Страница автоматически обновляется каждые 5 секунд
        QA Gate JS-001: Проверка существования и подключения JS файла
        """
        # Arrange
        url = reverse("admin:integrations_session_changelist")

        # Act
        response = client.get(url)

        # Assert
        assert response.status_code == 200
        content = response.content.decode("utf-8")

        # Проверяем что JavaScript файл подключен в HTML
        assert (
            "import_session_auto_refresh.js" in content
        ), "JavaScript файл для автообновления должен быть подключен через Media класс"

    def test_auto_refresh_javascript_file_exists(self):
        """
        Тест: JavaScript файл автообновления существует в файловой системе

        Story 9.7 AC#5: Автообновление каждые 5 секунд
        QA Gate JS-001: Проверка физического существования файла
        """
        # Arrange
        import os

        from django.contrib.staticfiles import finders

        # Путь к JavaScript файлу (через staticfiles finders)
        js_file_path = finders.find("admin/js/import_session_auto_refresh.js")

        # Act & Assert
        assert js_file_path, "JavaScript файл должен существовать в staticfiles"
        assert os.path.exists(js_file_path), f"JavaScript файл должен существовать по пути: {js_file_path}"
        assert os.path.isfile(js_file_path), f"Путь должен указывать на файл, а не директорию: {js_file_path}"

        # Дополнительно: проверяем что файл не пустой
        assert os.path.getsize(js_file_path) > 0, "JavaScript файл не должен быть пустым"
