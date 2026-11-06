"""
Integration-тесты раздела маркетинга `/marketing/` (стори 42.6).

Покрывает:
- AC1 — вход: маркетолог и руководитель пускаются, остальные роли,
  суперпользователь (в том числе в группе «Маркетинг»), аноним — нет;
- AC2 — рубрика, новость, статья и баннер, созданные в разделе, видны в
  публичном API; нет ссылки «Смотреть на сайте»;
- AC3 — рубрику с новостями или дочерними рубриками удалить нельзя;
- AC4/AC5 — список и карточка товара: белый список, правятся только метки;
- AC6 — сохраняются только изменённые поля, чужие правки не возвращаются;
- AC7 — бренды; AC8 — категории главной; AC9 — главная с подписчиками;
- AC10 — отказ по прямым URL; AC11 — права внутри раздела при одних `view_*`;
- AC12 — ссылки и редиректы ведут в раздел; AC13 — число запросов;
- AC16 — очистка HTML новостей и блога.

Тесты транзакционные: сброс кэша избранных брендов и сброс главной идут через
`transaction.on_commit`. Правки прав группы стирает `flush`, следующий тест
заново получает группы из `role_groups`.
"""

from __future__ import annotations

import io
import re
from datetime import timedelta
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest
from django import forms
from django.conf import settings
from django.contrib.admin.models import LogEntry
from django.contrib.admin.utils import label_for_field
from django.contrib.auth.models import Group, Permission
from django.core.files.base import ContentFile
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.utils import timezone
from PIL import Image
from rest_framework.test import APIClient

from apps.banners.models import Banner
from apps.common.models import BlogPost
from apps.common.models import Category as ContentCategory
from apps.common.models import News, Newsletter
from apps.products.factories import BrandFactory, CategoryFactory, ProductFactory, ProductVariantFactory
from apps.products.models import Brand, Category, Product
from apps.users.models import User
from apps.users.staff_roles import MANAGERS_GROUP, MARKETING_GROUP, SUPERVISORS_GROUP
from freesport.admin_site import marketing_site
from tests.conftest import get_unique_suffix
from tests.integration.test_manager_clients_section import (  # noqa: F401 — autouse-фикстура групп
    PASSWORD,
    make_staff_member,
    message_texts,
    role_groups,
)

pytestmark = [pytest.mark.integration, pytest.mark.django_db(transaction=True)]

INDEX_URL = "/marketing/"
PRODUCTS_URL = "/marketing/products/product/"
BRANDS_URL = "/marketing/products/brand/"
HOMEPAGE_URL = "/marketing/products/homepagecategory/"
RUBRICS_URL = "/marketing/common/category/"
NEWS_URL = "/marketing/common/news/"
BLOG_URL = "/marketing/common/blogpost/"
BANNERS_URL = "/marketing/banners/banner/"
LABELS = ("is_hit", "is_new", "is_sale", "is_promo", "is_premium")
# «Акция» выводится из акционных цен 1С и руками не правится
EDITABLE_LABELS = ("is_hit", "is_new", "is_sale", "is_premium")
LABEL_ACTIONS = [
    "mark_as_hit",
    "unmark_as_hit",
    "mark_as_new",
    "unmark_as_new",
    "mark_as_sale",
    "unmark_as_sale",
    "mark_as_premium",
    "unmark_as_premium",
]
# Карточка товара: в HTML нет ни поля, ни подписи (AC5).
HIDDEN_PRODUCT_FIELDS = (
    "onec_id",
    "parent_onec_id",
    "onec_brand_id",
    "sync_status",
    "last_sync_at",
    "error_message",
    "onec_deleted",
    "vat_rate",
    "slug",
    "specifications",
    "description",
    "short_description",
    "base_images",
    "seo_title",
    "seo_description",
    "is_featured",
    "min_order_quantity",
)
HIDDEN_PRODUCT_LABELS = (
    "Технические характеристики",
    "Ставка НДС (%)",
    "ID товара в 1С (SKU)",
    "Скрыт импортом 1С",
    "Базовые изображения",
    "Краткое описание",
    "Статус синхронизации",
)


# --------------------------------------------------------------------------
# Хелперы
# --------------------------------------------------------------------------


def png_bytes() -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (8, 8), color="red").save(buffer, format="PNG")
    return buffer.getvalue()


SVG_ICON = b'<svg xmlns="http://www.w3.org/2000/svg"><script>alert(document.cookie)</script></svg>'


def png_upload(name: str = "logo.png") -> SimpleUploadedFile:
    return SimpleUploadedFile(name, png_bytes(), content_type="image/png")


def _hidden_value(value: Any) -> str:
    return "" if value is None else str(value)


def _put_form_fields(data: dict[str, Any], form: forms.BaseForm) -> None:
    """Поля формы, как их отправил бы браузер, плюс скрытые «увиденные» значения."""
    for name, field in form.fields.items():
        if isinstance(field, forms.FileField):
            continue
        bound = form[name]
        value = bound.value()
        if field.show_hidden_initial:
            data[bound.html_initial_name] = _hidden_value(value)
        if value is None or value is False:
            continue
        data[bound.html_name] = "on" if value is True else value


def card_payload(response) -> dict[str, Any]:
    """POST-данные карточки из GET-ответа (без файлов и формсетов)."""
    data: dict[str, Any] = {}
    _put_form_fields(data, response.context["adminform"].form)
    return data


def changelist_payload(response) -> dict[str, Any]:
    """POST сохранения списка (`list_editable`) из GET-ответа."""
    formset = response.context["cl"].formset
    data: dict[str, Any] = {"_save": "Сохранить"}
    management = formset.management_form
    for name in management.fields:
        data[f"{formset.prefix}-{name}"] = management[name].value()
    for form in formset.forms:
        _put_form_fields(data, form)
    return data


def row_prefix(response, obj: Any) -> str:
    for form in response.context["cl"].formset.forms:
        if form.instance.pk == obj.pk:
            return form.prefix
    raise AssertionError(f"строки {obj.pk} нет в списке")


def set_checkbox(data: dict[str, Any], name: str, value: bool) -> None:
    if value:
        data[name] = "on"
    else:
        data.pop(name, None)


def change_url(base: str, obj: Any) -> str:
    return f"{base}{obj.pk}/change/"


def results(response_json: Any) -> list[dict[str, Any]]:
    return response_json["results"] if isinstance(response_json, dict) else response_json


def make_product(*, photo: bool = True, category: Category | None = None, **overrides: Any) -> Product:
    """Товар с одним вариантом; `photo` — у варианта есть основное изображение."""
    if category is not None:
        overrides["category"] = category
    if photo:
        overrides["main_image"] = f"products/variants/{get_unique_suffix()}.png"
    return ProductFactory(**overrides)


def category_chain(depth: int = 4) -> Category:
    """Ветка каталога заданной глубины, возвращает лист."""
    node = None
    for _ in range(depth):
        node = CategoryFactory(parent=node)
    assert node is not None
    return node


