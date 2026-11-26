"""
Разовый пересчёт ответственного менеджера у всех клиентов (эпик 42, стори 42.3).

Автоназначение 42.2 срабатывает на события: регистрацию, смену ИНН или
страны, правку правила региона. Клиенты, которых эти события не задели,
ответственного не получили — их добирает эта команда.

Когда запускать: на проде после распределения регионов в «Правилах
маршрутизации менеджеров», сначала с ``--dry-run``, затем без него:

    python manage.py recalculate_responsible_managers --dry-run
    python manage.py recalculate_responsible_managers

Логику назначения команда не дублирует: ответственного даёт
``resolve_responsible_for_key`` (42.2), с кэшем по ключу региона, поэтому
число запросов разрешения правил зависит от числа ключей, а не клиентов.
Чтение клиентов, блокировка их строк и запись идут пачками: эти запросы
растут с числом клиентов, по одному на пачку.

Весь прогон — одна транзакция. Первой её командой команда встаёт в общую
очередь с импортом контрагентов 1С (``acquire_bulk_clients_lock``): импорт
меняет клиентов в порядке файла, и без очереди их транзакции могли бы
захватить строки навстречу друг другу. Затем таблица правил блокируется от
изменений (``SHARE ROW EXCLUSIVE``): правку, создание и удаление правила, а
также второй запуск команды PostgreSQL заставит ждать до конца прогона.
Иначе сигнал 42.2 переназначил бы клиентов по новому правилу, а команда
записала бы поверх ответственного по старому из своего кэша.

Запись — через ``QuerySet.update()``: хук автоназначения ``User.save()`` здесь
не нужен, а ``updated_at`` не трогается, чтобы тысячи записей не выглядели
изменёнными. ``UPDATE`` повторяет всё, на чём основан расчёт: клиент не
назначен вручную, не стал сотрудником, ключ региона и прежний ответственный
те же, что при чтении. Клиент, изменившийся во время прогона, не
перезаписывается, а отчёт строится по числу реально обновлённых строк.
Прежнего ответственного ``UPDATE`` сверяет у каждого клиента своего, но
одним запросом на пачку: число запросов не зависит от того, сколько разных
менеджеров стояло у клиентов до прогона.

Перед первым ``UPDATE`` строки всех назначаемых клиентов блокируются
отдельными запросами (``SELECT … FOR UPDATE``), по возрастанию id сразу по
всем группам записи — так команда не замкнёт цикл ожидания с транзакцией,
которая тоже меняет клиентов по возрастанию id. ``UPDATE``, дождавшийся
чужой блокировки строки, перепроверяет только поля самой строки, а подзапрос
по группам сотрудников видит снимок начала ``UPDATE`` и не заметил бы только
что добавленное членство. После блокировки новый запрос видит всё
закоммиченное, а добавить
клиента в группу до конца прогона нельзя: проверка внешнего ключа
``users_groups`` ждёт эту блокировку.

Без активного резервного правила с менеджером команда не запускается:
клиенты регионов без правила остались бы без ответственного. Заблокированный
руководитель в резервном правиле ответственного не даёт (стори 42.7, решение 17)
и тоже останавливает команду.
"""

from __future__ import annotations

import logging
from collections import Counter, defaultdict
from typing import Any

from django.core.management.base import BaseCommand, CommandError, CommandParser
from django.db import connection, transaction
from django.db.models import Q

from apps.common.models import ManagerRoutingRule
from apps.common.regions import REGION_NAMES, region_name
from apps.users.models import User
from apps.users.services.bulk_clients_lock import acquire_bulk_clients_lock
from apps.users.services.responsible_manager import (
    RUSSIA_COUNTRY_VALUES,
    SOURCE_COUNTRY,
    SOURCE_FALLBACK,
    SOURCE_NONE,
    SOURCE_REGION,
    RegionKey,
    ResponsibleResolution,
    region_key,
    resolve_responsible_for_key,
)
from apps.users.staff_roles import staff_accounts_q

logger = logging.getLogger(__name__)

NO_FALLBACK_MESSAGE = (
    "Нет активного резервного правила с менеджером или руководитель резервного правила заблокирован. "
    "Назначьте активного руководителя в резервном правиле и запустите снова; для оценки — --dry-run."
)

# Конфликтует с ROW EXCLUSIVE (INSERT, UPDATE, DELETE) и с самим собой, чтение не блокирует.
LOCK_RULES_SQL = f'LOCK TABLE "{ManagerRoutingRule._meta.db_table}" IN SHARE ROW EXCLUSIVE MODE'

