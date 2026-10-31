"""
Integration-тесты инструкций сотрудников `/manager/instructions/`.

Покрывает:
- доступ: менеджер и руководитель пускаются; маркетинг, сотрудник без группы,
  суперпользователь и аноним уходят на страницу входа раздела;
- список и страница каждой инструкции из реестра, 404 на неизвестный адрес;
- переходы: блок «Инструкции» на главной раздела, «Другие инструкции» на странице,
  ссылка со страницы подтверждения заявки (только в разделе менеджера);
- картинки инструкций найдены статикой: в проде `CompressedManifestStaticFilesStorage`
  без файла в manifest отдал бы 500.

Тесты транзакционные (autouse `clear_db_before_test` в `tests/conftest.py`).
"""

from __future__ import annotations

import re

import pytest
from django.conf import settings
from django.contrib.staticfiles import finders
from django.test import Client

from apps.users.models import User
from apps.users.staff_instructions import STAFF_INSTRUCTIONS, StaffInstruction
from apps.users.staff_roles import MANAGERS_GROUP, MARKETING_GROUP, SUPERVISORS_GROUP
from freesport import admin_site
from tests.integration.test_manager_clients_section import (  # noqa: F401 — фикстуры подключаются импортом
    PASSWORD,
    get_unique_suffix,
    make_client,
    make_staff_member,
    manager,
    manager_client,
    no_routing_rules,
    role_groups,
    verified_email_task,
)

pytestmark = [pytest.mark.integration, pytest.mark.django_db]

INDEX_URL = "/manager/"
INSTRUCTIONS_URL = "/manager/instructions/"
LOGIN_URL = "/manager/login/"
VERIFY_CLIENT_URL = f"{INSTRUCTIONS_URL}verify-client/"
IMAGE_SRC = re.compile(r'<img[^>]+src="([^"]+)"')


def logged_in(user: User) -> Client:
    browser = Client()
    browser.force_login(user)
    return browser


def get_html(browser: Client, url: str) -> str:
    response = browser.get(url)
    assert response.status_code == 200, url
    return response.content.decode()


class TestAccess:
    @pytest.mark.parametrize("url", [INSTRUCTIONS_URL, VERIFY_CLIENT_URL])
    @pytest.mark.parametrize("group_name", [MANAGERS_GROUP, SUPERVISORS_GROUP])
    def test_manager_and_supervisor_are_let_in(self, group_name, url):
        browser = logged_in(make_staff_member(group_name))

        assert browser.get(url).status_code == 200

    @pytest.mark.parametrize("url", [INSTRUCTIONS_URL, VERIFY_CLIENT_URL])
    @pytest.mark.parametrize(
        "who",
        ["marketing", "no_group", "superuser", "inactive_manager", "anonymous"],
    )
    def test_others_go_to_section_login(self, who, url):
        browser = Client()
        if who == "marketing":
            browser.force_login(make_staff_member(MARKETING_GROUP))
        elif who == "no_group":
            browser.force_login(make_staff_member(None))
        elif who == "superuser":
            browser.force_login(
                User.objects.create_superuser(email=f"su_{get_unique_suffix()}@example.com", password=PASSWORD)
            )
        elif who == "inactive_manager":
            browser.force_login(make_staff_member(MANAGERS_GROUP, is_active=False))

        response = browser.get(url)

        assert response.status_code == 302
        assert response["Location"].startswith(LOGIN_URL)


