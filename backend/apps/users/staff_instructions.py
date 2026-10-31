"""
Инструкции для сотрудников в разделе менеджера `/manager/instructions/`.

Реестр — единственное место, где перечислены инструкции: из него строятся
список страницы `/manager/instructions/`, блок на главной раздела и маршрут
`/manager/instructions/<slug>/`. Текст каждой инструкции лежит в шаблоне
`admin/instructions/<template>.html`, картинки — в статике приложения
(`users/static/users/instructions/`). Новая инструкция — запись здесь плюс
шаблон; маршруты и ссылки добавлять не нужно.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class StaffInstruction:
    """Одна инструкция: адрес, название для списка, краткое описание и шаблон текста."""

    slug: str
    title: str
    summary: str
    template: str


# Адрес инструкции, на которую ссылается страница подтверждения заявки.
VERIFY_CLIENT_SLUG = "verify-client"

STAFF_INSTRUCTIONS: tuple[StaffInstruction, ...] = (
    StaffInstruction(
        slug=VERIFY_CLIENT_SLUG,
        title="Подтверждение заявки нового клиента",
        summary="Как проверить данные клиента, выбрать контрагента 1С, подтвердить или отклонить заявку.",
        template="admin/instructions/verify_client.html",
    ),
)


def get_instruction(slug: str) -> StaffInstruction | None:
    """Инструкция по адресу или None, если такой нет в реестре."""
    return next((instruction for instruction in STAFF_INSTRUCTIONS if instruction.slug == slug), None)
