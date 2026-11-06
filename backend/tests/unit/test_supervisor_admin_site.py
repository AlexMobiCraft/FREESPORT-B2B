"""
Unit-тесты раздела руководителя `/supervisor/` (стори 42.7): доступ к сайту,
признак руководителя, состав регистрации, выбор менеджера в формах,
управляемые сотрудники, резервное правило и заблокированный менеджер в
правилах регионов.
"""

from __future__ import annotations

import importlib
from types import SimpleNamespace

import pytest
from django import forms
from django.apps import apps as django_apps
from django.contrib import admin
from django.contrib.auth.models import AnonymousUser, Group, Permission
from django.core.exceptions import ValidationError
from django.db import connection
from django.test import RequestFactory

from apps.bonuses.admin import BonusProgramSettingsAdmin, BonusTransactionAdmin
from apps.bonuses.models import BonusProgramSettings, BonusTransaction
from apps.common.admin import ManagerRoutingRuleAdmin, NotificationRecipientAdmin
from apps.common.models import ManagerRoutingRule, NotificationRecipient
from apps.users.admin import UserAdmin
from apps.users.models import User
from apps.users.services.region_routing import resolve_manager_recipients
from apps.users.services.responsible_manager import SOURCE_FALLBACK, resolve_responsible_for_key
from apps.users.staff_roles import (
    MANAGERS_GROUP,
    MARKETING_GROUP,
    SUPERVISORS_GROUP,
    is_supervisor,
    limit_manager_field,
    responsible_manager_candidates,
)
from apps.users.supervisor_admin import manageable_staff_q
from freesport.admin_site import supervisor_site
from tests.conftest import get_unique_suffix

pytestmark = [pytest.mark.unit, pytest.mark.django_db]

PASSWORD = "StrongPassword123!"
FALLBACK = ManagerRoutingRule.MATCH_FALLBACK
INN_REGION = ManagerRoutingRule.MATCH_INN_REGION

_migration = importlib.import_module("apps.users.migrations.0023_staff_role_groups")


@pytest.fixture(autouse=True)
def role_groups():
    _migration.create_staff_role_groups(django_apps, SimpleNamespace(connection=connection))


@pytest.fixture(autouse=True)
def no_routing_rules():
    ManagerRoutingRule.objects.all().delete()


def make_user(*group_names: str, **extra) -> User:
    user = User.objects.create_user(email=f"u_{get_unique_suffix()}@example.com", password=PASSWORD, **extra)
    for name in group_names:
        user.groups.add(Group.objects.get(name=name))
    return User.objects.get(pk=user.pk)


def make_staff(*group_names: str, **extra) -> User:
    return make_user(*group_names, is_staff=True, **extra)


def request_for(user, path: str = "/supervisor/"):
    request = RequestFactory().get(path)
    request.user = user
    return request


class TestHasPermission:
    @pytest.mark.parametrize(
        "group_names, extra, expected",
        [
            ((SUPERVISORS_GROUP,), {"is_staff": True}, True),
            ((MANAGERS_GROUP, SUPERVISORS_GROUP), {"is_staff": True}, True),
            ((MANAGERS_GROUP,), {"is_staff": True}, False),
            ((MARKETING_GROUP,), {"is_staff": True}, False),
            ((), {"is_staff": True}, False),
            ((SUPERVISORS_GROUP,), {"is_staff": False}, False),
            ((SUPERVISORS_GROUP,), {"is_staff": True, "is_active": False}, False),
            ((SUPERVISORS_GROUP,), {"is_staff": True, "is_superuser": True}, False),
            ((), {"is_staff": True, "is_superuser": True}, False),
        ],
    )
    def test_matrix(self, group_names, extra, expected):
        user = make_user(*group_names, **extra)
        assert supervisor_site.has_permission(request_for(user)) is expected

    def test_anonymous(self):
        assert supervisor_site.has_permission(request_for(AnonymousUser())) is False

    def test_titles(self):
        assert supervisor_site.site_header == "OPTISPORT — Руководитель"
        assert supervisor_site.site_title == "OPTISPORT — Руководитель"
        assert supervisor_site.index_title == "Раздел руководителя"
        assert supervisor_site.section_groups == ("Руководители",)