class TestPages:
    def test_list_links_every_instruction(self, manager_client):
        html = get_html(manager_client, INSTRUCTIONS_URL)

        assert STAFF_INSTRUCTIONS
        for instruction in STAFF_INSTRUCTIONS:
            assert f'href="{INSTRUCTIONS_URL}{instruction.slug}/"' in html
            assert instruction.title in html

    @pytest.mark.parametrize("instruction", STAFF_INSTRUCTIONS, ids=lambda item: item.slug)
    def test_every_registered_instruction_renders(self, manager_client, instruction):
        html = get_html(manager_client, f"{INSTRUCTIONS_URL}{instruction.slug}/")

        assert f"<h1>{instruction.title}</h1>" in html
        assert 'id="instruction-body"' in html
        # Возврат к списку — и в хлебных крошках, и в блоке переходов.
        assert html.count(f'href="{INSTRUCTIONS_URL}"') >= 2

    def test_page_lists_other_instructions_but_not_itself(self, manager_client, monkeypatch):
        extra = StaffInstruction(
            slug="second",
            title="Вторая инструкция",
            summary="Описание второй",
            template="admin/instructions/verify_client.html",
        )
        monkeypatch.setattr(admin_site, "STAFF_INSTRUCTIONS", (*STAFF_INSTRUCTIONS, extra))

        html = get_html(manager_client, VERIFY_CLIENT_URL)

        links = re.search(r'id="instruction-links".*?</table>', html, re.S)
        assert links is not None
        assert f'href="{INSTRUCTIONS_URL}second/"' in links.group(0)
        assert f'href="{VERIFY_CLIENT_URL}"' not in links.group(0)

    @pytest.mark.parametrize("slug", ["unknown", "verify-client-2", "VERIFY"])
    def test_unknown_slug_is_404(self, manager_client, slug):
        assert manager_client.get(f"{INSTRUCTIONS_URL}{slug}/").status_code == 404

    def test_page_without_trailing_slash_redirects(self, manager_client):
        response = manager_client.get("/manager/instructions/verify-client")

        assert response.status_code == 301
        assert response["Location"] == VERIFY_CLIENT_URL


class TestStaticImages:
    @pytest.mark.parametrize("instruction", STAFF_INSTRUCTIONS, ids=lambda item: item.slug)
    def test_images_are_found_by_staticfiles(self, manager_client, instruction):
        html = get_html(manager_client, f"{INSTRUCTIONS_URL}{instruction.slug}/")

        sources = IMAGE_SRC.findall(html)
        for source in sources:
            assert source.startswith(settings.STATIC_URL), source
            relative = source[len(settings.STATIC_URL) :]
            assert finders.find(relative), f"картинка {relative} не найдена статикой"

    def test_verify_instruction_has_both_screenshots(self, manager_client):
        sources = IMAGE_SRC.findall(get_html(manager_client, VERIFY_CLIENT_URL))

        assert len(sources) == 2


class TestNavigationLinks:
    def test_manager_index_has_instructions_block(self, manager_client):
        html = get_html(manager_client, INDEX_URL)

        block = re.search(r'id="manager-instructions".*?</table>', html, re.S)
        assert block is not None
        assert f'href="{INSTRUCTIONS_URL}"' in block.group(0)
        assert f'href="{VERIFY_CLIENT_URL}"' in block.group(0)

    def test_supervisor_index_has_instructions_block(self):
        html = get_html(logged_in(make_staff_member(SUPERVISORS_GROUP)), INDEX_URL)

        assert 'id="manager-instructions"' in html

    def test_verify_page_links_to_instruction(self, manager_client, manager):
        applicant = make_client(
            manager, verification_status="pending", is_verified=False, is_active=False, tax_id="5099999999"
        )

        html = get_html(manager_client, f"/manager/users/user/{applicant.pk}/verify/")

        assert f'href="{VERIFY_CLIENT_URL}"' in html
        assert "Инструкция: как подтвердить заявку" in html

    def test_admin_verify_page_has_no_instruction_link(self, client):
        # В /admin/ (суперпользователь) инструкций нет: ссылка вела бы в закрытый раздел.
        superuser = User.objects.create_superuser(email=f"su_{get_unique_suffix()}@example.com", password=PASSWORD)
        applicant = make_client(None, verification_status="pending", is_verified=False, is_active=False)
        client.force_login(superuser)

        html = get_html(client, f"/admin/users/user/{applicant.pk}/verify/")

        assert "Инструкция: как подтвердить заявку" not in html