READ_CHUNK_SIZE = 2000
UPDATE_CHUNK_SIZE = 1000

COUNTER_BY_SOURCE = {
    SOURCE_REGION: "by_region",
    SOURCE_COUNTRY: "by_country",
    SOURCE_FALLBACK: "by_fallback",
}

# Группа записи: (новый ответственный, источник, ключ региона).
PendingGroup = tuple[int, str, RegionKey | None]
# Клиент группы: (id, прежний ответственный).
PendingClient = tuple[int, int | None]


def previous_manager_q(chunk: list[PendingClient]) -> Q:
    """Условие ``UPDATE``: у каждого клиента пачки тот же ответственный, что при чтении."""
    by_previous: defaultdict[int | None, list[int]] = defaultdict(list)
    for pk, previous_id in chunk:
        by_previous[previous_id].append(pk)
    condition = Q()
    for previous_id, ids in by_previous.items():
        condition |= Q(pk__in=ids, responsible_manager_id=previous_id)
    return condition


def region_key_q(key: RegionKey | None) -> Q:
    """Условие ``UPDATE``: ключ региона клиента тот же, что при чтении (как в ``region_key``)."""
    russian = Q(country__in=RUSSIA_COUNTRY_VALUES)
    if key is None:
        return russian & ~Q(tax_id__regex=r"^[0-9]{2}")
    if key[0] == ManagerRoutingRule.MATCH_INN_REGION:
        return russian & Q(tax_id__startswith=key[1])
    return Q(country=key[1])