def section_permissions(*codenames: str) -> list[Permission]:
    return list(Permission.objects.filter(codename__in=codenames))


# --------------------------------------------------------------------------
# Фикстуры
# --------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def media_root(settings, tmp_path):
    """Загрузки логотипов и картинок не пишутся в рабочий media/."""
    settings.MEDIA_ROOT = str(tmp_path)


@pytest.fixture
def marketer() -> User:
    return make_staff_member(MARKETING_GROUP)


@pytest.fixture
def marketer_client(client, marketer):
    client.force_login(marketer)
    return client


@pytest.fixture(params=[MARKETING_GROUP, SUPERVISORS_GROUP], ids=["marketing", "supervisor"])
def section_member(request) -> User:
    return make_staff_member(request.param)


@pytest.fixture
def section_client(client, section_member):
    client.force_login(section_member)
    return client


@pytest.fixture
def showcase() -> dict[str, Category]:
    """Якорь витрины, два корня витрины, подкатегория и категория вне якоря."""
    anchor = Category.objects.filter(name=settings.ROOT_CATEGORY_NAME, parent__isnull=True).first()
    if anchor is None:
        anchor = CategoryFactory(name=settings.ROOT_CATEGORY_NAME, parent=None)
    first = CategoryFactory(parent=anchor, sort_order=1)
    second = CategoryFactory(parent=anchor, sort_order=2)
    return {
        "anchor": anchor,
        "first": first,
        "second": second,
        "sub": CategoryFactory(parent=first, sort_order=3),
        "outside": CategoryFactory(parent=None, sort_order=4),
    }


@pytest.fixture
def home_reset():
    with patch("apps.products.signals.revalidate_nextjs_path_in_background") as reset:
        yield reset


# --------------------------------------------------------------------------
# AC1 — вход
# --------------------------------------------------------------------------


class TestEntry:
    @pytest.mark.parametrize("group_name", [MARKETING_GROUP, SUPERVISORS_GROUP])
    def test_marketer_and_supervisor_enter(self, client, group_name):
        client.force_login(make_staff_member(group_name))

        for url in (INDEX_URL, PRODUCTS_URL):
            response = client.get(url)
            assert response.status_code == 200, url
            assert "OPTISPORT — Маркетинг" in response.content.decode()

    @pytest.mark.parametrize(
        "make_user",
        [
            pytest.param(lambda: make_staff_member(MANAGERS_GROUP), id="manager"),
            pytest.param(lambda: make_staff_member(None), id="staff-without-group"),
            pytest.param(lambda: make_staff_member(MARKETING_GROUP, is_active=False), id="blocked-marketer"),
            pytest.param(lambda: make_staff_member(MARKETING_GROUP, is_staff=False), id="marketer-without-is-staff"),
            pytest.param(
                lambda: User.objects.create_superuser(email=f"su_{get_unique_suffix()}@example.com", password=PASSWORD),
                id="superuser",
            ),
            pytest.param(
                lambda: make_staff_member(MARKETING_GROUP, is_superuser=True),
                id="superuser-in-marketing-group",
            ),
            pytest.param(None, id="anonymous"),
        ],
    )
    def test_others_are_redirected_to_login(self, client, make_user):
        if make_user is not None:
            client.force_login(make_user())

        for url in (INDEX_URL, PRODUCTS_URL):
            response = client.get(url)
            assert response.status_code == 302, url
            assert response.url.startswith("/marketing/login/"), response.url

    def test_superuser_keeps_admin(self, client):
        client.force_login(make_staff_member(MARKETING_GROUP, is_superuser=True))

        assert client.get("/admin/").status_code == 200

    def test_marketer_has_no_manager_section(self, marketer_client):
        response = marketer_client.get("/manager/")

        assert response.status_code == 302
        assert response.url.startswith("/manager/login/")


# --------------------------------------------------------------------------
# AC2 — контент
# --------------------------------------------------------------------------


def _datetime_fields(name: str, value) -> dict[str, str]:
    local = timezone.localtime(value)
    return {f"{name}_0": local.strftime("%Y-%m-%d"), f"{name}_1": local.strftime("%H:%M:%S")}


def rubric_post(name: str, parent: ContentCategory | None = None) -> dict[str, Any]:
    slug = f"rubric-{get_unique_suffix()}"
    data = {"name": name, "slug": slug, "description": "", "meta_keywords": "", "meta_description": ""}
    data["is_active"] = "on"
    if parent is not None:
        data["parent"] = str(parent.pk)
    return data


def news_post(title: str, category: ContentCategory, published_at, **extra: Any) -> dict[str, Any]:
    data = {
        "title": title,
        "slug": f"news-{get_unique_suffix()}",
        "category": str(category.pk),
        "author": "",
        "excerpt": "Анонс",
        "content": "<p>Текст новости</p>",
        "is_published": "on",
        **_datetime_fields("published_at", published_at),
    }
    data.update(extra)
    return data


def blog_post(title: str, category: ContentCategory, published_at, *, published: bool = True, **extra: Any):
    data = {
        "title": title,
        "slug": f"blog-{get_unique_suffix()}",
        "subtitle": "",
        "category": str(category.pk),
        "author": "",
        "excerpt": "Анонс",
        "content": "<p>Текст статьи</p>",
        "meta_title": "",
        "meta_description": "",
        **_datetime_fields("published_at", published_at),
    }
    if published:
        data["is_published"] = "on"
    data.update(extra)
    return data


def banner_post(title: str, start, end) -> dict[str, Any]:
    return {
        "type": "marketing",
        "title": title,
        "subtitle": "",
        "image": png_upload("banner.png"),
        "image_alt": "",
        "cta_text": "Подробнее",
        "cta_link": "/catalog",
        "show_to_guests": "on",
        "advertiser_name": "",
        "advertiser_inn": "",
        "erid": "",
        "is_active": "on",
        "priority": "0",
        **_datetime_fields("start_date", start),
        **_datetime_fields("end_date", end),
    }


def assert_saved(response) -> None:
    if response.status_code != 302:
        form = response.context["adminform"].form
        raise AssertionError(f"форма не сохранена: {form.errors}")


