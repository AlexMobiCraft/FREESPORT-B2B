"""
Тесты реестра текстов согласий (стори 41.9).

Реестр — единственный источник значения `UserConsent.consent_text_version`.
Если он начнёт молча отдавать неверную или несуществующую версию, журнал
согласий перестанет быть доказательством по ФЗ-152 ст. 9, а обнаружится это
уже на живых записях. Поэтому здесь проверяются три вещи: все живые пары
привязаны, версия меняется вместе с текстом, а исторические версии
по-прежнему разрешаются в свой текст.
"""

import json

import pytest

from apps.common.consent_texts import (
    MAX_VERSION_LENGTH,
    ConsentTextRegistry,
    ConsentTextsError,
    compute_consent_text_version,
    current_consent_text_version,
    load_registry,
    resolve_consent_text,
)
from apps.common.models import UserConsent


# Маркер `unit` проставляет pytest_collection_modifyitems по каталогу — руками не ставим.


def _known_versions(surfaces: dict) -> list[str]:
    """Версии всех ревизий фикстуры — то, что реестр требует в `known_versions`."""
    return [
        compute_consent_text_version(revision["label"], revision["text"])
        for surface in surfaces.values()
        for revision in surface["revisions"]
    ]


def _registry(surfaces: dict, bindings: dict, known_versions: list[str] | None = None) -> ConsentTextRegistry:
    """Реестр из фикстуры в памяти — файл на диске не трогается.

    `known_versions` по умолчанию вычисляется из самих ревизий: тесты, которые
    проверяют не защиту истории, а другое поведение, не должны носить хеши руками.
    Тесты самой защиты передают список явно.
    """
    return ConsentTextRegistry(
        {
            "surfaces": surfaces,
            "bindings": bindings,
            "known_versions": _known_versions(surfaces) if known_versions is None else known_versions,
        },
        origin="<фикстура>",
    )


# ---------------------------------------------------------------------------
# Реальный реестр проекта
# ---------------------------------------------------------------------------


def test_every_live_pair_is_bound_to_a_surface():
    """Каждая живая пара (источник, тип согласия) привязана к поверхности.

    Живые источники берутся из модели, а не переписываются здесь списком:
    добавление источника в `SOURCE_CHOICES` без привязки в реестре обязано
    ронять этот тест, а не приводить к падению на первой же записи согласия.
    """
    live_sources = [value for value, _label in UserConsent.SOURCE_CHOICES if value != UserConsent.SOURCE_UNKNOWN]
    consent_types = [value for value, _label in UserConsent.CONSENT_TYPE_CHOICES]

    expected_pairs = {(source, consent_type) for source in live_sources for consent_type in consent_types}

    assert load_registry().bound_pairs == expected_pairs


def test_unknown_source_is_not_bound():
    """`unknown` — метка строк до миграции 0019, у неё не может быть текста."""
    bound_sources = {source for source, _consent_type in load_registry().bound_pairs}

    assert UserConsent.SOURCE_UNKNOWN not in bound_sources


def test_registry_versions_are_unique():
    """Совпадение версий двух ревизий сделало бы разрешение версии неоднозначным."""
    versions = load_registry().versions

    assert len(set(versions)) == len(versions)


def test_current_version_resolves_back_to_its_text():
    """Версия, записанная в журнал, разрешается обратно в дословный текст."""
    for source, consent_type in load_registry().bound_pairs:
        version = current_consent_text_version(source, consent_type)
        text = resolve_consent_text(version)

        assert text, f"версия {version} пары ({source}, {consent_type}) не разрешается в текст"
        assert compute_consent_text_version(version.rsplit("-", 1)[0], text) == version


def test_newsletter_pair_shares_one_surface():
    """Чекбокс подписки один и покрывает оба согласия (редакция 2 стори 41.3)."""
    assert current_consent_text_version(UserConsent.SOURCE_NEWSLETTER, "pdp_contract") == current_consent_text_version(
        UserConsent.SOURCE_NEWSLETTER, "marketing_email"
    )


def test_1c_link_reuses_registration_surfaces():
    """Привязка к 1С — та же форма регистрации, отдельных текстов не существует."""
    for consent_type in ("pdp_contract", "marketing_email"):
        assert current_consent_text_version(UserConsent.SOURCE_1C_LINK, consent_type) == current_consent_text_version(
            UserConsent.SOURCE_REGISTRATION, consent_type
        )


def test_registration_pdp_and_marketing_have_different_versions():
    """У ПДн и маркетинга регистрации — разные чекбоксы и разные версии."""
    pdp = current_consent_text_version(UserConsent.SOURCE_REGISTRATION, "pdp_contract")
    marketing = current_consent_text_version(UserConsent.SOURCE_REGISTRATION, "marketing_email")

    assert pdp != marketing


