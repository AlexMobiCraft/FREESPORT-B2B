"""
Очистка HTML, который сотрудники пишут в админке и сайт выводит как есть.

Фронтенд вставляет `content` новостей, статей и страниц без очистки
(`dangerouslySetInnerHTML`), а сайт работает на том же origin, что `/admin/`:
`<script>` в новости, открытой суперпользователем, мог бы от его имени
отправить форму админки. Поэтому HTML чистится на бэкенде при сохранении.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping

import bleach

# Удаляет блоки <style>...</style>, <script>...</script>, <head>...</head> ВМЕСТЕ
# с содержимым. Bleach с strip=True вырезает только теги, но оставляет текст —
# поэтому CSS/JS код проступал на страницу. Имя тега кончается там же, где у
# HTML-парсера, — на пробеле, `/` или `>`: `</style >`, `</script foo>` закрывают
# блок, а `</style-x>` и `<script-widget>` — другие теги.
_STRIP_BLOCKS_RE = re.compile(r"<(style|script|head)(?=[\s/>])[^>]*>[\s\S]*?</\1(?=[\s/>])[^>]*>", re.IGNORECASE)

# Белый список rich-контента (перенесён из Page.save).
RICH_HTML_TAGS: tuple[str, ...] = (
    "p",
    "div",
    "span",
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
    "ul",
    "ol",
    "li",
    "a",
    "strong",
    "em",
    "b",
    "i",
    "u",
    "s",
    "br",
    "hr",
    "table",
    "thead",
    "tbody",
    "tfoot",
    "tr",
    "td",
    "th",
    "caption",
    "colgroup",
    "col",
    "img",
    "figure",
    "figcaption",
    "blockquote",
    "pre",
    "code",
    "sub",
    "sup",
    "dl",
    "dt",
    "dd",
    "details",
    "summary",
    "section",
    "article",
    "header",
    "footer",
    "nav",
    "main",
    "aside",
    "address",
    "time",
    "mark",
    "small",
    "cite",
    "q",
    "abbr",
    "dfn",
    "kbd",
    "samp",
    "var",
    "wbr",
    "ins",
    "del",
)

RICH_HTML_ATTRIBUTES: dict[str, list[str]] = {
    "a": ["href", "title", "target", "rel"],
    "img": ["src", "alt", "width", "height", "loading"],
    "td": ["colspan", "rowspan"],
    "th": ["colspan", "rowspan"],
    "*": ["class", "id"],
}

RICH_HTML_PROTOCOLS = ("http", "https", "mailto")


def strip_html_blocks(html: str) -> str:
    """Удаляет блоки `<style>`, `<script>` и `<head>` вместе с содержимым."""
    return _STRIP_BLOCKS_RE.sub("", html)


def sanitize_rich_html(
    html: str,
    *,
    tags: Iterable[str] = RICH_HTML_TAGS,
    attributes: Mapping[str, list[str]] = RICH_HTML_ATTRIBUTES,
) -> str:
    """
    Оставляет в HTML только белый список тегов, атрибутов и протоколов ссылок.

    Запрещённые теги удаляются (`strip=True`), а не экранируются; блоки
    `<style>`/`<script>`/`<head>` — вместе с содержимым.
    """
    if not html:
        return html
    cleaned: str = bleach.clean(
        strip_html_blocks(html),
        tags=set(tags),
        attributes=dict(attributes),
        protocols=list(RICH_HTML_PROTOCOLS),
        strip=True,
    )
    return cleaned