class TestContent:
    def test_create_rubric_news_blog_banner(self, marketer_client):
        now = timezone.now()
        api = APIClient()

        assert_saved(marketer_client.post(f"{RUBRICS_URL}add/", rubric_post("Соревнования")))
        rubric = ContentCategory.objects.get(name="Соревнования")

        assert_saved(
            marketer_client.post(f"{NEWS_URL}add/", news_post("Новость дня", rubric, now - timedelta(hours=1)))
        )
        assert_saved(marketer_client.post(f"{NEWS_URL}add/", news_post("Будущая", rubric, now + timedelta(days=2))))
        assert_saved(marketer_client.post(f"{BLOG_URL}add/", blog_post("Статья дня", rubric, now - timedelta(hours=1))))
        assert_saved(
            marketer_client.post(
                f"{BLOG_URL}add/", blog_post("Черновик", rubric, now - timedelta(hours=1), published=False)
            )
        )
        assert_saved(
            marketer_client.post(
                f"{BANNERS_URL}add/", banner_post("Акция недели", now - timedelta(days=1), now + timedelta(days=1))
            )
        )
        assert_saved(
            marketer_client.post(
                f"{BANNERS_URL}add/", banner_post("Прошлая акция", now - timedelta(days=5), now - timedelta(days=1))
            )
        )

        news = results(api.get("/api/v1/news/").json())
        assert [item["title"] for item in news] == ["Новость дня"]
        assert news[0]["category"]["slug"] == rubric.slug

        blog = results(api.get("/api/v1/blog/").json())
        assert [item["title"] for item in blog] == ["Статья дня"]
        assert blog[0]["category"]["slug"] == rubric.slug

        banners = api.get("/api/v1/banners/", {"type": "marketing"}).json()
        assert [item["title"] for item in results(banners)] == ["Акция недели"]

    @pytest.mark.parametrize(
        "make_obj, base",
        [
            pytest.param(
                lambda r: News.objects.create(title="Н", slug=f"n-{get_unique_suffix()}", content="x", category=r),
                NEWS_URL,
                id="news",
            ),
            pytest.param(
                lambda r: BlogPost.objects.create(title="С", slug=f"b-{get_unique_suffix()}", content="x", category=r),
                BLOG_URL,
                id="blog",
            ),
            pytest.param(lambda r: r, RUBRICS_URL, id="rubric"),
        ],
    )
    def test_no_view_on_site_link(self, marketer_client, make_obj, base):
        rubric = ContentCategory.objects.create(name=f"Рубрика {get_unique_suffix()}", slug=f"r-{get_unique_suffix()}")
        obj = make_obj(rubric)

        response = marketer_client.get(change_url(base, obj))

        assert response.status_code == 200
        assert response.context["has_absolute_url"] is False
        assert "viewsitelink" not in response.content.decode()


# --------------------------------------------------------------------------
# AC3 — удаление рубрики
# --------------------------------------------------------------------------


def make_rubric(name: str, parent: ContentCategory | None = None) -> ContentCategory:
    return ContentCategory.objects.create(name=name, slug=f"r-{get_unique_suffix()}", parent=parent)


class TestRubricDelete:
    @pytest.fixture
    def rubrics(self) -> dict[str, Any]:
        with_news = make_rubric("С новостью")
        news = News.objects.create(
            title="Новость рубрики", slug=f"n-{get_unique_suffix()}", content="x", category=with_news
        )
        with_child = make_rubric("С дочерней")
        child = make_rubric("Дочерняя", parent=with_child)
        with_post = make_rubric("Со статьёй")
        post = BlogPost.objects.create(title="Статья", slug=f"b-{get_unique_suffix()}", content="x", category=with_post)
        empty = make_rubric("Пустая")
        return {
            "with_news": with_news,
            "news": news,
            "with_child": with_child,
            "child": child,
            "with_post": with_post,
            "post": post,
            "empty": empty,
        }

    def test_card_delete(self, marketer_client, rubrics):
        for key, protected_line in (("with_news", "Новость: Новость рубрики"), ("with_child", "Рубрика: Дочерняя")):
            url = f"{RUBRICS_URL}{rubrics[key].pk}/delete/"
            page = marketer_client.get(url)
            assert page.status_code == 200
            assert protected_line in page.context["protected"]

            response = marketer_client.post(url, {"post": "yes"})
            assert response.status_code == 200
            assert ContentCategory.objects.filter(pk=rubrics[key].pk).exists()

        assert News.objects.filter(pk=rubrics["news"].pk).exists()
        assert ContentCategory.objects.filter(pk=rubrics["child"].pk).exists()

        for key in ("with_post", "empty"):
            response = marketer_client.post(f"{RUBRICS_URL}{rubrics[key].pk}/delete/", {"post": "yes"})
            assert response.status_code == 302
            assert not ContentCategory.objects.filter(pk=rubrics[key].pk).exists()

        post = BlogPost.objects.get(pk=rubrics["post"].pk)
        assert post.category is None

    def test_bulk_delete(self, marketer_client, rubrics):
        ids = [str(rubrics[key].pk) for key in ("with_news", "with_child", "with_post", "empty")]

        response = marketer_client.post(
            RUBRICS_URL, {"action": "delete_selected", "_selected_action": ids, "post": "yes"}
        )

        assert response.status_code == 200
        assert {"Новость: Новость рубрики", "Рубрика: Дочерняя"} <= set(response.context["protected"])
        assert ContentCategory.objects.filter(pk__in=ids).count() == 4

        ok = [str(rubrics[key].pk) for key in ("with_post", "empty")]
        response = marketer_client.post(
            RUBRICS_URL, {"action": "delete_selected", "_selected_action": ok, "post": "yes"}
        )
        assert response.status_code == 302
        assert not ContentCategory.objects.filter(pk__in=ok).exists()

    def test_parent_with_child_with_news(self, marketer_client):
        """Дочерняя рубрика выбрана вместе с родителем — её новости всё равно защищают удаление."""
        parent = make_rubric("Родитель")
        child = make_rubric("Ребёнок", parent=parent)
        News.objects.create(title="Новость ребёнка", slug=f"n-{get_unique_suffix()}", content="x", category=child)

        response = marketer_client.post(
            RUBRICS_URL,
            {"action": "delete_selected", "_selected_action": [str(parent.pk), str(child.pk)], "post": "yes"},
        )

        assert response.status_code == 200
        assert response.context["protected"] == ["Новость: Новость ребёнка"]
        assert ContentCategory.objects.filter(pk__in=[parent.pk, child.pk]).count() == 2

    def test_superuser_sees_rubrics_in_admin(self, client):
        make_rubric("Видна в админке")
        client.force_login(
            User.objects.create_superuser(email=f"su_{get_unique_suffix()}@example.com", password=PASSWORD)
        )

        response = client.get("/admin/common/category/")

        assert response.status_code == 200
        assert "Видна в админке" in response.content.decode()


# --------------------------------------------------------------------------
# AC4 — список товаров
# --------------------------------------------------------------------------


