"""
Имена групп ролей сотрудников и критерий «сотрудник» (эпик 42).

Три роли — «Менеджеры», «Маркетинг», «Руководители» — это группы Django.
Их создаёт data-миграция `users/0023_staff_role_groups`, и наборы прав
каждой группы зафиксированы в ней (миграция хранит свою замороженную копию
имён и прав). Здесь — имена, на которые опирается код приложения, и
критерий «сотрудник», по которому учётные записи исключаются из
автоназначения ответственного менеджера.

Модуль импортируют `users/models.py` и `common/models.py`, поэтому модели
здесь импортируются только внутри функций — иначе цикл импорта.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import TYPE_CHECKING, Any, cast

from django.core.exceptions import ValidationError
from django.db.models import Exists, OuterRef, Q, QuerySet
from django.db.models.functions import Lower
from django.forms import Field, ModelChoiceField
from django.http import HttpRequest

if TYPE_CHECKING:
    from apps.users.models import User

MANAGERS_GROUP = "Менеджеры"
MARKETING_GROUP = "Маркетинг"
SUPERVISORS_GROUP = "Руководители"

STAFF_ROLE_GROUPS = (MANAGERS_GROUP, MARKETING_GROUP, SUPERVISORS_GROUP)


# Учётные записи, которые не бывают клиентами: им не назначается
# ответственный, и их не трогает пересчёт по правилам регионов.
# role="admin" — ради робота обмена 1С: у него is_staff=False, а без этого
# условия он получил бы ответственного из резервного правила.
def staff_accounts_q() -> Q:
    return Q(is_staff=True) | Q(is_superuser=True) | Q(role="admin") | Q(groups__name__in=STAFF_ROLE_GROUPS)


# Кого можно выбрать ответственным менеджером и менеджером правила региона.
RESPONSIBLE_MANAGER_CHOICES = Q(
    is_staff=True,
    is_superuser=False,
    groups__name__in=(MANAGERS_GROUP, SUPERVISORS_GROUP),
)


def is_supervisor(request: HttpRequest) -> bool:
    """
    Сотрудник запроса — руководитель (стори 42.7): состоит в группе «Руководители».

    Сотрудник в двух группах («Менеджеры» и «Руководители») — руководитель.
    `is_superuser` не проверяется: суперпользователь в разделы не входит.
    Членство читается из БД один раз за запрос — функцию зовут выборки,
    колонки и формы раздела.
    """
    cached = getattr(request, "_is_supervisor", None)
    if cached is None:
        user = request.user
        cached = bool(user.is_authenticated and user.groups.filter(name=SUPERVISORS_GROUP).exists())
        request._is_supervisor = cached  # type: ignore[attr-defined]
    return bool(cached)


def _in_groups(names: tuple[str, ...]) -> Exists:
    """Сотрудник состоит хотя бы в одной из групп — подзапросом, без JOIN и дублей строк."""
    from apps.users.models import User

    return Exists(User.groups.through._default_manager.filter(user_id=OuterRef("pk"), group__name__in=names))


def responsible_manager_candidate_q() -> Q:
    """
    Кого можно выбрать ответственным менеджером и менеджером правила (стори 42.7).

    Строже `RESPONSIBLE_MANAGER_CHOICES`: только активный сотрудник. Членство —
    через `Exists`: JOIN по `groups` дал бы сотруднику в двух группах две строки,
    а `ModelChoiceField.to_python` на `.get()` — `MultipleObjectsReturned`.
    """
    return Q(is_active=True, is_staff=True, is_superuser=False) & Q(_in_groups((MANAGERS_GROUP, SUPERVISORS_GROUP)))


def responsible_manager_candidates() -> QuerySet[User]:
    from apps.users.models import User

    return User.objects.filter(responsible_manager_candidate_q())


def split_by_manager_section(emails: Iterable[str]) -> tuple[list[str], list[str]]:
    """
    Делит адреса писем на `(для /admin/, для /manager/)` — по тому, куда пустят получателя.

    В раздел менеджера входит ровно тот, кого можно назначить ответственным
    (`responsible_manager_candidate_q`, см. `ManagerAdminSite`): менеджер или
    руководитель. `/admin/` их не пускает, поэтому ссылка из письма должна вести
    в `/manager/`. Остальные адреса — суперпользователь или адрес без учётной
    записи — получают ссылку в `/admin/`, как раньше. Email сравнивается без
    учёта регистра, порядок адресов сохраняется.
    """
    from apps.users.models import User

    emails = list(emails)
    section = {
        email.lower()
        for email in User.objects.filter(responsible_manager_candidate_q())
        .annotate(email_lower=Lower("email"))
        .filter(email_lower__in=[email.lower() for email in emails])
        .values_list("email_lower", flat=True)
    }
    admin = [email for email in emails if email.lower() not in section]
    manager = [email for email in emails if email.lower() in section]
    return admin, manager


def manager_label(user: User) -> str:
    """Подпись менеджера в выборе: «ФИО (email)»."""
    name = user.full_name
    return f"{name} ({user.email})" if name else str(user.email or f"ID {user.pk}")


def validate_manager_candidate(value: User | None) -> None:
    """Ошибка поля, если выбранный менеджер больше не может отвечать за клиентов."""
    if value is None or responsible_manager_candidates().filter(pk=value.pk).exists():
        return
    raise ValidationError(
        f"«{value.email}» больше не может быть ответственным менеджером: учётная запись заблокирована "
        "или выведена из групп «Менеджеры» и «Руководители». Выберите другого менеджера."
    )


def limit_manager_field(form_field: Field, current_id: Any) -> None:
    """
    Выбор менеджера в форме: только допустимые, без дублей, текущий не теряется.

    Текущее значение остаётся в queryset, даже если менеджер заблокирован или
    выведен из групп: форма показывает его выбранным, а сохранить с ним нельзя —
    `validate_manager_candidate` требует выбрать другого. `limit_choices_to`
    поля сбрасывается: иначе `BaseModelForm.__init__` снова отфильтровал бы
    queryset по `RESPONSIBLE_MANAGER_CHOICES` модели и убрал текущее значение.
    Один `filter`, не `union()`: `ModelChoiceField.to_python` фильтрует queryset по pk.
    """
    from apps.users.models import User

    field = cast(ModelChoiceField, form_field)
    condition = responsible_manager_candidate_q()
    if current_id is not None:
        condition |= Q(pk=current_id)
    field.queryset = User.objects.filter(condition).order_by("last_name", "first_name", "email")
    field.limit_choices_to = None
    field.label_from_instance = manager_label  # type: ignore[assignment]
    if validate_manager_candidate not in field.validators:
        field.validators.append(validate_manager_candidate)
