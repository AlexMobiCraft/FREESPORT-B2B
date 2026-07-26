"""
Tests for 1C Exchange API: ``mode=info`` (Bitrix sale.export.1c compatibility).

Спецификация: ``_bmad-output/implementation-artifacts/dev-task-order-status-mode-info.md``.

Эти тесты покрывают сценарий, когда 1С нажимает "Загрузить с сайта" в настройках
обмена заказами модуля "1С-Битрикс. Управление сайтом" — компонент Bitrix
``sale.export.1c`` запрашивает у сайта справочник статусов и платёжных систем
через ``GET ?type=sale&mode=info``.
"""

import base64

import pytest
from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APIClient

from apps.orders.constants import STATUS_MAPPING

User = get_user_model()


@pytest.mark.django_db
@pytest.mark.integration
class Test1CInfoMode:
    """Tests for ``mode=info`` — XML-справочник статусов заказов для Bitrix."""

    def setup_method(self):
        self.client = APIClient()
        self.url = "/api/integration/1c/exchange/"
        self.test_user = User.objects.create_user(
            email="1c_info@example.com",
            password="pass123",
            first_name="1C",
            last_name="Info",
            is_staff=True,
        )

    def _auth_header(self) -> str:
        return "Basic " + base64.b64encode(b"1c_info@example.com:pass123").decode("ascii")

    def _checkauth(self) -> None:
        self.client.get(self.url, data={"mode": "checkauth"}, HTTP_AUTHORIZATION=self._auth_header())

    def _decode(self, response) -> str:
        # Bitrix-совместимый ответ — windows-1251.
        return response.content.decode("windows-1251")

    # ------------------------------------------------------------------ AC1

    def test_info_returns_200(self):
        """AC1: GET ?type=sale&mode=info возвращает 200 (а не failure)."""
        self._checkauth()

        response = self.client.get(self.url, data={"type": "sale", "mode": "info"})

        assert response.status_code == status.HTTP_200_OK
        assert b"failure" not in response.content
        assert b"Unknown mode" not in response.content

    def test_info_works_without_type_param(self):
        """``mode=info`` обрабатывается даже без параметра ``type`` (защита от вариаций 1С)."""
        self._checkauth()

        response = self.client.get(self.url, data={"mode": "info"})

        assert response.status_code == status.HTTP_200_OK
        assert b"failure" not in response.content

    # ------------------------------------------------------------------ AC2

    def test_info_xml_declaration_present(self):
        """AC2: XML declaration с правильной кодировкой."""
        self._checkauth()

        response = self.client.get(self.url, data={"type": "sale", "mode": "info"})
        body = self._decode(response)

        assert body.startswith('<?xml version="1.0" encoding="windows-1251"?>')

    def test_info_root_element_spravochnik(self):
        """AC2: корневой элемент — ``<Справочник>``."""
        self._checkauth()

        response = self.client.get(self.url, data={"type": "sale", "mode": "info"})
        body = self._decode(response)

        assert "<Справочник>" in body
        assert "</Справочник>" in body

    def test_info_statuses_block_uses_latin_c(self):
        """AC2: блок статусов открывается тегом ``<Cтатусы>`` с ЛАТИНСКОЙ "C".

        Этот нюанс взят из языкового файла Bitrix
        (``CC_BSC1_DI_STATUSES = "Cтатусы"``). Несовпадение приведёт к
        несовместимости с компонентом ``bitrix:sale.export.1c``.
        """
        self._checkauth()

        response = self.client.get(self.url, data={"type": "sale", "mode": "info"})
        body = self._decode(response)

        # Latin "C" (U+0043), а не русская "С" (U+0421).
        assert "<Cтатусы>" in body
        assert "</Cтатусы>" in body
        # Точечная проверка: первый символ после "<" в теге Cтатусы — именно
        # латинская C, ord == 0x43. Так мы ловим случайную замену на кириллицу.
        idx = body.index("<Cтатусы>") + 1
        assert ord(body[idx]) == 0x43, f"Expected latin C (0x43), got 0x{ord(body[idx]):04x}"
        # Убедимся, что в выводе нет русской "С" в начале тега статусов.
        assert "<Статусы>" not in body
        assert "</Статусы>" not in body

    def test_info_payment_systems_block_present(self):
        """AC2: пустой блок ``<ПлатежныеСистемы>`` присутствует в парной форме тега."""
        self._checkauth()

        response = self.client.get(self.url, data={"type": "sale", "mode": "info"})
        body = self._decode(response)

        assert "<ПлатежныеСистемы>" in body
        assert "</ПлатежныеСистемы>" in body

    # ------------------------------------------------------------------ AC3

    def test_info_content_type_windows_1251(self):
        """AC3: Content-Type содержит ``windows-1251``."""
        self._checkauth()

        response = self.client.get(self.url, data={"type": "sale", "mode": "info"})

        ctype = response["Content-Type"].lower()
        assert "xml" in ctype
        assert "windows-1251" in ctype

    def test_info_response_decodes_as_windows_1251(self):
        """AC3: байты ответа корректно декодируются как windows-1251."""
        self._checkauth()

        response = self.client.get(self.url, data={"type": "sale", "mode": "info"})

        body = response.content.decode("windows-1251")
        # Кириллический текст должен присутствовать без ошибок декодирования.
        assert "Справочник" in body
        assert "Элемент" in body

    # ------------------------------------------------------------------ AC4

    def test_info_contains_all_status_mapping_keys(self):
        """AC4: справочник содержит все ключи STATUS_MAPPING."""
        self._checkauth()

        response = self.client.get(self.url, data={"type": "sale", "mode": "info"})
        body = self._decode(response)

        for status_name in STATUS_MAPPING.keys():
            assert f"<Ид>{status_name}</Ид>" in body, f"Missing status Ид: {status_name}"
            assert f"<Название>{status_name}</Название>" in body, f"Missing status Название: {status_name}"

    def test_info_contains_default_export_status(self):
        """AC4: справочник содержит дефолтный статус экспорта (``Не согласован``).

        Backend отправляет это значение в реквизите ``Статус заказа`` при экспорте
        новых заказов; следовательно, 1С должна уметь сопоставить его в таблице.
        """
        self._checkauth()

        response = self.client.get(self.url, data={"type": "sale", "mode": "info"})
        body = self._decode(response)

        assert "<Ид>Не согласован</Ид>" in body
        assert "<Название>Не согласован</Название>" in body

    def test_info_contains_default_status_when_order_defaults_absent(self, settings):
        """Follow-up 1: если ORDER_DEFAULTS отсутствует или None — справочник
        всё равно содержит дефолтный экспортный статус ``Не согласован``.

        Проверяет, что handle_info использует тот же fallback, что и
        OrderExportService._get_order_defaults(), а не молчаливо пропускает статус.
        """
        self._checkauth()

        # Убираем ORDER_DEFAULTS из конфигурации
        onec_cfg = dict(getattr(settings, "ONEC_EXCHANGE", {}))
        onec_cfg.pop("ORDER_DEFAULTS", None)
        settings.ONEC_EXCHANGE = onec_cfg

        response = self.client.get(self.url, data={"type": "sale", "mode": "info"})
        body = self._decode(response)

        assert "<Ид>Не согласован</Ид>" in body
        assert "<Название>Не согласован</Название>" in body

    def test_info_contains_default_status_when_order_defaults_none(self, settings):
        """Follow-up 1: если ORDER_DEFAULTS явно None — справочник
        всё равно содержит ``Не согласован``.
        """
        self._checkauth()

        onec_cfg = dict(getattr(settings, "ONEC_EXCHANGE", {}))
        onec_cfg["ORDER_DEFAULTS"] = None
        settings.ONEC_EXCHANGE = onec_cfg

        response = self.client.get(self.url, data={"type": "sale", "mode": "info"})
        body = self._decode(response)

        assert "<Ид>Не согласован</Ид>" in body

    def test_info_status_count(self):
        """Количество элементов = STATUS_MAPPING + дефолтный экспортный статус (без дублей).

        Считаем ожидаемое значение по той же логике, что и production-код, чтобы
        тест не падал, если ``Не согласован`` когда-либо будет добавлен в
        ``STATUS_MAPPING`` или сменится дефолтный статус экспорта.
        """
        from django.conf import settings as django_settings

        self._checkauth()

        response = self.client.get(self.url, data={"type": "sale", "mode": "info"})
        body = self._decode(response)

        # Зеркало production-логики handle_info: fallback "Не согласован" всегда присутствует.
        defaults = (getattr(django_settings, "ONEC_EXCHANGE", {}).get("ORDER_DEFAULTS") or {})
        default_status = defaults.get("STATUS", "Не согласован")
        expected = len(STATUS_MAPPING) + (1 if default_status not in STATUS_MAPPING else 0)
        assert body.count("<Элемент>") == expected
        assert body.count("</Элемент>") == expected

    # ------------------------------------------------------------------ AC5

    def test_info_does_not_break_unknown_mode_failure(self):
        """AC5: неизвестный режим по-прежнему возвращает ``failure\\nUnknown mode``."""
        self._checkauth()

        response = self.client.get(self.url, data={"mode": "definitely_not_a_real_mode"})

        assert response.status_code == status.HTTP_200_OK
        assert b"failure" in response.content
        assert b"Unknown mode" in response.content

    def test_info_does_not_break_init_mode(self):
        """AC5: ``mode=init`` после реализации ``mode=info`` продолжает работать."""
        self._checkauth()

        response = self.client.get(self.url, data={"mode": "init", "type": "sale"})

        assert response.status_code == status.HTTP_200_OK
        body = response.content.decode("utf-8")
        assert "version=2.09" in body
        assert "sessid=" in body

    # ------------------------------------------------------------------ POST

    def test_info_works_via_post_request(self):
        """1С может слать info как POST — обработка должна быть симметрична GET."""
        self._checkauth()

        response = self.client.post(self.url + "?type=sale&mode=info")
        body = self._decode(response)

        assert response.status_code == status.HTTP_200_OK
        assert "<Справочник>" in body
        assert "<Cтатусы>" in body

    # ------------------------------------------------------------------ структурная валидность

    def test_info_xml_is_well_formed(self):
        """Ответ — well-formed XML (парсится без ошибок)."""
        from xml.etree import ElementTree as ET

        self._checkauth()

        response = self.client.get(self.url, data={"type": "sale", "mode": "info"})

        # ElementTree сам распарсит declaration encoding="windows-1251".
        root = ET.fromstring(response.content)

        assert root.tag == "Справочник"
        # Дочерние элементы: Cтатусы (latin C) + ПлатежныеСистемы.
        children = [child.tag for child in root]
        assert "Cтатусы" in children
        assert "ПлатежныеСистемы" in children
