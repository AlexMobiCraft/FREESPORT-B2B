"""
Имена групп ролей сотрудников и критерий «сотрудник» (эпик 42).

Три роли — «Менеджеры», «Маркетинг», «Руководители» — это группы Django.
Их создаёт data-миграция `users/0023_staff_role_groups`, и наборы прав
каждой группы зафиксированы в ней (миграция хранит свою замороженную копию
имён и прав). Здесь — имена, на которые опирается код приложения, и
критерий «сотрудник», по которому учётные записи исключаются из
автоназначения ответственного менеджера.
"""

from django.db.models import Q

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