def test_registry_file_is_valid_json_with_normalized_texts():
    """Файл реестра читается как JSON, тексты нормализованы (одна строка, одиночные пробелы)."""
    from apps.common.consent_texts import REGISTRY_PATH

    data = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))

    for surface_name, surface in data["surfaces"].items():
        for revision in surface["revisions"]:
            text = revision["text"]
            assert text == " ".join(text.split()), f"текст поверхности {surface_name} не нормализован"


# ---------------------------------------------------------------------------
# Поведение загрузчика на фикстурах (файл на диске не правится)
# ---------------------------------------------------------------------------


def test_version_changes_when_text_changes():
    """AC5: новая ревизия с изменённым текстом даёт другую версию.

    Проверяется на фикстуре с двумя ревизиями, а не правкой файла реестра:
    именно так поведёт себя реестр, когда формулировку однажды перепишут.
    """
    old_text = "Я даю согласие на обработку моих персональных данных"
    new_text = "Я даю согласие на обработку моих персональных данных и на получение рассылки"
    registry = _registry(
        surfaces={
            "surface": {
                "revisions": [
                    {"label": "2026-01-01", "text": old_text},
                    {"label": "2026-06-01", "text": new_text},
                ]
            }
        },
        bindings={"registration.pdp_contract": "surface"},
    )

    old_version = compute_consent_text_version("2026-01-01", old_text)
    new_version = compute_consent_text_version("2026-06-01", new_text)

    # Действующая версия — последняя ревизия.
    assert registry.current_version("registration", "pdp_contract") == new_version
    assert new_version != old_version
    # AC5: прежние записи сохраняют свою версию и по-прежнему разрешаются в свой текст.
    assert registry.resolve_text(old_version) == old_text
    assert registry.resolve_text(new_version) == new_text


def test_version_changes_even_when_label_stays_the_same():
    """Правка текста без смены метки всё равно меняет версию — бамп не забыть."""
    first = compute_consent_text_version("2026-01-01", "Текст один")
    second = compute_consent_text_version("2026-01-01", "Текст два")

    assert first != second
    assert first.startswith("2026-01-01-")
    assert second.startswith("2026-01-01-")


def test_version_digest_is_32_hex():
    """Хеш в версии — 32 hex, то есть 128 бит (решение Alex, шестой круг ревью стори 41.9).

    Проверяется и формула, и каждая версия реального реестра: `known_versions`
    обязан быть пересчитан вместе с формулой, а не остаться короткими строками.
    """
    label = "2026-01-01"
    digest = compute_consent_text_version(label, "Текст").removeprefix(f"{label}-")

    assert len(digest) == 32
    assert set(digest) <= set("0123456789abcdef")

    for version in load_registry().versions:
        assert len(version.rsplit("-", 1)[1]) == 32, f"версия {version} посчитана не 32-символьным хешем"


def test_short_digest_collision_found_by_review_is_resolved():
    """Две разные формулировки при одной метке не получают одну версию.

    Пару нашло ревью: у «Текст согласия 1115» и «Текст согласия 1675» первые
    8 hex sha256 совпадают. При 8-символьном хеше обе дали бы одну версию, и
    журнал перестал бы различать две редакции согласия.
    """
    label = "2026-01-01"
    first = compute_consent_text_version(label, "Текст согласия 1115")
    second = compute_consent_text_version(label, "Текст согласия 1675")
    start = len(f"{label}-")

    # Предпосылка теста: коллизия по первым 8 hex действительно есть.
    assert first[start : start + 8] == second[start : start + 8] == "f4ef3d1f"
    assert first != second


def test_unknown_version_resolves_to_none():
    """Версия, которой нет в реестре, разрешается в None, а не в чужой текст."""
    assert resolve_consent_text("1999-01-01-deadbeef") is None


def test_unbound_pair_raises():
    """Непривязанная пара обязана падать, а не отдавать молчаливый `unknown`."""
    registry = _registry(
        surfaces={"surface": {"revisions": [{"label": "2026-01-01", "text": "Текст"}]}},
        bindings={"registration.pdp_contract": "surface"},
    )

    with pytest.raises(ConsentTextsError, match="не привязана"):
        registry.current_version("newsletter", "pdp_contract")


def test_duplicate_revision_raises():
    """Две одинаковые ревизии дали бы одну версию на два места в истории."""
    with pytest.raises(ConsentTextsError, match="встречается дважды"):
        _registry(
            surfaces={
                "surface": {
                    "revisions": [
                        {"label": "2026-01-01", "text": "Текст"},
                        {"label": "2026-01-01", "text": "Текст"},
                    ]
                }
            },
            bindings={"registration.pdp_contract": "surface"},
        )


