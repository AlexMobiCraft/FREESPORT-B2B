"""Регрессионные тесты для race-condition фикса в handle_init и _dispatch_or_dryrun.

Проверяет 6 сценариев из I/O Matrix спеки
`tech-spec-fix-1c-import-cleanup-race.md`: orchestrator marks IN_PROGRESS до marker,
race-skip в init, чистый cleanup, нет marker, DB-исключение, терминальные статусы.

Ключевые patch targets:
- `FileStreamService` (views.py:27, import_orchestrator.py:21) — module-level импорт →
  patch `apps.integrations.onec_exchange.views.FileStreamService` /
  `apps.integrations.onec_exchange.import_orchestrator.FileStreamService`.
- `FileRoutingService` — импортируется ЛОКАЛЬНО внутри handle_init (views.py:426),
  локальный импорт пересоздаёт имя в области функции и обходит mock на views-namespace →
  patch `apps.integrations.onec_exchange.routing_service.FileRoutingService`.
- `process_1c_import_task` — импортируется локально внутри `_dispatch_or_dryrun`, но
  `apps.products.tasks.process_1c_import_task.delay` — это метод того же объекта task,
  поэтому patch на этом target работает независимо от места импорта.
"""
import logging
import re
from unittest.mock import MagicMock, patch

import pytest
from django.db import OperationalError
from django.urls import reverse
from rest_framework.test import APIClient

from apps.products.models import ImportSession
from apps.users.models import User


SKIP_LOG_REGEX = re.compile(r"Skipping import dir cleanup — \d+ sessions in progress")
INIT_BODY_REGEX = re.compile(r"^zip=(yes|no)\nfile_limit=\d+\nsessid=[^\n]+\nversion=[^\n]+\n$")


@pytest.mark.django_db
class TestHandleInitCleanupRace:
    """Тесты на guard в handle_init, защищающий shared import dir от удаления
    под бегущими Celery-задачами предыдущего цикла."""

    SESSID = "test-sessid-cleanup-race"

    def setup_method(self):
        self.client = APIClient()
        self.user = User.objects.create_user(email="1c_init_race@example.com", password="password")
        self.user.is_staff = True
        self.user.save()
        self.client.force_authenticate(user=self.user)
        self.url = reverse("integrations:onec_exchange:exchange")

    def _get_init(self):
        return self.client.get(self.url, {"mode": "init", "sessid": self.SESSID})

    def _assert_init_response_ok(self, response):
        assert response.status_code == 200
        assert response["Content-Type"].startswith("text/plain")
        body = response.content.decode("utf-8")
        assert INIT_BODY_REGEX.match(body), f"Unexpected init body: {body!r}"

    @patch("apps.integrations.onec_exchange.routing_service.FileRoutingService")
    @patch("apps.integrations.onec_exchange.views.FileStreamService")
    def test_race_skip_when_in_progress_session_exists(self, mock_stream_cls, mock_routing_cls, caplog):
        """marker есть + есть IN_PROGRESS → весь cleanup-блок пропускается,
        marker сохраняется, INFO Skipping."""
        ImportSession.objects.create(
            session_key=self.SESSID,
            status=ImportSession.ImportStatus.IN_PROGRESS,
            import_type=ImportSession.ImportType.CATALOG,
        )
        stream = mock_stream_cls.return_value
        stream.is_complete.return_value = True
        routing = mock_routing_cls.return_value

        with caplog.at_level(logging.INFO, logger="apps.integrations.onec_exchange.views"):
            response = self._get_init()

        self._assert_init_response_ok(response)
        stream.cleanup_session.assert_not_called()
        routing.cleanup_import_dir.assert_not_called()
        stream.clear_complete.assert_not_called()
        assert any(
            SKIP_LOG_REGEX.search(rec.message) for rec in caplog.records
        ), f"Expected Skipping-log not found. Got: {[r.message for r in caplog.records]}"

    @patch("apps.integrations.onec_exchange.routing_service.FileRoutingService")
    @patch("apps.integrations.onec_exchange.views.FileStreamService")
    def test_clean_cleanup_when_no_active_sessions(self, mock_stream_cls, mock_routing_cls):
        """marker есть + нет активных → cleanup_session + cleanup_import_dir + clear_complete."""
        stream = mock_stream_cls.return_value
        stream.is_complete.return_value = True
        routing = mock_routing_cls.return_value

        response = self._get_init()

        self._assert_init_response_ok(response)
        stream.cleanup_session.assert_called_once_with(force=True)
        routing.cleanup_import_dir.assert_called_once_with(force=True)
        stream.clear_complete.assert_called_once_with()

    @patch("apps.integrations.onec_exchange.routing_service.FileRoutingService")
    @patch("apps.integrations.onec_exchange.views.FileStreamService")
    def test_no_marker_no_cleanup_invocation(self, mock_stream_cls, mock_routing_cls):
        """marker отсутствует → ни cleanup_session, ни cleanup_import_dir, ни clear_complete."""
        stream = mock_stream_cls.return_value
        stream.is_complete.return_value = False
        routing = mock_routing_cls.return_value

        response = self._get_init()

        self._assert_init_response_ok(response)
        stream.cleanup_session.assert_not_called()
        routing.cleanup_import_dir.assert_not_called()
        stream.clear_complete.assert_not_called()

    @patch("apps.products.models.ImportSession.objects.filter")
    @patch("apps.integrations.onec_exchange.routing_service.FileRoutingService")
    @patch("apps.integrations.onec_exchange.views.FileStreamService")
    def test_db_error_preserves_marker(self, mock_stream_cls, mock_routing_cls, mock_filter, caplog):
        """marker есть + ImportSession.objects.filter бросает OperationalError →
        ни cleanup_session, ни cleanup_import_dir, ни clear_complete не вызываются;
        marker сохраняется; HTTP 200 с корректным телом; WARNING-лог.

        Patch только метода .filter (не всего manager) — чтобы не сломать ORM
        для signals/middleware на время теста (узкий blast radius).
        """
        stream = mock_stream_cls.return_value
        stream.is_complete.return_value = True
        routing = mock_routing_cls.return_value
        mock_filter.side_effect = OperationalError("simulated DB outage")

        with caplog.at_level(logging.WARNING, logger="apps.integrations.onec_exchange.views"):
            response = self._get_init()

        self._assert_init_response_ok(response)
        stream.cleanup_session.assert_not_called()
        routing.cleanup_import_dir.assert_not_called()
        stream.clear_complete.assert_not_called()
        warning_msgs = [rec.message for rec in caplog.records if rec.levelno == logging.WARNING]
        assert any(
            self.SESSID in msg and "Active sessions check failed" in msg for msg in warning_msgs
        ), f"Expected WARNING with sessid not found. Got: {warning_msgs}"

    @patch("apps.integrations.onec_exchange.routing_service.FileRoutingService")
    @patch("apps.integrations.onec_exchange.views.FileStreamService")
    def test_terminal_statuses_do_not_block_cleanup(self, mock_stream_cls, mock_routing_cls):
        """В БД только COMPLETED/FAILED → DB-check вернёт 0 → cleanup_import_dir вызван."""
        ImportSession.objects.create(
            session_key="other-sess-completed",
            status=ImportSession.ImportStatus.COMPLETED,
            import_type=ImportSession.ImportType.CATALOG,
        )
        ImportSession.objects.create(
            session_key="other-sess-failed",
            status=ImportSession.ImportStatus.FAILED,
            import_type=ImportSession.ImportType.CATALOG,
        )
        stream = mock_stream_cls.return_value
        stream.is_complete.return_value = True
        routing = mock_routing_cls.return_value

        response = self._get_init()

        self._assert_init_response_ok(response)
        routing.cleanup_import_dir.assert_called_once_with(force=True)
        stream.clear_complete.assert_called_once_with()