class TestProductChangelist:
    def test_columns_filters_and_rows(self, marketer_client):
        leaf = category_chain(3)
        product = make_product(category=leaf, retail_price="98765.43", stock_quantity=4321)
        # Фильтр по связи выводится, только если выбирать есть из чего — второй бренд.
        make_product(category=leaf)

        response = marketer_client.get(PRODUCTS_URL)

        assert response.status_code == 200
        cl = response.context["cl"]
        labels = [
            label_for_field(name, Product, cl.model_admin) for name in cl.list_display if name != "action_checkbox"
        ]
        assert labels == [
            "Фото",
            "Название",
            "Бренд",
            "Категория",
            "Активный",
            "Хит продаж",
            "Новинка",
            "Распродажа",
            "Акция",
            "Премиум",
            "Процент скидки",
        ]
        assert [spec.title for spec in cl.filter_specs] == [
            "Хит продаж",
            "Новинка",
            "Распродажа",
            "Акция",
            "Премиум",
            "Бренд",
            "Категория",
        ]
        html = response.content.decode()
        prefix = row_prefix(response, product)
        for label in EDITABLE_LABELS:
            assert f'name="{prefix}-{label}"' in html
        assert f'name="{prefix}-is_promo"' not in html
        assert f'name="{prefix}-discount_percent"' not in html

        category_filter = cl.filter_specs[-1]
        path = dict(category_filter.lookup_choices)[leaf.pk]
        assert path == f"{leaf.parent.parent.name} > {leaf.parent.name} > {leaf.name}"
        assert f'<td class="field-category_name">{leaf.name}</td>' in html

        choices = [value for value, _ in response.context["action_form"].fields["action"].choices if value]
        assert choices == LABEL_ACTIONS

        for needle in ("РРЦ", "МРЦ", "98765", "4321", "onec_id", "НДС", "retail_price", "stock_quantity"):
            assert needle not in html, needle

    @pytest.mark.parametrize(
        ("photo", "base_image", "expected"),
        [
            (True, "/products/b.png", "/media/products/b.png"),
            (False, "/products/b.png", "/media/products/b.png"),
            (False, "/media/products/b.png", "/media/products/b.png"),
            (False, "http://cdn.example.com/b.png", "http://cdn.example.com/b.png"),
            (False, "https://cdn.example.com/b.png", "https://cdn.example.com/b.png"),
            (False, "uploads/b.png", "/media/uploads/b.png"),
            (False, "/uploads/b.png", "/media/uploads/b.png"),
        ],
    )
    def test_photo_src(self, marketer_client, photo, base_image, expected):
        """Первое фото 1С (base_images) важнее фото варианта; путь приводится к /media/."""
        make_product(photo=photo, base_images=[base_image])

        html = marketer_client.get(PRODUCTS_URL).content.decode()

        assert re.findall(r'<img src="([^"]*)" style="max-height:50px', html) == [expected]

    def test_photo_of_variant_without_base_images(self, marketer_client):
        """Без base_images — фото варианта."""
        product = make_product(base_images=[])

        html = marketer_client.get(PRODUCTS_URL).content.decode()

        assert re.findall(r'<img src="([^"]*)" style="max-height:50px', html) == [
            f"{settings.MEDIA_URL}{product.variants.get().main_image.name}"
        ]

    def test_photo_of_first_variant_with_photo(self, marketer_client):
        """Из нескольких вариантов с фото — вариант с меньшим pk; вариант без фото пропускается."""
        product = make_product(photo=False, base_images=[])
        first, second = (
            ProductVariantFactory(product=product, main_image=f"products/variants/{get_unique_suffix()}.png")
            for _ in range(2)
        )
        assert first.pk < second.pk

        html = marketer_client.get(PRODUCTS_URL).content.decode()

        assert re.findall(r'<img src="([^"]*)" style="max-height:50px', html) == [
            f"{settings.MEDIA_URL}{first.main_image.name}"
        ]

    def test_list_save_and_action(self, marketer_client):
        a, b, c, untouched = (make_product(is_new=True) for _ in range(4))

        page = marketer_client.get(PRODUCTS_URL)
        data = changelist_payload(page)
        set_checkbox(data, f"{row_prefix(page, a)}-is_hit", True)
        response = marketer_client.post(PRODUCTS_URL, data)
        assert response.status_code == 302

        response = marketer_client.post(
            PRODUCTS_URL, {"action": "unmark_as_new", "_selected_action": [str(b.pk), str(c.pk)]}
        )
        assert response.status_code == 302

        a.refresh_from_db()
        b.refresh_from_db()
        c.refresh_from_db()
        untouched.refresh_from_db()
        assert a.is_hit is True and a.is_new is True
        assert b.is_new is False and c.is_new is False
        assert b.is_hit is False and c.is_hit is False
        assert untouched.is_new is True and untouched.is_hit is False


# --------------------------------------------------------------------------
# AC5 — карточка товара
# --------------------------------------------------------------------------


class TestProductCard:
    def test_card_whitelist(self, marketer_client):
        product = make_product()

        response = marketer_client.get(change_url(PRODUCTS_URL, product))

        assert response.status_code == 200
        assert list(response.context["adminform"].form.fields) == list(EDITABLE_LABELS)
        html = response.content.decode()
        for name in HIDDEN_PRODUCT_FIELDS:
            assert f'name="{name}"' not in html, name
        for label in HIDDEN_PRODUCT_LABELS:
            assert label not in html, label
        assert "variants-TOTAL_FORMS" not in html
        assert "images-TOTAL_FORMS" not in html
        assert f'href="/marketing/products/brand/{product.brand_id}/change/"' in html
        assert product.brand.name in html
        assert product.category.name in html
        assert "/products/category/" not in html
        assert response.context["has_add_permission"] is False
        assert response.context["has_delete_permission"] is False
        assert f'href="{PRODUCTS_URL}{product.pk}/delete/"' not in html
        assert f'href="{PRODUCTS_URL}add/"' not in html

    def test_forged_post_changes_only_label(self, marketer_client):
        product = make_product(discount_percent=10)
        other_brand = BrandFactory()
        other_category = CategoryFactory()
        before = Product.objects.values().get(pk=product.pk)

        page = marketer_client.get(change_url(PRODUCTS_URL, product))
        data = card_payload(page)
        data.update(
            {
                "is_hit": "on",
                "name": "Подделка",
                "description": "Подделка",
                "slug": "poddelka",
                "vat_rate": "0",
                "onec_id": "forged",
                "discount_percent": "99",
                "brand": str(other_brand.pk),
                "category": str(other_category.pk),
                "specifications": '{"a": 1}',
            }
        )
        data.pop("is_active", None)
        response = marketer_client.post(change_url(PRODUCTS_URL, product), data)

        assert response.status_code == 302
        after = Product.objects.values().get(pk=product.pk)
        assert after["is_hit"] is True
        changed = {key for key in before if before[key] != after[key]}
        assert changed == {"is_hit", "updated_at"}


# --------------------------------------------------------------------------
# AC6 — только изменённые поля
# --------------------------------------------------------------------------