class TestIsSupervisor:
    def test_cached_on_request(self, django_assert_num_queries):
        request = request_for(make_staff(SUPERVISORS_GROUP))

        with django_assert_num_queries(1):
            assert is_supervisor(request) is True
            assert is_supervisor(request) is True

    def test_member_of_two_groups_is_supervisor(self):
        assert is_supervisor(request_for(make_staff(MANAGERS_GROUP, SUPERVISORS_GROUP))) is True

    @pytest.mark.parametrize("groups", [(MANAGERS_GROUP,), (MARKETING_GROUP,), ()])
    def test_others_are_not(self, groups):
        assert is_supervisor(request_for(make_staff(*groups))) is False

    def test_anonymous_is_not(self, django_assert_num_queries):
        with django_assert_num_queries(0):
            assert is_supervisor(request_for(AnonymousUser())) is False


class TestRegistry:
    def test_supervisor_site_has_exactly_five_models(self):
        assert {model._meta.label for model in supervisor_site._registry} == {
            "users.User",
            "common.ManagerRoutingRule",
            "common.NotificationRecipient",
            "bonuses.BonusProgramSettings",
            "bonuses.BonusTransaction",
        }

    def test_main_admin_keeps_parent_classes(self):
        assert type(admin.site._registry[User]) is UserAdmin
        assert type(admin.site._registry[ManagerRoutingRule]) is ManagerRoutingRuleAdmin
        assert type(admin.site._registry[NotificationRecipient]) is NotificationRecipientAdmin
        assert type(admin.site._registry[BonusProgramSettings]) is BonusProgramSettingsAdmin
        assert type(admin.site._registry[BonusTransaction]) is BonusTransactionAdmin

    def test_no_view_on_site_in_section(self):
        for model, model_admin in supervisor_site._registry.items():
            assert model_admin.view_on_site is False, model

    @pytest.mark.parametrize("action", ["block_staff", "unblock_staff"])
    def test_staff_actions_require_change(self, action):
        model_admin = supervisor_site._registry[User]
        assert tuple(getattr(model_admin, action).allowed_permissions) == ("change",)

    def test_staff_card_whitelist_has_no_privileges(self):
        model_admin = supervisor_site._registry[User]
        request = request_for(make_staff(SUPERVISORS_GROUP))
        member = make_staff(MANAGERS_GROUP)

        for obj in (None, member):
            fields = {name for _, options in model_admin.get_fieldsets(request, obj) for name in options["fields"]}
            form_fields = set(model_admin.get_form(request, obj).base_fields)
            for hidden in (*UserAdmin.PRIVILEGE_FIELDS, "role", "responsible_manager"):
                assert hidden not in fields, (obj, hidden)
                assert hidden not in form_fields, (obj, hidden)


class TestResponsibleManagerCandidates:
    def test_only_active_managers_and_supervisors_once(self):
        manager = make_staff(MANAGERS_GROUP)
        supervisor = make_staff(SUPERVISORS_GROUP)
        both = make_staff(MANAGERS_GROUP, SUPERVISORS_GROUP)
        make_staff(MANAGERS_GROUP, is_active=False)
        make_staff(MARKETING_GROUP)
        make_staff()
        make_user(MANAGERS_GROUP)  # без is_staff
        make_staff(SUPERVISORS_GROUP, is_superuser=True)
        make_user()  # клиент

        pks = list(responsible_manager_candidates().values_list("pk", flat=True))

        assert sorted(pks) == sorted([manager.pk, supervisor.pk, both.pk])

    def test_current_former_manager_stays_selected(self):
        manager = make_staff(MANAGERS_GROUP)
        both = make_staff(MANAGERS_GROUP, SUPERVISORS_GROUP)
        former = make_staff(MARKETING_GROUP, first_name="Бывший", last_name="Менеджер")
        # ModelForm: её __init__ применяет limit_choices_to поля модели.
        form_class = forms.modelform_factory(User, fields=["responsible_manager"])
        field = form_class.base_fields["responsible_manager"]

        limit_manager_field(field, former.pk)
        rendered_choices = [value for value, _ in form_class().fields["responsible_manager"].choices if value]

        assert sorted(int(str(value)) for value in rendered_choices) == sorted([manager.pk, both.pk, former.pk])
        assert field.label_from_instance(former) == f"Бывший Менеджер ({former.email})"
        with pytest.raises(ValidationError) as error:
            field.clean(str(former.pk))
        assert error.value.messages == [
            f"«{former.email}» больше не может быть ответственным менеджером: учётная запись заблокирована "
            "или выведена из групп «Менеджеры» и «Руководители». Выберите другого менеджера."
        ]
        assert field.clean(str(both.pk)) == both


