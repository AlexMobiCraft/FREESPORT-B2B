"""
Своя БД Redis на воркер pytest-xdist (`freesport/settings/test.py`, R42.4-18).

Autouse-фикстура `clear_db_before_test` перед каждым тестом зовёт
`cache.clear()`, то есть FLUSHDB. Если два воркера параллельного прогона
окажутся в одной БД Redis, очистка одного посреди теста другого удалит ему
кэш и локи импорта 1С. Обязательный CI-прогон последовательный и такую
поломку настроек не увидит, поэтому тест поднимает настройки двух воркеров
в отдельных процессах — так же, как их получает xdist.

Пробе нужны две БД, которых не занимает ни один воркер текущего прогона
(R42.4-19): очистка с занятой базой стёрла бы данные живого воркера.
Занятые базы — с базовой из `REDIS_URL` по `PYTEST_XDIST_WORKER_COUNT` штук.
При базовой 1 и `-n 15` свободна одна БД 0 — проба пропускается. Счёт верен,
пока упавший воркер не заменяется: замена получила бы номер за этим диапазоном
(R42.4-26), поэтому `backend/conftest.py` замену выключает.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from urllib.parse import urlsplit, urlunsplit

import pytest
from django.conf import settings

import conftest as root_conftest

# Redis по умолчанию держит 16 БД, тестовый compose и CI этого не меняют.
REDIS_DATABASES = 16
KEY = "xdist-isolation-probe"

# Дочерний процесс: настройки freesport.settings.test, шаги из argv —
# `set=<значение>`, `get`, `clear`. Печатает LOCATION кэша и прочитанное.
CHILD = """
import json, sys
import django

django.setup()
from django.conf import settings
from django.core.cache import cache

key, steps = sys.argv[1], sys.argv[2:]
result = {"location": settings.CACHES["default"]["LOCATION"], "got": []}
for step in steps:
    if step.startswith("set="):
        cache.set(key, step[len("set="):], timeout=300)
    elif step == "get":
        result["got"].append(cache.get(key))
    elif step == "clear":
        cache.clear()
