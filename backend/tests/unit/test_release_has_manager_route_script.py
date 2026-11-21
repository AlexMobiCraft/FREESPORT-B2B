"""
Скрипт `scripts/deploy/release-has-manager-route.sh` (R42.4-35).

`deploy.yml` после деплоя проверяет `/manager/` только у релиза, в коде которого
этот маршрут есть: откат (`image_tag`) на релиз до стори 42.4 разворачивает
исправный образ без раздела, и обязательная проверка дала бы ложный провал.
Решает код разворачиваемого коммита, а не ответ сервера. Тест строит временный
git-репозиторий с историей «до раздела → с разделом» и запускает скрипт в нём.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

# В тестовом контейнере scripts/deploy смонтирован в /app/scripts/deploy, в CI и
# venv pytest стартует из backend/ полного checkout — скрипт на уровень выше.
_BACKEND_ROOT = Path(__file__).resolve().parents[2]
_SCRIPT_DIRS = (_BACKEND_ROOT / "scripts" / "deploy", _BACKEND_ROOT.parent / "scripts" / "deploy")
_SCRIPT_NAME = "release-has-manager-route.sh"
SCRIPT = next((path / _SCRIPT_NAME for path in _SCRIPT_DIRS if (path / _SCRIPT_NAME).is_file()), None)
URLS = _BACKEND_ROOT / "freesport" / "urls.py"

pytestmark = pytest.mark.skipif(
    SCRIPT is None or shutil.which("bash") is None or shutil.which("git") is None,
    reason=f"нужны bash, git и скрипт (искали в {[str(p) for p in _SCRIPT_DIRS]})",
)

URLS_BEFORE_SECTION = 'urlpatterns = [\n    path("admin/", admin.site.urls),\n]\n'
# Релиз после 42.4 и до 42.6: раздел менеджера есть, раздела маркетинга нет.
URLS_MANAGER_ONLY = (
    'urlpatterns = [\n    path("admin/", admin.site.urls),\n    path("manager/", manager_site.urls),\n]\n'
)
# Релиз после 42.6 и до 42.7: разделы менеджера и маркетинга есть, раздела руководителя нет.
URLS_BEFORE_SUPERVISOR = (
    'urlpatterns = [\n    path("admin/", admin.site.urls),\n    path("manager/", manager_site.urls),\n'
    '    path("marketing/", marketing_site.urls),\n]\n'
)


def git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-c", "user.name=test", "-c", "user.email=test@example.com", *args],
        cwd=repo,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=True,
    ).stdout.strip()


def commit_urls(repo: Path, content: str) -> str:
    """Коммитит backend/freesport/urls.py с заданным текстом, возвращает SHA."""
    urls = repo / "backend" / "freesport" / "urls.py"
    urls.parent.mkdir(parents=True, exist_ok=True)
    urls.write_text(content, encoding="utf-8")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "release")
    return git(repo, "rev-parse", "HEAD")


@pytest.fixture
def history(tmp_path: Path) -> tuple[Path, str, str]:
    """Репозиторий: релиз до раздела, затем релиз с настоящим urls.py проекта (HEAD)."""
    git(tmp_path, "init", "-q")
    before = commit_urls(tmp_path, URLS_BEFORE_SECTION)
    current = commit_urls(tmp_path, URLS.read_text(encoding="utf-8"))
    return tmp_path, before, current


@pytest.fixture
def before_supervisor_release(history: tuple[Path, str, str]) -> tuple[Path, str]:
    """Тот же репозиторий плюс коммит релиза с разделами менеджера и маркетинга, до 42.7."""
    repo, _, _ = history
    git(repo, "checkout", "-q", "-b", "before-supervisor", "HEAD~1")
    return repo, commit_urls(repo, URLS_BEFORE_SUPERVISOR)


@pytest.fixture
def manager_only_release(history: tuple[Path, str, str]) -> tuple[Path, str]:
    """Тот же репозиторий плюс коммит релиза с разделом менеджера без раздела маркетинга."""
    repo, _, _ = history
    git(repo, "checkout", "-q", "-b", "manager-only", "HEAD~1")
    return repo, commit_urls(repo, URLS_MANAGER_ONLY)


def run_script(repo: Path, release: str, *section: str) -> subprocess.CompletedProcess[str]:
    """Без `section` — прежний вызов, раздел по умолчанию `/manager/`."""
    return subprocess.run(
        ["bash", str(SCRIPT), release, *section],
        cwd=repo,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=60,
    )


def test_current_release_has_section(history):
    """Настоящий urls.py проекта распознаётся: смена записи маршрута уронит тест, а не пропустит проверку."""
    repo, _, current = history

    result = run_script(repo, current)

    assert result.returncode == 0, result.stdout + result.stderr


def test_short_sha_is_resolved(history):
    """Теги образов в ghcr — короткий SHA коммита (`type=sha` в deploy.yml)."""
    repo, _, current = history

    result = run_script(repo, current[:7])

    assert result.returncode == 0, result.stdout + result.stderr


def test_release_before_section_is_not_checked(history):
    """Откат на релиз до 42.4: в рабочей копии раздел есть, но решает коммит релиза."""
    repo, before, _ = history

    result = run_script(repo, before)

    assert result.returncode == 1, result.stdout + result.stderr


def test_release_without_urls_file_is_not_checked(tmp_path):
    git(tmp_path, "init", "-q")
    (tmp_path / "README.md").write_text("до backend\n", encoding="utf-8")
    git(tmp_path, "add", "-A")
    git(tmp_path, "commit", "-q", "-m", "init")

    result = run_script(tmp_path, git(tmp_path, "rev-parse", "HEAD"))

    assert result.returncode == 1, result.stdout + result.stderr


@pytest.mark.parametrize("release", ["production", "0" * 40, ""], ids=["tag-name", "unknown-sha", "empty"])
def test_unknown_release_is_reported(history, release):
    """Неизвестный коммит — отдельный код: deploy.yml тогда проверяет /manager/, а не пропускает."""
    repo, _, _ = history

    result = run_script(repo, release)

    assert result.returncode == 2, result.stdout + result.stderr


def test_current_release_has_marketing_section(history):
    """Стори 42.6: настоящий urls.py проекта содержит раздел маркетинга."""
    repo, _, current = history

    result = run_script(repo, current, "marketing")

    assert result.returncode == 0, result.stdout + result.stderr


def test_release_before_marketing_is_not_checked(manager_only_release):
    """Релиз с /manager/, но до 42.6: /marketing/ не проверяется, /manager/ — проверяется."""
    repo, release = manager_only_release

    assert run_script(repo, release, "marketing").returncode == 1
    assert run_script(repo, release).returncode == 0
    assert run_script(repo, release, "manager").returncode == 0


def test_current_release_has_supervisor_section(history):
    """Стори 42.7: настоящий urls.py проекта содержит раздел руководителя."""
    repo, _, current = history

    result = run_script(repo, current, "supervisor")

    assert result.returncode == 0, result.stdout + result.stderr


def test_release_before_supervisor_is_not_checked(before_supervisor_release):
    """Релиз с /manager/ и /marketing/, но до 42.7: /supervisor/ не проверяется, остальные — проверяются."""
    repo, release = before_supervisor_release

    assert run_script(repo, release, "supervisor").returncode == 1
    assert run_script(repo, release).returncode == 0
    assert run_script(repo, release, "marketing").returncode == 0


def test_release_before_any_section_has_no_marketing(history):
    repo, before, _ = history

    result = run_script(repo, before, "marketing")

    assert result.returncode == 1, result.stdout + result.stderr


@pytest.mark.parametrize("section", ["Marketing", "../admin", "market ing", "marketing/"])
def test_invalid_section_name_is_reported(history, section):
    """Недопустимое имя раздела не превращается в «релиз раньше раздела» (код 1)."""
    repo, _, current = history

    result = run_script(repo, current, section)

    assert result.returncode == 2, result.stdout + result.stderr
    assert "Недопустимое имя раздела" in result.stdout
