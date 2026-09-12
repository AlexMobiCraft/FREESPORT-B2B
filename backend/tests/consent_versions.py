"""Версии текстов согласий для тестовых payload'ов (стори 41.9).

Формы регистрации и подписки присылают версию формулировки, которую они
показали человеку; сервер отклоняет запрос, если версия не действующая.
Тестам эта версия нужна в каждом payload, и брать её литералом нельзя — при
правке текста в реестре пришлось бы руками чинить десятки тестов. Значения
читаются из того же реестра, что и рабочий код.
"""

from __future__ import annotations

from apps.common.consent_texts import current_consent_text_version
from apps.common.models import UserConsent

REGISTRATION_PDP_TEXT_VERSION = current_consent_text_version(UserConsent.SOURCE_REGISTRATION, "pdp_contract")
REGISTRATION_MARKETING_TEXT_VERSION = current_consent_text_version(UserConsent.SOURCE_REGISTRATION, "marketing_email")
NEWSLETTER_TEXT_VERSION = current_consent_text_version(UserConsent.SOURCE_NEWSLETTER, "pdp_contract")