class TestChangedFieldsOnly:
    def test_card_keeps_import_changes(self, marketer_client):
        product = make_product()
        page = marketer_client.get(change_url(PRODUCTS_URL, product))
        # Импорт 1С пишет строку, пока карточка открыта.
        Product.objects.filter(pk=product.pk).update(name="Имя из 1С", description="Описание из 1С")

        data = card_payload(page)
        data["is_sale"] = "on"
        original_save = Product.save
        with patch.object(Product, "save", autospec=True, side_effect=original_save) as save:
            response = marketer_client.post(change_url(PRODUCTS_URL, product), data)

        assert response.status_code == 302
        assert save.call_count == 1
        assert save.call_args.kwargs["update_fields"] == ["is_sale", "updated_at"]
        product.refresh_from_db()
        assert product.is_sale is True
        assert product.name == "Имя из 1С"
        assert product.description == "Описание из 1С"

    def test_unchanged_card_does_not_save(self, marketer_client):
        product = make_product()
        updated_at = Product.objects.get(pk=product.pk).updated_at
        page = marketer_client.get(change_url(PRODUCTS_URL, product))

        original_save = Product.save
        with patch.object(Product, "save", autospec=True, side_effect=original_save) as save:
            response = marketer_client.post(change_url(PRODUCTS_URL, product), card_payload(page))

        assert response.status_code == 302
        save.assert_not_called()
        assert Product.objects.get(pk=product.pk).updated_at == updated_at

    def test_list_save_keeps_colleague_label(self, marketer_client):
        x = make_product()
        y = make_product()
        page = marketer_client.get(PRODUCTS_URL)
        # Коллега ставит X «Хит» из своей карточки после открытия списка.
        Product.objects.filter(pk=x.pk).update(is_hit=True)

        data = changelist_payload(page)
        set_checkbox(data, f"{row_prefix(page, y)}-is_new", True)
        response = marketer_client.post(PRODUCTS_URL, data)

        assert response.status_code == 302
        x.refresh_from_db()
        y.refresh_from_db()
        assert x.is_hit is True
        assert y.is_new is True

    def test_brand_card_keeps_colleague_featured(self, marketer_client):
        brand = BrandFactory(is_featured=False, image="brands/logo.png", description="Старое")
        page = marketer_client.get(change_url(BRANDS_URL, brand))
        Brand.objects.filter(pk=brand.pk).update(is_featured=True)

        data = card_payload(page)
        data["description"] = "Новое описание"
        response = marketer_client.post(change_url(BRANDS_URL, brand), data)

        assert response.status_code == 302
        brand.refresh_from_db()
        assert brand.is_featured is True
        assert brand.description == "Новое описание"

    def test_homepage_list_keeps_colleague_order(self, marketer_client, showcase):
        x, y = showcase["first"], showcase["second"]
        page = marketer_client.get(HOMEPAGE_URL)
        Category.objects.filter(pk=x.pk).update(sort_order=7)

        data = changelist_payload(page)
        data[f"{row_prefix(page, y)}-sort_order"] = "9"
        response = marketer_client.post(HOMEPAGE_URL, data)

        assert response.status_code == 302
        assert Category.objects.get(pk=x.pk).sort_order == 7
        assert Category.objects.get(pk=y.pk).sort_order == 9


# --------------------------------------------------------------------------
# AC7 — бренды
# --------------------------------------------------------------------------


class TestBrands:
    def test_feature_with_logo(self, marketer_client, home_reset):
        brand = BrandFactory(is_featured=False, image="", is_active=True)
        APIClient().get("/api/v1/brands/featured/")  # кэш endpoint заполнен до правки
        page = marketer_client.get(change_url(BRANDS_URL, brand))
        home_reset.reset_mock()

        data = card_payload(page)
        data["is_featured"] = "on"
        data["image"] = png_upload()
        response = marketer_client.post(change_url(BRANDS_URL, brand), data)

        assert response.status_code == 302
        brand.refresh_from_db()
        assert brand.is_featured is True
        assert brand.image
        featured = APIClient().get("/api/v1/brands/featured/").json()
        assert brand.slug in [item["slug"] for item in featured]
        home_reset.assert_called_once_with("/home")

    def test_feature_without_logo_is_rejected(self, marketer_client):
        brand = BrandFactory(is_featured=False, image="")
        page = marketer_client.get(change_url(BRANDS_URL, brand))

        data = card_payload(page)
        data["is_featured"] = "on"
        response = marketer_client.post(change_url(BRANDS_URL, brand), data)

        assert response.status_code == 200
        assert "Для показа на главной нужен логотип" in response.content.decode()
        brand.refresh_from_db()
        assert brand.is_featured is False

    def test_not_featured_edit_does_not_reset_home(self, marketer_client, home_reset):
        brand = BrandFactory(is_featured=False)
        page = marketer_client.get(change_url(BRANDS_URL, brand))
        home_reset.reset_mock()

        data = card_payload(page)
        data["description"] = "Другое описание"
        assert marketer_client.post(change_url(BRANDS_URL, brand), data).status_code == 302

        home_reset.assert_not_called()

    def test_next_failure_does_not_break_save(self, marketer_client, settings, caplog):
        from apps.common.services.nextjs_revalidate import revalidate_nextjs_path

        settings.FRONTEND_INTERNAL_URL = "http://frontend:3000"
        settings.REVALIDATE_SECRET = "s3cret"
        brand = BrandFactory(is_featured=True, image="brands/logo.png")
        page = marketer_client.get(change_url(BRANDS_URL, brand))
        data = card_payload(page)
        data["description"] = "После сбоя Next"

        # Сброс — синхронно, чтобы увидеть исход в этом же тесте.
        with (
            patch("apps.products.signals.revalidate_nextjs_path_in_background", side_effect=revalidate_nextjs_path),
            patch("apps.common.services.nextjs_revalidate.requests.post", side_effect=OSError("refused")),
            caplog.at_level("WARNING", logger="apps.common.services.nextjs_revalidate"),
        ):
            response = marketer_client.post(change_url(BRANDS_URL, brand), data)

        assert response.status_code == 302
        assert Brand.objects.get(pk=brand.pk).description == "После сбоя Next"
        assert "Next.js revalidation failed for /home: refused" in caplog.text

    def test_card_and_list_whitelist(self, marketer_client):
        brand = BrandFactory(is_featured=False)

        card = marketer_client.get(change_url(BRANDS_URL, brand))
        html = card.content.decode()
        assert sorted(card.context["adminform"].form.fields) == ["description", "image", "is_featured"]
        for name in ("slug", "normalized_name", "website", "name", "is_active"):
            assert f'name="{name}"' not in html, name
        assert "onec_mappings-TOTAL_FORMS" not in html
        assert card.context["has_add_permission"] is False
        assert card.context["has_delete_permission"] is False

        listing = marketer_client.get(BRANDS_URL)
        list_html = listing.content.decode()
        assert "Маппинги 1С" not in list_html
        assert "merge_brands" not in list_html
        assert listing.context["action_form"] is None
        assert listing.context["has_add_permission"] is False


# --------------------------------------------------------------------------
# AC8 — категории на главной
# --------------------------------------------------------------------------