class Command(BaseCommand):
    help = "Разовый пересчёт ответственного менеджера для всех клиентов по правилам регионов"

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Посчитать и вывести отчёт, ничего не меняя",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        dry_run: bool = options["dry_run"]

        with transaction.atomic():
            # Сначала очередь с импортом контрагентов, затем правила (см. docstring модуля).
            acquire_bulk_clients_lock()
            # Блокировка правил — до первого их чтения и до конца записи.
            with connection.cursor() as cursor:
                cursor.execute(LOCK_RULES_SQL)

            # Проверка резерва — до чтения клиентов, чтобы ничего не обнулить.
            fallback = resolve_responsible_for_key(None)
            if fallback.source == SOURCE_NONE and not dry_run:
                raise CommandError(NO_FALLBACK_MESSAGE)

            counters, fallback_codes, pending = self._collect(fallback)
            if not dry_run:
                self._apply(pending, counters, fallback_codes)

        self._write_report(counters, fallback_codes, dry_run)
        if fallback.source == SOURCE_NONE:
            self.stderr.write(self.style.WARNING(NO_FALLBACK_MESSAGE))

        logger.info(
            "Responsible managers recalculated",
            extra={"action": "responsible_manager_recalculate", "dry_run": dry_run, **counters},
        )

    def _collect(
        self, fallback: ResponsibleResolution
    ) -> tuple[dict[str, int], Counter[str], defaultdict[PendingGroup, list[PendingClient]]]:
        """Прочитать клиентов и рассчитать, кому какого ответственного назначить."""
        counters = dict.fromkeys(
            ("checked", "by_region", "by_country", "by_fallback", "manual", "unchanged", "no_manager", "changed"), 0
        )
        fallback_codes: Counter[str] = Counter()
        pending: defaultdict[PendingGroup, list[PendingClient]] = defaultdict(list)
        cache: dict[RegionKey | None, ResponsibleResolution] = {None: fallback}

        clients = (
            User.objects.exclude(staff_accounts_q())
            .only("id", "country", "tax_id", "responsible_manager", "responsible_manager_manual")
            .order_by("pk")
            .iterator(chunk_size=READ_CHUNK_SIZE)
        )
        for client in clients:
            counters["checked"] += 1
            if client.responsible_manager_manual:
                counters["manual"] += 1
                continue

            key = region_key(client.country, client.tax_id)
            if key not in cache:
                cache[key] = resolve_responsible_for_key(key)
            resolution = cache[key]

            # manager пуст ровно тогда, когда source == SOURCE_NONE: резерва с менеджером нет.
            if resolution.manager is None:
                counters["no_manager"] += 1
                continue

            if (
                resolution.source == SOURCE_FALLBACK
                and key is not None
                and key[0] == ManagerRoutingRule.MATCH_INN_REGION
            ):
                fallback_codes[key[1]] += 1

            target_id = resolution.manager.pk
            if client.responsible_manager_id == target_id:
                counters["unchanged"] += 1
                continue
            counters[COUNTER_BY_SOURCE[resolution.source]] += 1
            pending[(target_id, resolution.source, key)].append((client.pk, client.responsible_manager_id))
        return counters, fallback_codes, pending

    def _apply(
        self,
        pending: defaultdict[PendingGroup, list[PendingClient]],
        counters: dict[str, int],
        fallback_codes: Counter[str],
    ) -> None:
        """
        Записать назначения и поправить счётчики по реально обновлённым строкам.

        Строка не обновляется, если с момента чтения клиент назначен вручную,
        стал сотрудником (в том числе через группу) или у него сменились ключ
        региона или ответственный — например, после смены ИНН хук 42.2 уже
        назначил нового. Такие клиенты переносятся из «Назначено …» в
        «Пропущено»: сумма счётчиков по-прежнему равна числу проверенных.
        """
        self._lock_clients(pending)
        for (target_id, source, key), clients in pending.items():
            for start in range(0, len(clients), UPDATE_CHUNK_SIZE):
                chunk = clients[start : start + UPDATE_CHUNK_SIZE]
                ids = [pk for pk, _previous_id in chunk]
                updated = (
                    User.objects.filter(region_key_q(key), previous_manager_q(chunk), responsible_manager_manual=False)
                    .exclude(staff_accounts_q())
                    .update(responsible_manager_id=target_id)
                )
                skipped = len(chunk) - updated
                if not skipped:
                    continue
                manual = User.objects.filter(pk__in=ids, responsible_manager_manual=True).count()
                counters[COUNTER_BY_SOURCE[source]] -= skipped
                counters["manual"] += manual
                counters["changed"] += skipped - manual
                if source == SOURCE_FALLBACK and key is not None and key[0] == ManagerRoutingRule.MATCH_INN_REGION:
                    fallback_codes[key[1]] -= skipped
                    if fallback_codes[key[1]] <= 0:
                        del fallback_codes[key[1]]

    @staticmethod
    def _lock_clients(pending: defaultdict[PendingGroup, list[PendingClient]]) -> None:
        """
        Заблокировать строки всех клиентов к записи — до первого ``UPDATE``, по возрастанию id.

        Отдельный запрос: ``UPDATE`` после него получит снимок с уже
        закоммиченным членством в группах (см. docstring модуля). Порядок —
        общий для всех групп записи: при захвате по группам команда держала
        бы строку с большим id, ожидая строку с меньшим, и транзакция,
        которая меняет клиентов по возрастанию id, замкнула бы с ней цикл
        ожидания. Импорт контрагентов 1С идёт в порядке файла, поэтому с ним
        команда не пересекается вовсе: их разводит ``acquire_bulk_clients_lock``.
        """
        ids = sorted(pk for clients in pending.values() for pk, _previous_id in clients)
        for start in range(0, len(ids), UPDATE_CHUNK_SIZE):
            chunk = ids[start : start + UPDATE_CHUNK_SIZE]
            list(User.objects.filter(pk__in=chunk).order_by("pk").select_for_update().values_list("pk", flat=True))

    def _write_report(self, counters: dict[str, int], fallback_codes: Counter[str], dry_run: bool) -> None:
        title = "Пересчёт ответственных менеджеров"
        if dry_run:
            title += " (пробный запуск, изменения не сохранены)"
        lines = [
            title,
            f"Проверено клиентов: {counters['checked']}",
            f"Назначено по коду региона: {counters['by_region']}",
            f"Назначено по стране: {counters['by_country']}",
            f"Ушло на резервное правило: {counters['by_fallback']}",
            f"Пропущено (назначен вручную): {counters['manual']}",
            f"Без изменений: {counters['unchanged']}",
        ]
        if counters["changed"]:
            lines.append(f"Пропущено (изменились во время пересчёта): {counters['changed']}")
        if counters["no_manager"]:
            lines.append(f"Без ответственного (нет резервного правила с менеджером): {counters['no_manager']}")
        if fallback_codes:
            lines.append("Коды без менеджера, клиенты ушли на резерв:")
            for code, count in sorted(fallback_codes.items(), key=lambda item: (-item[1], item[0])):
                label = f"{code} — {region_name(code)}" if code in REGION_NAMES else code
                lines.append(f"  {label}: {count}")
        for line in lines:
            self.stdout.write(line)