@pytest.mark.django_db
class TestDispatchMarksInProgressBeforeMarker:
    """AC #1: `_dispatch_or_dryrun()` должен ставить session.status=IN_PROGRESS
    ДО `process_1c_import_task.delay(...)` И ДО `file_service.mark_complete()`.
    Закрывает окно очереди Celery, в котором handle_init guard иначе видел бы
    session как PENDING (не блокирующий) и стирал бы файлы под бегущей задачей."""

    SESSID = "test-orch-dispatch-sess"

    @patch("apps.integrations.onec_exchange.import_orchestrator.FileStreamService")
    @patch("apps.products.tasks.process_1c_import_task.delay")
    def test_session_marked_in_progress_before_dispatch_and_marker(self, mock_delay, mock_stream_cls):
        from apps.integrations.onec_exchange.import_orchestrator import ImportOrchestratorService

        session = ImportSession.objects.create(
            session_key=self.SESSID,
            status=ImportSession.ImportStatus.PENDING,
            import_type=ImportSession.ImportType.CATALOG,
        )

        captured = {}

        def capture_status_at_delay(*args, **kwargs):
            captured["delay"] = ImportSession.objects.get(pk=session.pk).status
            mr = MagicMock()
            mr.id = "task-id-stub"
            return mr

        def capture_status_at_mark():
            captured["mark"] = ImportSession.objects.get(pk=session.pk).status

        mock_delay.side_effect = capture_status_at_delay
        mock_stream_cls.return_value.mark_complete.side_effect = capture_status_at_mark

        orchestrator = ImportOrchestratorService(self.SESSID, filename="rests_1.xml")
        orchestrator._dispatch_or_dryrun(session, dry_run=False)

        # Оба наблюдения должны видеть session уже как IN_PROGRESS
        assert (
            captured.get("delay") == ImportSession.ImportStatus.IN_PROGRESS
        ), f"Celery .delay() saw status={captured.get('delay')}, ожидался IN_PROGRESS"
        assert (
            captured.get("mark") == ImportSession.ImportStatus.IN_PROGRESS
        ), f"mark_complete() saw status={captured.get('mark')}, ожидался IN_PROGRESS"

        # Финальное состояние в БД
        session.refresh_from_db()
        assert session.status == ImportSession.ImportStatus.IN_PROGRESS

        # Marker всё ещё ставится
        mock_stream_cls.return_value.mark_complete.assert_called_once()

        # Report содержит маркерную фразу из спеки (для аудита)
        assert "Celery task queued; session marked IN_PROGRESS before complete marker" in session.report