def test_binding_to_missing_surface_raises():
    with pytest.raises(ConsentTextsError, match="неизвестную поверхность"):
        _registry(
            surfaces={"surface": {"revisions": [{"label": "2026-01-01", "text": "Текст"}]}},
            bindings={"registration.pdp_contract": "опечатка"},
        )


def test_non_normalized_text_raises():
    """Ненормализованный текст не совпал бы с доступным именем чекбокса на фронте."""
    with pytest.raises(ConsentTextsError, match="не нормализован"):
        _registry(
            surfaces={"surface": {"revisions": [{"label": "2026-01-01", "text": "Текст  с   пробелами"}]}},
            bindings={"registration.pdp_contract": "surface"},
        )


def test_empty_revisions_raise():
    # Привязка непустая намеренно: пустой раздел `bindings` отбраковывается
    # раньше и заслонил бы проверяемую здесь ошибку.
    with pytest.raises(ConsentTextsError, match="пустой список ревизий"):
        _registry(
            surfaces={"surface": {"revisions": []}},
            bindings={"registration.pdp_contract": "surface"},
        )


def test_malformed_binding_key_raises():
    with pytest.raises(ConsentTextsError, match="вид"):
        _registry(
            surfaces={"surface": {"revisions": [{"label": "2026-01-01", "text": "Текст"}]}},
            bindings={"registration": "surface"},
        )


def test_missing_registry_file_raises_with_path(tmp_path):
    """Отсутствие файла — падение с указанием пути, а не тихий фолбэк."""
    missing = tmp_path / "consent_texts.json"

    with pytest.raises(ConsentTextsError, match=str(missing.name)):
        load_registry(missing)


def test_broken_json_raises_with_path(tmp_path):
    broken = tmp_path / "consent_texts.json"
    broken.write_text("{не json", encoding="utf-8")

    with pytest.raises(ConsentTextsError, match="не разбирается как JSON"):
        load_registry(broken)


def test_broken_encoding_raises_consent_texts_error(tmp_path):
    """Реестр, сохранённый не в UTF-8, тоже падает единым исключением с путём.

    `UnicodeDecodeError` наследуется от `ValueError`, а не от `OSError`, поэтому
    без отдельной ветки он вылетал бы мимо `ConsentTextsError` и рвал обещание
    модуля: одно понятное исключение, называющее файл.
    """
    broken = tmp_path / "consent_texts.json"
    # Кириллица в CP1251 — не декодируется как UTF-8.
    broken.write_bytes('{"surfaces": {"а": {}}}'.encode("cp1251"))

    with pytest.raises(ConsentTextsError, match="не читается как UTF-8"):
        load_registry(broken)