class TestHomepageCategories:
    def test_list_contains_only_showcase_roots(self, marketer_client, showcase):
        response = marketer_client.get(HOMEPAGE_URL)

        assert response.status_code == 200
        rows = {obj.pk for obj in response.context["cl"].result_list}
        assert rows == {showcase["first"].pk, showcase["second"].pk}
        html = response.content.decode()
        prefix = row_prefix(response, showcase["first"])
        assert f'name="{prefix}-sort_order"' in html
        assert not re.search(r'name="form-\d+-is_active"', html)

    def test_edit_order_icon_and_image(self, marketer_client, showcase):
        target = showcase["first"]
        page = marketer_client.get(HOMEPAGE_URL)
        data = changelist_payload(page)
        data[f"{row_prefix(page, target)}-sort_order"] = "5"
        assert marketer_client.post(HOMEPAGE_URL, data).status_code == 302
        assert Category.objects.get(pk=target.pk).sort_order == 5

        card = marketer_client.get(change_url(HOMEPAGE_URL, target))
        html = card.content.decode()
        assert 'name="is_active"' not in html
        assert 'name="name"' not in html
        assert 'name="parent"' not in html
        data = card_payload(card)
        data["icon"] = png_upload("icon.png")
        data["image"] = png_upload("image.png")
        assert marketer_client.post(change_url(HOMEPAGE_URL, target), data).status_code == 302

        target.refresh_from_db()
        assert target.icon.name.startswith("categories/icons/")
        assert target.image
        assert target.sort_order == 5

    def test_forged_is_active_is_ignored(self, marketer_client, showcase):
        target = showcase["first"]

        card = marketer_client.get(change_url(HOMEPAGE_URL, target))
        data = card_payload(card)
        data.pop("is_active", None)
        data["sort_order"] = "6"
        assert marketer_client.post(change_url(HOMEPAGE_URL, target), data).status_code == 302
        assert Category.objects.get(pk=target.pk).is_active is True

        page = marketer_client.get(HOMEPAGE_URL)
        data = changelist_payload(page)
        prefix = row_prefix(page, target)
        data[f"{prefix}-sort_order"] = "8"
        data[f"{prefix}-is_active"] = ""
        data[f"initial-{prefix}-is_active"] = "True"
        assert marketer_client.post(HOMEPAGE_URL, data).status_code == 302
        target.refresh_from_db()
        assert target.is_active is True
        assert target.sort_order == 8

    def test_zero_order_hides_from_homepage(self, marketer_client, showcase):
        target = showcase["first"]
        api = APIClient()

        def homepage_ids() -> set[int]:
            return {item["id"] for item in results(api.get("/api/v1/categories/", {"is_homepage": "true"}).json())}

        assert target.pk in homepage_ids()
        for value, visible in (("0", False), ("3", True)):
            page = marketer_client.get(HOMEPAGE_URL)
            data = changelist_payload(page)
            data[f"{row_prefix(page, target)}-sort_order"] = value
            assert marketer_client.post(HOMEPAGE_URL, data).status_code == 302
            assert (target.pk in homepage_ids()) is visible

    @pytest.mark.parametrize(
        ("name", "content", "content_type"),
        [
            pytest.param("icon.html", b"<script>alert(document.cookie)</script>", "text/html", id="html"),
            pytest.param("icon.svg", SVG_ICON, "image/svg+xml", id="svg"),
            pytest.param("icon.png", b"<html><script>alert(1)</script></html>", "image/png", id="html-as-png"),
            pytest.param("icon.svg", png_bytes(), "image/svg+xml", id="png-as-svg"),
            pytest.param("icon.html", png_bytes(), "text/html", id="png-as-html"),
        ],
    )
    def test_icon_must_be_raster_image(self, marketer_client, showcase, name, content, content_type):
        """Иконка открывается по /media/ на origin сайта: в разделе — только растровые форматы (R42.6-2)."""
        target = showcase["first"]
        card = marketer_client.get(change_url(HOMEPAGE_URL, target))
        data = card_payload(card)
        data["icon"] = SimpleUploadedFile(name, content, content_type=content_type)

        response = marketer_client.post(change_url(HOMEPAGE_URL, target), data)

        assert response.status_code == 200
        assert "icon" in response.context["adminform"].form.errors
        target.refresh_from_db()
        assert not target.icon
        assert not Path(settings.MEDIA_ROOT, "categories", "icons").exists()

    def test_superuser_uploads_svg_icon_in_admin(self, client, showcase):
        """В /admin/ проверки нет: SVG-иконки загружает суперпользователь."""
        client.force_login(make_staff_member(MARKETING_GROUP, is_superuser=True))
        target = showcase["first"]
        url = change_url("/admin/products/homepagecategory/", target)
        data = card_payload(client.get(url))
        data["icon"] = SimpleUploadedFile("icon.svg", SVG_ICON, content_type="image/svg+xml")

        assert client.post(url, data).status_code == 302
        target.refresh_from_db()
        assert target.icon.name.startswith("categories/icons/")
        assert target.icon.name.endswith(".svg")

    def test_edit_card_preserves_existing_svg_icon(self, marketer_client, showcase):
        """Прежнюю SVG-иконку владельца проверка не трогает: маркетолог правит порядок (R42.6-7)."""
        target = showcase["first"]
        target.icon.save("icon.svg", ContentFile(SVG_ICON))
        icon_name = target.icon.name

        card = marketer_client.get(change_url(HOMEPAGE_URL, target))
        data = card_payload(card)
        data["sort_order"] = "7"

        assert marketer_client.post(change_url(HOMEPAGE_URL, target), data).status_code == 302
        target.refresh_from_db()
        assert target.sort_order == 7
        assert target.icon.name == icon_name

    @pytest.mark.parametrize("key", ["sub", "outside"])
    def test_out_of_scope_card_is_404(self, marketer_client, showcase, key):
        response = marketer_client.get(change_url(HOMEPAGE_URL, showcase[key]))

        assert response.status_code == 404


# --------------------------------------------------------------------------
# AC9 — главная с подписчиками
# --------------------------------------------------------------------------


def subscribe(count: int, *, days_ago: float, active: bool = True) -> None:
    rows = [Newsletter(email=f"sub_{get_unique_suffix()}@example.com", is_active=active) for _ in range(count)]
    created = Newsletter.objects.bulk_create(rows)
    Newsletter.objects.filter(pk__in=[row.pk for row in created]).update(
        subscribed_at=timezone.now() - timedelta(days=days_ago),
        unsubscribed_at=None if active else timezone.now(),
    )


