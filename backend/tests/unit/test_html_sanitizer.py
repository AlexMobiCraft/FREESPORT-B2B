"""
Очистка HTML новостей, блога и страниц (`apps/common/utils/html_sanitizer.py`, стори 42.6).

Каждый вредный фрагмент AC16 проверяется отдельно; разрешённая разметка
проходит без изменений. Страничный белый список `Page` — прежний.
"""

from __future__ import annotations

import pytest

from apps.common.utils.html_sanitizer import RICH_HTML_ATTRIBUTES, RICH_HTML_TAGS, sanitize_rich_html
from apps.pages.models import PAGE_HTML_ATTRIBUTES, PAGE_HTML_TAGS

pytestmark = pytest.mark.unit

ALLOWED = (
    '<h2>Заголовок</h2><p class="lead">Вводный <strong>абзац</strong></p>'
    '<ul><li>Пункт</li></ul><a href="https://optisport.ru/catalog">Каталог</a>'
)


@pytest.mark.parametrize(
    "dangerous, forbidden",
    [
        pytest.param("<script>alert(1)</script>", ["<script", "alert(1)"], id="script"),
        pytest.param('<img src="x" onerror="alert(1)">', ["onerror", "alert(1)"], id="onerror"),
        pytest.param('<a href="javascript:alert(1)">клик</a>', ["javascript:"], id="javascript-href"),
        pytest.param('<iframe src="https://evil.example"></iframe>', ["<iframe"], id="iframe"),
        pytest.param("<style>body{display:none}</style>", ["<style", "body{display:none}"], id="style"),
        pytest.param(
            '<meta http-equiv="refresh" content="0;url=https://evil.example">',
            ["<meta", "evil.example"],
            id="meta-refresh",
        ),
        pytest.param(
            '<link rel="stylesheet" href="https://evil.example/x.css">', ["<link", "evil.example"], id="link-css"
        ),
    ],
)
def test_dangerous_fragment_is_removed(dangerous, forbidden):
    cleaned = sanitize_rich_html(f"<p>до</p>{dangerous}<p>после</p>")

    for needle in forbidden:
        assert needle not in cleaned
    assert "<p>до</p>" in cleaned
    assert "<p>после</p>" in cleaned


def test_style_and_script_removed_with_content():
    """Bleach с strip=True оставил бы текст CSS и JS — блоки удаляются целиком до него."""
    cleaned = sanitize_rich_html("<style>.a{color:red}</style><script>var x = 1;</script><p>текст</p>")

    assert cleaned == "<p>текст</p>"


@pytest.mark.parametrize(
    "block",
    [
        pytest.param("<style>body{display:none}</style >", id="style-space"),
        pytest.param("<script>alert(1)</script >", id="script-space"),
        pytest.param("<head><title>заголовок</title></head >", id="head-space"),
        pytest.param("<STYLE>body{display:none}</STYLE\n>", id="style-newline-upper"),
        pytest.param("<script>alert(1)</script foo>", id="script-attribute"),
    ],
)
def test_block_with_loose_end_tag_removed_with_content(block):
    """HTML-парсер закрывает блок и на `</style >`: содержимое не должно остаться текстом (R42.6-4)."""
    assert sanitize_rich_html(f"<p>a</p>{block}x") == "<p>a</p>x"


def test_end_tag_with_hyphen_does_not_close_block():
    """`</style-x>` — другой тег: блок закрывает только `</style>` (R42.6-6)."""
    assert sanitize_rich_html("<p>a</p><style>x{}</style-x>CSS{}</style>x") == "<p>a</p>x"


def test_tag_with_hyphen_is_not_a_block():
    """`<script-widget>` — не `<script>`: тег вырезается, текст остаётся (R42.6-6).

    Настоящий `<script>` дальше — иначе блок не от чего было бы удалить до него.
    """
    html = "<p>a</p><script-widget>Важный текст</script-widget><p>b</p><script>x()</script>"

    assert sanitize_rich_html(html) == "<p>a</p>Важный текст<p>b</p>"


def test_allowed_markup_is_unchanged():
    assert sanitize_rich_html(ALLOWED) == ALLOWED


def test_empty_value_is_returned_as_is():
    assert sanitize_rich_html("") == ""


def test_meta_and_link_are_not_in_rich_whitelist():
    assert "meta" not in RICH_HTML_TAGS
    assert "link" not in RICH_HTML_TAGS
    assert "meta" not in RICH_HTML_ATTRIBUTES
    assert "link" not in RICH_HTML_ATTRIBUTES


def test_page_whitelist_keeps_meta_and_link_attributes():
    """Страничный список прежний: атрибуты meta и link есть, сами теги в списке тегов не появились."""
    assert PAGE_HTML_TAGS == RICH_HTML_TAGS
    assert PAGE_HTML_ATTRIBUTES["meta"] == ["content", "http-equiv", "charset", "name"]
    assert PAGE_HTML_ATTRIBUTES["link"] == ["href", "rel", "type"]
    assert {key: value for key, value in PAGE_HTML_ATTRIBUTES.items() if key not in ("meta", "link")} == (
        RICH_HTML_ATTRIBUTES
    )


def test_page_whitelist_cleans_like_before():
    html = '<p class="x">текст</p><meta charset="utf-8"><table><tr><td colspan="2">ячейка</td></tr></table>'

    assert sanitize_rich_html(html, tags=PAGE_HTML_TAGS, attributes=PAGE_HTML_ATTRIBUTES) == (
        '<p class="x">текст</p><table><tbody><tr><td colspan="2">ячейка</td></tr></tbody></table>'
    )
