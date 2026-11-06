# Seed data for Manager Region Routing feature.
#
# Источник — файл "Электронные адреса менеджеров и Федер округа.xlsx".
# Сопоставление «первые 2 цифры ИНН = код субъекта РФ» → федеральный округ →
# менеджер. Правила редактируются через Django Admin; эта миграция лишь задаёт
# начальное состояние (идемпотентно через get_or_create).

from django.db import migrations

MILOVANOV = ("Милованов Максим", "manager3@freesportopt.ru")
LOPATINA = ("Лопатина Диана", "d.lopatina@freesportopt.ru")
GUSEV = ("Гусев Георгий", "1managermsk@freesportopt.ru")
ISAKOVA = ("Исакова Галина", "manager5@freesportopt.ru")
CHERNOV = ("Чернов Виктор", "managermsk3@freesportopt.ru")
ADMIN = ("основная почта", "admin@freesportopt.ru")

# (Федеральный округ, менеджер, [коды субъектов РФ])
REGION_GROUPS = [
    ("ЦФО", GUSEV, ["31", "32", "33", "36", "37", "40", "44", "46", "48", "50", "57", "62", "67", "68", "69", "71", "76", "77"]),
    ("СЗФО", LOPATINA, ["10", "11", "29", "35", "39", "47", "51", "53", "60", "78", "83"]),
    ("СКФО", MILOVANOV, ["05", "06", "07", "09", "15", "20", "26"]),
    ("ПФО", GUSEV, ["02", "12", "13", "16", "18", "21", "43", "52", "56", "58", "59", "63", "64", "73"]),
    ("УФО", LOPATINA, ["45", "66", "72", "74", "86", "89"]),
    ("СибФО", ISAKOVA, ["04", "17", "19", "22", "24", "38", "42", "54", "55", "70"]),
    ("ДФО", ISAKOVA, ["03", "14", "25", "27", "28", "41", "49", "65", "75", "79", "87"]),
    # ЮФО делится по регионам между двумя менеджерами.
    ("ЮФО", LOPATINA, ["34", "30", "08", "61"]),  # Волгоград, Астрахань, Калмыкия, Ростов
    ("ЮФО", ISAKOVA, ["23", "91", "01", "92"]),  # Краснодар, Крым, Адыгея, Севастополь
    # Новые территории (коды ФНС подтверждены пользователем).
    ("Новые территории", LOPATINA, ["93", "94", "90"]),  # ДНР, ЛНР, Запорожская
]

# Правила по стране (для зарубежных клиентов — ИНН РФ отсутствует).
COUNTRY_GROUPS = [
    ("Беларусь", LOPATINA),
    ("Казахстан", LOPATINA),
]

# Резервные получатели, если регион/страна не определены.
FALLBACK = [CHERNOV, ADMIN]


def seed(apps, schema_editor):
    Rule = apps.get_model("common", "ManagerRoutingRule")

    for district, (name, email), codes in REGION_GROUPS:
        for code in codes:
            Rule.objects.get_or_create(
                match_type="inn_region",
                match_value=code,
                manager_email=email,
                defaults={"manager_name": name, "federal_district": district},
            )

    for country, (name, email) in COUNTRY_GROUPS:
        Rule.objects.get_or_create(
            match_type="country",
            match_value=country,
            manager_email=email,
            defaults={"manager_name": name, "federal_district": country},
        )

    for name, email in FALLBACK:
        Rule.objects.get_or_create(
            match_type="fallback",
            match_value="default",
            manager_email=email,
            defaults={"manager_name": name, "federal_district": ""},
        )


def unseed(apps, schema_editor):
    Rule = apps.get_model("common", "ManagerRoutingRule")
    Rule.objects.all().delete()


class Migration(migrations.Migration):
    dependencies = [
        ("common", "0017_managerroutingrule"),
    ]

    operations = [
        migrations.RunPython(seed, unseed),
    ]