@pytest.mark.parametrize("field", ["text", "label"])
def test_lone_surrogate_raises_consent_texts_error(tmp_path, field):
    """Одиночный суррогат из валидного JSON escape — то же единое исключение с путём.

    `"\\ud800"` — корректный JSON: `json.loads` отдаёт строку с одиночным
    суррогатом, а `str.encode("utf-8")` на ней падает `UnicodeEncodeError`. Текст
    хешируется при вычислении версии, метка входит в саму версию, а версия уходит
    в БД — оба пути обязаны давать `ConsentTextsError` с файлом и поверхностью,
    а не голое исключение кодека.
    """
    revision = {"label": "2026-09-10", "text": "Согласен"}
    revision[field] += "\ud800"
    # Для метки версия вычисляется без ошибки — список заполнен ею, чтобы до правки
    # загрузка проходила целиком, а не падала на сверке `known_versions`.
    known = (
        [compute_consent_text_version(revision["label"], revision["text"])]
        if field == "label"
        else ["2026-09-10-00000000"]
    )
    registry_file = tmp_path / "consent_texts.json"
    # `ensure_ascii` (по умолчанию) пишет суррогат escape-последовательностью.
    registry_file.write_text(
        json.dumps(
            {
                "surfaces": {"surface": {"revisions": [revision]}},
                "bindings": {"newsletter.pdp_contract": "surface"},
                "known_versions": known,
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ConsentTextsError, match="UTF-8") as excinfo:
        load_registry(registry_file)

    assert str(registry_file) in str(excinfo.value)
    assert "surface" in str(excinfo.value)


# ---------------------------------------------------------------------------
# Страж истории ревизий и границы реестра (замечания ревью стори 41.9)
# ---------------------------------------------------------------------------


def test_registry_file_declares_every_version_in_known_versions():
    """Реальный реестр проекта фиксирует все свои ревизии в `known_versions`."""
    from apps.common.consent_texts import REGISTRY_PATH

    data = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    computed = {
        compute_consent_text_version(revision["label"], revision["text"])
        for surface in data["surfaces"].values()
        for revision in surface["revisions"]
    }

    assert set(data["known_versions"]) == computed


def test_editing_historical_revision_text_raises():
    """Правка текста уже действовавшей ревизии обрывает связь записей с текстом.

    Именно так выглядит «мелкая правка формулировки задним числом»: версия
    пересчитывается, а версия, записанная в журнал, больше ничему не соответствует.
    """
    original = "Я даю согласие на обработку моих персональных данных"
    frozen = compute_consent_text_version("2026-01-01", original)

    with pytest.raises(ConsentTextsError, match="изменён или"):
        _registry(
            surfaces={"surface": {"revisions": [{"label": "2026-01-01", "text": original + " и на рассылку"}]}},
            bindings={"registration.pdp_contract": "surface"},
            known_versions=[frozen],
        )


def test_deleting_historical_revision_raises():
    """Удаление старой ревизии «как устаревшей» обязано ронять загрузку."""
    old_version = compute_consent_text_version("2026-01-01", "Прежняя формулировка")
    new_text = "Действующая формулировка"

    with pytest.raises(ConsentTextsError, match="ни одна ревизия их больше не даёт"):
        _registry(
            surfaces={"surface": {"revisions": [{"label": "2026-06-01", "text": new_text}]}},
            bindings={"registration.pdp_contract": "surface"},
            known_versions=[old_version, compute_consent_text_version("2026-06-01", new_text)],
        )


def test_new_revision_must_be_recorded_in_known_versions():
    """Добавленная ревизия без записи в `known_versions` не проходит загрузку."""
    old_text = "Прежняя формулировка"
    new_text = "Новая формулировка"

    with pytest.raises(ConsentTextsError, match="не зафиксированы"):
        _registry(
            surfaces={
                "surface": {
                    "revisions": [
                        {"label": "2026-01-01", "text": old_text},
                        {"label": "2026-06-01", "text": new_text},
                    ]
                }
            },
            bindings={"registration.pdp_contract": "surface"},
            known_versions=[compute_consent_text_version("2026-01-01", old_text)],
        )


def test_missing_known_versions_section_raises():
    """Раздел нельзя просто убрать — иначе страж истории обходится удалением."""
    with pytest.raises(ConsentTextsError, match="known_versions"):
        ConsentTextRegistry(
            {
                "surfaces": {"surface": {"revisions": [{"label": "2026-01-01", "text": "Текст"}]}},
                "bindings": {"registration.pdp_contract": "surface"},
            },
            origin="<фикстура>",
        )


def test_duplicate_known_version_raises():
    version = compute_consent_text_version("2026-01-01", "Текст")

    with pytest.raises(ConsentTextsError, match="повторы"):
        _registry(
            surfaces={"surface": {"revisions": [{"label": "2026-01-01", "text": "Текст"}]}},
            bindings={"registration.pdp_contract": "surface"},
            known_versions=[version, version],
        )


def test_version_longer_than_model_field_raises():
    """Версия обязана помещаться в `UserConsent.consent_text_version`."""
    long_label = "2026-01-01-" + "x" * MAX_VERSION_LENGTH

    with pytest.raises(ConsentTextsError, match="длиннее"):
        _registry(
            surfaces={"surface": {"revisions": [{"label": long_label, "text": "Текст"}]}},
            bindings={"registration.pdp_contract": "surface"},
        )


def test_max_version_length_matches_model_field():
    """Константа модуля и `max_length` поля модели не имеют права разъехаться.

    Модуль не импортирует Django (тот же JSON читает страж на фронте), поэтому
    значение продублировано — и сверяется здесь.
    """
    field = UserConsent._meta.get_field("consent_text_version")

    assert field.max_length == MAX_VERSION_LENGTH


def test_every_registry_version_fits_the_model_field():
    """Ни одна живая версия реестра не обрежется при записи в журнал."""
    for version in load_registry().versions:
        assert len(version) <= MAX_VERSION_LENGTH


def test_duplicate_json_keys_are_rejected(tmp_path):
    """Повтор ключа в JSON молча оставил бы последнее значение и подменил привязку."""
    registry_file = tmp_path / "consent_texts.json"
    registry_file.write_text(
        """
        {
          "surfaces": {
            "a": {"revisions": [{"label": "2026-01-01", "text": "Текст A"}]},
            "b": {"revisions": [{"label": "2026-01-01", "text": "Текст B"}]}
          },
          "known_versions": ["ignored"],
          "bindings": {
            "registration.pdp_contract": "a",
            "registration.pdp_contract": "b"
          }
        }
        """,
        encoding="utf-8",
    )

    with pytest.raises(ConsentTextsError, match="объявлен дважды"):
        load_registry(registry_file)
