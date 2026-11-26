"""
Свои файловые каталоги на воркер pytest-xdist (`freesport/settings/test.py`, R42.4-24).

Настройки разводят `MEDIA_ROOT`, `ONEC_PRIVATE_DIR`, каталоги обмена 1С и логов
по имени воркера. Если два воркера параллельного прогона получат один корень,
импорты и загрузки соседей будут дописывать и перезаписывать файлы друг друга.
Обязательный CI-прогон последовательный и такую поломку настроек не увидит,
а тесты обмена подменяют каталоги через `tmp_path`. Поэтому тест поднимает
настройки двух воркеров в отдельных процессах — так же, как их получает xdist, —
и пишет через `FileStreamService` файл с одним и тем же относительным именем.

Временный каталог дочерних процессов (`TMPDIR`) — `tmp_path` теста: проба не
задевает каталоги воркеров текущего прогона.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

from django.conf import settings

SESSION = "xdist-isolation-probe"
FILENAME = "import.zip"
WORKERS = ("gw0", "gw1")

# Дочерний процесс: настройки freesport.settings.test, шаг из argv —
# `write=<содержимое>` или `read`. Печатает файловые корни и прочитанное.
CHILD = """
import json, sys
import django

django.setup()
from django.conf import settings
from apps.integrations.onec_exchange.file_service import FileStreamService

session, filename, step = sys.argv[1:4]
service = FileStreamService(session)
if step.startswith("write="):
    service.append_chunk(filename, step[len("write="):].encode())
roots = {
    "MEDIA_ROOT": settings.MEDIA_ROOT,
    "ONEC_PRIVATE_DIR": settings.ONEC_PRIVATE_DIR,
    "TEMP_DIR": settings.ONEC_EXCHANGE["TEMP_DIR"],
    "IMPORT_DIR": settings.ONEC_EXCHANGE["IMPORT_DIR"],
    "EXCHANGE_LOG_DIR": settings.EXCHANGE_LOG_DIR,
}
path = service.get_file_path(filename)
print(json.dumps({
    "roots": {name: str(value) for name, value in roots.items()},
    "path": str(path),
    "content": path.read_bytes().decode() if path.exists() else None,
}))
"""


def run_worker(tmp_dir: Path, worker: str, step: str) -> dict[str, Any]:
    """Шаг с файлом в отдельном процессе воркера `worker`, временный каталог — `tmp_dir`."""
    env = {
        **os.environ,
        "DJANGO_SETTINGS_MODULE": "freesport.settings.test",
        "PYTEST_XDIST_WORKER": worker,
        "TMPDIR": str(tmp_dir),
    }
    completed = subprocess.run(
        [sys.executable, "-c", CHILD, SESSION, FILENAME, step],
        cwd=Path(settings.BASE_DIR),
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert completed.returncode == 0, f"воркер {worker} упал:\n{completed.stderr}"
    return json.loads(completed.stdout.strip().splitlines()[-1])


def test_workers_have_separate_file_roots(tmp_path: Path) -> None:
    """Каждый файловый корень у воркеров свой и лежит во временном каталоге."""
    first, second = (run_worker(tmp_path, worker, "read")["roots"] for worker in WORKERS)

    for name, root in first.items():
        assert root != second[name], f"{name} у {WORKERS[0]} и {WORKERS[1]} общий: {root}"
    for roots in (first, second):
        for name, root in roots.items():
            assert Path(root).is_relative_to(tmp_path), f"{name} вне временного каталога: {root}"


def test_same_relative_file_is_not_shared(tmp_path: Path) -> None:
    """Файл с одним относительным именем, записанный двумя воркерами, у каждого свой."""
    first = run_worker(tmp_path, WORKERS[0], "write=first")
    second = run_worker(tmp_path, WORKERS[1], "write=second")

    assert first["path"] != second["path"]
    # Контрольные значения: каждый воркер прочитал записанное.
    assert first["content"] == "first"
    assert second["content"] == "second"

    after = run_worker(tmp_path, WORKERS[0], "read")
    assert after["content"] == "first", "запись второго воркера попала в файл первого"