print(json.dumps(result))
"""


def redis_db(location: str) -> int:
    return int(urlsplit(location).path.lstrip("/") or 0)


def worker_index(worker: str) -> int:
    return int(worker[2:]) if worker.startswith("gw") else 0


def active_dbs() -> range:
    """БД Redis, которые занимают воркеры текущего прогона (без xdist — одна)."""
    base = redis_db(settings.CACHES["default"]["LOCATION"]) - worker_index(os.environ.get("PYTEST_XDIST_WORKER", ""))
    return range(base, base + int(os.environ.get("PYTEST_XDIST_WORKER_COUNT", "1")))


def probe_dbs(active: range) -> tuple[int, int] | None:
    """Две старшие БД вне `active`; None, если свободных меньше двух."""
    free = [db for db in range(REDIS_DATABASES) if db not in active]
    return (free[-2], free[-1]) if len(free) >= 2 else None


def run_worker(base_db: int, worker: str, *steps: str) -> dict[str, Any]:
    """Шаги с кэшем в отдельном процессе: базовая БД `base_db`, воркер `worker`."""
    redis_url = urlsplit(os.environ.get("REDIS_URL") or settings.CACHES["default"]["LOCATION"])
    env = {
        **os.environ,
        "DJANGO_SETTINGS_MODULE": "freesport.settings.test",
        "PYTEST_XDIST_WORKER": worker,
        "REDIS_URL": urlunsplit(redis_url._replace(path=f"/{base_db}")),
    }
    completed = subprocess.run(
        [sys.executable, "-c", CHILD, KEY, *steps],
        cwd=Path(settings.BASE_DIR),
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert completed.returncode == 0, f"воркер {worker} упал:\n{completed.stderr}"
    return json.loads(completed.stdout.strip().splitlines()[-1])


@pytest.mark.parametrize(
    "worker, count, location, expected",
    [
        pytest.param("", None, "redis://redis:6379/1", range(1, 2), id="no-xdist"),
        pytest.param("gw0", "4", "redis://redis:6379/1", range(1, 5), id="gw0-of-4"),
        pytest.param("gw3", "12", "redis://redis:6379/4", range(1, 13), id="gw3-of-12"),
    ],
)
def test_active_dbs_cover_all_workers(monkeypatch, settings, worker, count, location, expected) -> None:
    """Занятые БД считаются от базовой по числу воркеров, а не по своей БД."""
    monkeypatch.setenv("PYTEST_XDIST_WORKER", worker)
    if count is None:
        monkeypatch.delenv("PYTEST_XDIST_WORKER_COUNT", raising=False)
    else:
        monkeypatch.setenv("PYTEST_XDIST_WORKER_COUNT", count)
    settings.CACHES = {"default": {**settings.CACHES["default"], "LOCATION": location}}

    assert active_dbs() == expected


@pytest.mark.parametrize("base", range(REDIS_DATABASES))
def test_probe_never_touches_active_workers(base: int) -> None:
    """При любом допустимом числе воркеров проба не берёт их БД (R42.4-19)."""
    for count in range(1, REDIS_DATABASES - base + 1):
        active = range(base, base + count)
        free = [db for db in range(REDIS_DATABASES) if db not in active]
        probe = probe_dbs(active)
        if probe is None:
            assert len(free) < 2, f"база {base}, -n {count}: свободны {free}, а проба пропущена"
            continue
        assert probe[0] != probe[1], f"база {base}, -n {count}: одна БД на двоих {probe}"
        assert set(probe) <= set(free), f"база {base}, -n {count}: проба {probe} задевает воркеров {active}"


@pytest.mark.parametrize("requested", [None, "5"])
def test_worker_restart_is_forced_off(requested: str | None) -> None:
    """Хук выключает замену и при явном `--max-worker-restart` (R42.4-26)."""
    config = SimpleNamespace(option=SimpleNamespace(maxworkerrestart=requested))

    root_conftest.pytest_configure(config)

    assert config.option.maxworkerrestart == "0"


def test_crashed_worker_is_not_replaced(request: pytest.FixtureRequest) -> None:
    """
    Упавший воркер не заменяется (R42.4-26): замена получила бы следующий номер
    gwN, а с ним БД Redis вне `active_dbs()` — её могла бы очистить проба, а при
    базовой 1 замена gw15 обращается к несуществующей DB16.
    """
    assert request.config.option.maxworkerrestart == "0"
    # Без xdist (CI ставит только pytest-django и pytest-cov) значение не читает никто.
    dsession = pytest.importorskip("xdist.dsession")
    assert dsession.get_default_max_worker_restart(request.config) == 0


def test_workers_do_not_clear_each_other() -> None:
    """Очистка кэша первым воркером не трогает значение второго."""
    probe = probe_dbs(active_dbs())
    if probe is None:
        pytest.skip(f"свободных БД Redis меньше двух: воркеры занимают {active_dbs()}")
    first_db, second_db = probe
    # Базовая БД пробы — first_db: воркер gw0 получает её, а второй воркер
    # с индексом second_db - first_db — БД second_db.
    second_worker = f"gw{second_db - first_db}"
    try:
        second = run_worker(first_db, second_worker, "set=second", "get")
        first = run_worker(first_db, "gw0", "set=first", "get", "clear", "get")

        assert redis_db(first["location"]) == first_db
        assert redis_db(second["location"]) == second_db
        # Контрольные значения: каждый воркер прочитал своё.
        assert second["got"] == ["second"]
        assert first["got"] == ["first", None]

        after = run_worker(first_db, second_worker, "get")
        assert after["got"] == ["second"], "cache.clear() первого воркера удалил значение второго"
    finally:
        # Ключи с таймаутом и так истекут, но БД пробы оставляем пустыми.
        run_worker(first_db, second_worker, "clear")