class TestManageableStaff:
    def manageable(self, user: User) -> bool:
        return User.objects.filter(pk=user.pk).filter(manageable_staff_q()).exists()

    def test_role_members_are_manageable(self):
        assert self.manageable(make_staff(MANAGERS_GROUP))
        assert self.manageable(make_staff(MARKETING_GROUP))
        assert self.manageable(make_staff(MANAGERS_GROUP, MARKETING_GROUP))
        assert self.manageable(make_staff())

    def test_supervisor_is_not(self):
        assert not self.manageable(make_staff(SUPERVISORS_GROUP))
        assert not self.manageable(make_staff(MANAGERS_GROUP, SUPERVISORS_GROUP))

    def test_direct_permission_is_not(self):
        member = make_staff(MANAGERS_GROUP)
        member.user_permissions.add(Permission.objects.get(codename="view_user"))
        assert not self.manageable(member)

    def test_foreign_group_is_not(self):
        member = make_staff(MANAGERS_GROUP)
        member.groups.add(Group.objects.create(name=f"Склад {get_unique_suffix()}"))
        assert not self.manageable(member)


class TestFallbackRuleRequiresSupervisor:
    MESSAGE = "Резервное правило назначает клиентов руководителю — выберите сотрудника из группы «Руководители»."

    def test_manager_is_rejected(self):
        rule = ManagerRoutingRule(match_type=FALLBACK, match_value="default", manager=make_staff(MANAGERS_GROUP))

        with pytest.raises(ValidationError) as error:
            rule.full_clean()

        assert error.value.message_dict["manager"] == [self.MESSAGE]

    def test_supervisor_is_accepted(self):
        rule = ManagerRoutingRule(match_type=FALLBACK, match_value="default", manager=make_staff(SUPERVISORS_GROUP))
        rule.full_clean()

    def test_regional_rule_takes_manager(self):
        rule = ManagerRoutingRule(match_type=INN_REGION, match_value="23", manager=make_staff(MANAGERS_GROUP))
        rule.full_clean()

    def test_excluded_manager_is_not_checked(self):
        """Строка list_editable без поля manager не падает ошибкой чужого поля."""
        manager = make_staff(MANAGERS_GROUP)
        rule = ManagerRoutingRule.objects.create(match_type=FALLBACK, match_value="default", manager=manager)
        rule.full_clean(exclude=["manager"])


class TestBlockedManagerInRules:
    def test_resolver_skips_blocked_manager(self):
        manager = make_staff(MANAGERS_GROUP)
        chief = make_staff(SUPERVISORS_GROUP)
        ManagerRoutingRule.objects.create(match_type=INN_REGION, match_value="23", manager=manager)
        ManagerRoutingRule.objects.create(match_type=FALLBACK, match_value="default", manager=chief)
        User.objects.filter(pk=manager.pk).update(is_active=False)

        resolution = resolve_responsible_for_key((INN_REGION, "23"))

        assert resolution.manager == chief
        assert resolution.source == SOURCE_FALLBACK

    def test_blocked_fallback_gives_nobody(self):
        chief = make_staff(SUPERVISORS_GROUP, is_active=False)
        ManagerRoutingRule.objects.create(match_type=FALLBACK, match_value="default", manager=chief)

        assert resolve_responsible_for_key(None).manager is None

    def test_email_goes_to_fallback(self):
        manager = make_staff(MANAGERS_GROUP, is_active=False)
        ManagerRoutingRule.objects.create(
            match_type=INN_REGION, match_value="23", manager=manager, manager_email="region23@example.com"
        )
        ManagerRoutingRule.objects.create(match_type=FALLBACK, match_value="default", manager_email="fb@example.com")

        assert resolve_manager_recipients("Россия", "2300000000") == ["fb@example.com"]

    def test_rule_without_account_keeps_email(self):
        ManagerRoutingRule.objects.create(match_type=INN_REGION, match_value="23", manager_email="region23@example.com")

        assert resolve_manager_recipients("Россия", "2300000000") == ["region23@example.com"]