class TestIndex:
    def test_subscribers(self, section_client):
        subscribe(105, days_ago=60)
        subscribe(15, days_ago=3)
        subscribe(5, days_ago=60, active=False)
        subscribe(2, days_ago=3, active=False)

        response = section_client.get(INDEX_URL)

        assert response.status_code == 200
        assert "Подписчиков: 120 (+15 за 30 дней)" in response.content.decode()

    def test_no_subscribers(self, marketer_client):
        assert "Подписчиков: 0 (+0 за 30 дней)" in marketer_client.get(INDEX_URL).content.decode()

    def test_thirty_day_boundary(self, marketer_client):
        frozen = timezone.now()
        boundary = frozen - timedelta(days=30)
        moments = {
            "older-by-minute": boundary - timedelta(minutes=1),
            "exactly-30-days": boundary,
            "newer-by-minute": boundary + timedelta(minutes=1),
        }
        for label, moment in moments.items():
            row = Newsletter.objects.create(email=f"{label}_{get_unique_suffix()}@example.com")
            Newsletter.objects.filter(pk=row.pk).update(subscribed_at=moment)

        with patch("django.utils.timezone.now", return_value=frozen):
            html = marketer_client.get(INDEX_URL).content.decode()

        # Подписка 30 дней и минуту назад — вне прироста; ровно 30 дней и
        # 30 дней без минуты назад — в приросте.
        assert "Подписчиков: 3 (+2 за 30 дней)" in html

    def test_blocks(self, marketer_client):
        response = marketer_client.get(INDEX_URL)

        app_list = response.context["app_list"]
        assert sorted(app["name"] for app in app_list) == ["Баннеры", "Новости и блог", "Товары"]
        content = next(app for app in app_list if app["name"] == "Новости и блог")
        assert sorted(model["name"] for model in content["models"]) == ["Новости", "Рубрики", "Статьи блога"]
        assert "Последние действия" not in response.content.decode()


# --------------------------------------------------------------------------
# AC10 — отказ по прямым URL
# --------------------------------------------------------------------------


class TestDirectUrls:
    @pytest.mark.parametrize(
        "url, login",
        [
            ("/manager/", "/manager/login/"),
            ("/manager/users/user/", "/manager/login/"),
            ("/manager/orders/order/", "/manager/login/"),
            ("/admin/users/user/", "/admin/login/"),
            ("/admin/orders/order/", "/admin/login/"),
            ("/admin/pages/page/", "/admin/login/"),
            ("/admin/common/newsletter/", "/admin/login/"),
        ],
    )
    def test_other_sites_redirect_to_login(self, marketer_client, url, login):
        response = marketer_client.get(url)

        assert response.status_code == 302
        assert response.url.startswith(login), response.url

    @pytest.mark.parametrize(
        "url",
        [
            "/marketing/users/user/",
            "/marketing/orders/order/",
            "/marketing/pages/page/",
            "/marketing/common/newsletter/",
            "/marketing/products/category/",
            "/marketing/products/productvariant/",
            "/marketing/products/brand1cmapping/",
            "/marketing/common/auditlog/",
        ],
    )
    def test_unregistered_models_are_404(self, marketer_client, url):
        assert marketer_client.get(url).status_code == 404

    def test_add_and_delete_are_forbidden(self, marketer_client, showcase):
        product = make_product()
        brand = BrandFactory()
        category = showcase["first"]

        for url in (f"{PRODUCTS_URL}add/", f"{BRANDS_URL}add/", f"{HOMEPAGE_URL}add/"):
            assert marketer_client.get(url).status_code == 403, url
        for base, obj in ((PRODUCTS_URL, product), (BRANDS_URL, brand), (HOMEPAGE_URL, category)):
            url = f"{base}{obj.pk}/delete/"
            assert marketer_client.get(url).status_code == 403, url
            assert marketer_client.post(url, {"post": "yes"}).status_code == 403, url
        assert Product.objects.filter(pk=product.pk).exists()
        assert Brand.objects.filter(pk=brand.pk).exists()


# --------------------------------------------------------------------------
# AC11 — права внутри раздела
# --------------------------------------------------------------------------


VIEW_PERMISSIONS = (
    "view_banner",
    "view_news",
    "view_blogpost",
    "view_category",
    "view_product",
    "view_brand",
    "view_homepagecategory",
)


class TestViewOnlyGroup:
    @pytest.fixture(autouse=True)
    def view_only(self):
        Group.objects.get(name=MARKETING_GROUP).permissions.set(section_permissions(*VIEW_PERMISSIONS))

    def test_cards_are_read_only(self, marketer_client, showcase):
        product = make_product()
        brand = BrandFactory()
        for url in (
            change_url(PRODUCTS_URL, product),
            change_url(BRANDS_URL, brand),
            change_url(HOMEPAGE_URL, showcase["first"]),
        ):
            response = marketer_client.get(url)
            assert response.status_code == 200, url
            html = response.content.decode()
            for name in (*LABELS, "image", "icon", "is_featured", "description", "sort_order"):
                assert f'name="{name}"' not in html, (url, name)
            assert marketer_client.post(url, {"is_hit": "on", "description": "x", "sort_order": "1"}).status_code == 403

        product.refresh_from_db()
        assert product.is_hit is False

    def test_lists_have_no_inputs_and_no_actions(self, marketer_client, showcase):
        product = make_product()

        for url in (PRODUCTS_URL, BRANDS_URL, HOMEPAGE_URL):
            response = marketer_client.get(url)
            assert response.status_code == 200, url
            assert response.context["cl"].formset is None, url
            assert response.context["action_form"] is None, url
            html = response.content.decode()
            assert not re.search(r'name="form-\d+-(is_hit|is_featured|sort_order)"', html), url

        response = marketer_client.post(
            PRODUCTS_URL,
            {"_save": "Сохранить", "form-TOTAL_FORMS": "1", "form-INITIAL_FORMS": "1", "form-0-id": str(product.pk)},
        )
        assert response.status_code == 403

        marketer_client.post(PRODUCTS_URL, {"action": "mark_as_hit", "_selected_action": [str(product.pk)]})
        product.refresh_from_db()
        assert product.is_hit is False

    def test_index_hides_models_without_view(self, marketer_client):
        Group.objects.get(name=MARKETING_GROUP).permissions.set(section_permissions("view_product"))

        app_list = marketer_client.get(INDEX_URL).context["app_list"]

        assert [(app["name"], [m["object_name"] for m in app["models"]]) for app in app_list] == [
            ("Товары", ["Product"])
        ]


# --------------------------------------------------------------------------
# AC12 — ссылки раздела ведут в раздел
# --------------------------------------------------------------------------


class TestLinksStayInSection:
    def test_no_admin_links(self, marketer_client, showcase):
        product = make_product()
        brand = BrandFactory()
        rubric = make_rubric("Рубрика ссылок")
        news = News.objects.create(title="Н", slug=f"n-{get_unique_suffix()}", content="x", category=rubric)
        post = BlogPost.objects.create(title="С", slug=f"b-{get_unique_suffix()}", content="x", category=rubric)
        banner = Banner.objects.create(title="Б", type="marketing", cta_link="/catalog", image="promos/x.png")

        page = marketer_client.get(change_url(PRODUCTS_URL, product))
        data = card_payload(page)
        data["is_hit"] = "on"
        assert marketer_client.post(change_url(PRODUCTS_URL, product), data).status_code == 302
        assert LogEntry.objects.filter(object_id=str(product.pk)).exists()

        urls = [INDEX_URL, f"{PRODUCTS_URL}{product.pk}/history/"]
        for base, obj in (
            (PRODUCTS_URL, product),
            (BRANDS_URL, brand),
            (HOMEPAGE_URL, showcase["first"]),
            (RUBRICS_URL, rubric),
            (NEWS_URL, news),
            (BLOG_URL, post),
            (BANNERS_URL, banner),
        ):
            urls += [base, change_url(base, obj)]

        for url in urls:
            response = marketer_client.get(url)
            assert response.status_code == 200, url
            html = response.content.decode()
            assert 'href="/admin/' not in html, url
            assert "viewsitelink" not in html, url

    def test_redirects_after_save(self, marketer_client):
        product = make_product()
        url = change_url(PRODUCTS_URL, product)

        data = card_payload(marketer_client.get(url))
        response = marketer_client.post(url, {**data, "_save": "Сохранить"})
        assert response.url.startswith(PRODUCTS_URL)
        assert response.url.split("?")[0] == PRODUCTS_URL

        data = card_payload(marketer_client.get(url))
        response = marketer_client.post(url, {**data, "_continue": "Сохранить и продолжить"})
        assert response.url.split("?")[0] == url

    def test_add_rubric_link_in_news_card(self, marketer_client):
        html = marketer_client.get(f"{NEWS_URL}add/").content.decode()

        assert "/marketing/common/category/add/" in html


# --------------------------------------------------------------------------
# AC13 — число запросов
# --------------------------------------------------------------------------


def count_queries(client, url: str) -> tuple[int, Any]:
    with CaptureQueriesContext(connection) as captured:
        response = client.get(url)
    assert response.status_code == 200
    return len(captured), response


class TestQueryCount:
    def test_product_list_scales_with_products(self, marketer_client, django_assert_num_queries):
        def add(count: int) -> None:
            for index in range(count):
                make_product(category=category_chain(4), photo=index % 2 == 0, base_images=["/products/b.png"])

        add(5)
        baseline, first = count_queries(marketer_client, PRODUCTS_URL)
        assert len(first.context["cl"].result_list) == 5

        add(45)
        with django_assert_num_queries(baseline):
            second = marketer_client.get(PRODUCTS_URL)
        assert len(second.context["cl"].result_list) == 50
        assert second.content.decode().count("<img ") >= 50

    def test_category_filter_scales_with_categories(self, marketer_client, django_assert_num_queries):
        make_product(category=category_chain(4))

        def add_chains(count: int) -> None:
            for _ in range(count):
                category_chain(4)

        add_chains(4)
        baseline, _ = count_queries(marketer_client, PRODUCTS_URL)

        add_chains(45)
        with django_assert_num_queries(baseline):
            response = marketer_client.get(PRODUCTS_URL)
        assert len(response.context["cl"].filter_specs[-1].lookup_choices) == 50 * 4

    def test_brand_list(self, marketer_client, django_assert_num_queries):
        def add(count: int) -> None:
            for _ in range(count):
                BrandFactory(image="brands/logo.png")

        add(5)
        baseline, _ = count_queries(marketer_client, BRANDS_URL)
        add(45)
        with django_assert_num_queries(baseline):
            response = marketer_client.get(BRANDS_URL)
        assert len(response.context["cl"].result_list) == 50

    def test_homepage_list(self, marketer_client, showcase, django_assert_num_queries):
        def add(count: int) -> None:
            for _ in range(count):
                CategoryFactory(parent=showcase["anchor"], sort_order=1)

        add(1)
        baseline, first = count_queries(marketer_client, HOMEPAGE_URL)
        assert len(first.context["cl"].result_list) == 3
        add(9)
        with django_assert_num_queries(baseline):
            response = marketer_client.get(HOMEPAGE_URL)
        assert len(response.context["cl"].result_list) == 12

    def test_index(self, marketer_client, django_assert_num_queries):
        subscribe(3, days_ago=1)
        baseline, _ = count_queries(marketer_client, INDEX_URL)
        subscribe(27, days_ago=1)
        with django_assert_num_queries(baseline):
            response = marketer_client.get(INDEX_URL)
        assert "Подписчиков: 30 (+30 за 30 дней)" in response.content.decode()


# --------------------------------------------------------------------------
# AC16 — очистка HTML новостей и блога
# --------------------------------------------------------------------------


DANGEROUS_HTML = (
    "<script>alert(1)</script>"
    '<img src="x" onerror="alert(2)">'
    '<a href="javascript:alert(3)">клик</a>'
    '<iframe src="https://evil.example/frame"></iframe>'
    "<style>body{display:none}</style>"
    '<meta http-equiv="refresh" content="0;url=https://evil.example">'
    '<link rel="stylesheet" href="https://evil.example/x.css">'
)
ALLOWED_HTML = (
    '<h2>Итоги турнира</h2><p class="lead">Победили <strong>наши</strong></p>'
    '<ul><li>Первое место</li></ul><a href="https://optisport.ru/catalog">Каталог</a>'
)
FORBIDDEN_SUBSTRINGS = (
    "<script",
    "onerror",
    "javascript:",
    "<iframe",
    "<style",
    "body{display:none}",
    "<meta",
    "<link",
)


class TestHtmlSanitizing:
    @pytest.fixture(params=["marketing", "admin"])
    def author(self, request, client):
        if request.param == "marketing":
            client.force_login(make_staff_member(MARKETING_GROUP))
        else:
            client.force_login(
                User.objects.create_superuser(email=f"su_{get_unique_suffix()}@example.com", password=PASSWORD)
            )
        return client, f"/{request.param}/common/"

    @staticmethod
    def assert_clean(*values: str) -> None:
        for value in values:
            for needle in FORBIDDEN_SUBSTRINGS:
                assert needle not in value, needle
            assert '<h2>Итоги турнира</h2><p class="lead">Победили <strong>наши</strong></p>' in value
            assert '<ul><li>Первое место</li></ul><a href="https://optisport.ru/catalog">Каталог</a>' in value

    def test_news_and_blog_are_cleaned(self, author):
        client, base = author
        rubric = make_rubric(f"Рубрика {get_unique_suffix()}")
        published = timezone.now() - timedelta(hours=1)
        html = DANGEROUS_HTML + ALLOWED_HTML
        api = APIClient()

        news_data = news_post("Новость с HTML", rubric, published, content=html, excerpt=html)
        assert_saved(client.post(f"{base}news/add/", news_data))
        blog_data = blog_post("Статья с HTML", rubric, published, content=html, excerpt=html)
        assert_saved(client.post(f"{base}blogpost/add/", blog_data))

        news = News.objects.get(slug=news_data["slug"])
        post = BlogPost.objects.get(slug=blog_data["slug"])
        self.assert_clean(news.content, news.excerpt, post.content, post.excerpt)

        news_api = api.get(f"/api/v1/news/{news.slug}/").json()
        blog_api = api.get(f"/api/v1/blog/{post.slug}/").json()
        self.assert_clean(news_api["content"], news_api["excerpt"], blog_api["content"], blog_api["excerpt"])
