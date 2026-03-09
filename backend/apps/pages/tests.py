"""
Unit тесты для Pages app (Story 2.10)
Включает security тесты для HTML sanitization и XSS protection
"""

import pytest
from django.core.exceptions import ValidationError
from django.test import TestCase

from .models import Page


@pytest.mark.unit
class PageModelSecurityTest(TestCase):
    """Security тесты для модели Page - Fix SEC-001"""

    def test_xss_script_removal(self):
        """Тест удаления script тегов для предотвращения XSS"""
        dangerous_content = """
        <p>Нормальный контент</p>
        <script>alert('XSS Attack!');</script>
        <script src="http://malicious.com/evil.js"></script>
        <h2>Заголовок</h2>
        """

        page = Page.objects.create(title="Security Test", content=dangerous_content, is_published=True)

        # Script теги должны быть полностью удалены
        self.assertNotIn("<script>", page.content)
        self.assertNotIn("</script>", page.content)
        # Содержимое script тегов может остаться как обычный текст после strip=True
        # но опасные теги сами должны быть удалены

        # Безопасные теги должны остаться
        self.assertIn("<p>Нормальный контент</p>", page.content)
        self.assertIn("<h2>Заголовок</h2>", page.content)

    def test_dangerous_attributes_removal(self):
        """Тест удаления опасных HTML атрибутов"""
        dangerous_content = """
        <p onclick="maliciousFunction()">Текст с onclick</p>
        <a href="javascript:alert('XSS')" onmouseover="stealData()">Ссылка</a>
        <img src="image.jpg" onerror="alert('XSS')" />
        <div style="background: url(javascript:alert('XSS'))">Content</div>
        """

        page = Page.objects.create(title="Attributes Test", content=dangerous_content, is_published=True)

        # Опасные теги должны быть удалены, но текст может остаться
        # Важно что опасные теги и их атрибуты удаляются
        self.assertNotIn("<script>", page.content)
        self.assertNotIn("onmouseover=", page.content)
        self.assertNotIn("onerror=", page.content)
        self.assertNotIn("<img", page.content)  # img не в allowed_tags
        self.assertNotIn("<div", page.content)  # div не в allowed_tags

    def test_iframe_and_embed_removal(self):
        """Тест удаления iframe и embed тегов"""
        dangerous_content = """
        <p>Контент</p>
        <iframe src="http://malicious.com"></iframe>
        <embed src="malicious.swf"></embed>
        <object data="malicious.swf"></object>
        """

        page = Page.objects.create(title="Iframe Test", content=dangerous_content, is_published=True)

        # Опасные теги должны быть удалены
        self.assertNotIn("<iframe", page.content)
        self.assertNotIn("<embed", page.content)
        self.assertNotIn("<object", page.content)
        self.assertNotIn("malicious.com", page.content)
        self.assertNotIn("malicious.swf", page.content)

        # Безопасный контент должен остаться
        self.assertIn("<p>Контент</p>", page.content)

    def test_allowed_tags_preservation(self):
        """Тест сохранения разрешенных HTML тегов"""
        safe_content = """
        <h1>Заголовок 1</h1>
        <h2>Заголовок 2</h2>
        <h3>Заголовок 3</h3>
        <p>Параграф с <strong>жирным</strong> и <em>курсивом</em></p>
        <ul>
            <li>Элемент списка 1</li>
            <li>Элемент списка 2</li>
        </ul>
        <ol>
            <li>Нумерованный элемент</li>
        </ol>
        <a href="https://example.com" title="Безопасная ссылка">Ссылка</a>
        <br>
        """

        page = Page.objects.create(title="Safe Tags Test", content=safe_content, is_published=True)

        # Все безопасные теги должны сохраниться
        safe_tags = ["h1", "h2", "h3", "p", "strong", "em", "ul", "ol", "li", "a", "br"]
        for tag in safe_tags:
            self.assertIn(f"<{tag}", page.content)

    def test_malicious_css_removal(self):
        """Тест удаления потенциально опасного CSS"""
        dangerous_content = """
        <p style="background: url(javascript:alert('XSS'))">CSS XSS</p>
        <div style="expression(alert('XSS'))">IE Expression</div>
        """

        page = Page.objects.create(title="CSS Test", content=dangerous_content, is_published=True)

        # Опасный CSS должен быть удален
        self.assertNotIn("javascript:", page.content)
        self.assertNotIn("expression(", page.content)
        self.assertNotIn("alert", page.content)

    def test_data_uri_removal(self):
        """Тест удаления потенциально опасных data: URI"""
        dangerous_content = """
        <img src="data:text/html,<script>alert('XSS')</script>" />
        <a href="data:text/html,<script>alert('XSS')</script>">Link</a>
        """

        page = Page.objects.create(title="Data URI Test", content=dangerous_content, is_published=True)

        # Data URI со скриптами должны быть удалены
        self.assertNotIn("data:text/html", page.content)
        self.assertNotIn("<script>", page.content)


@pytest.mark.unit
class PageModelTest(TestCase):
    """Общие unit тесты для модели Page"""

    def test_slug_auto_generation(self):
        """Тест автогенерации slug"""
        page = Page.objects.create(title="Тестовая Страница", content="<p>Контент</p>", is_published=True)

        self.assertEqual(page.slug, "testovaja-stranitsa")

    def test_seo_title_auto_generation(self):
        """Тест автогенерации SEO заголовка"""
        long_title = "Очень длинный заголовок страницы который должен быть обрезан"
        page = Page.objects.create(title=long_title, content="<p>Контент</p>", is_published=True)

        self.assertEqual(len(page.seo_title), 60)
        self.assertTrue(page.seo_title.startswith("Очень длинный"))

    def test_seo_description_auto_generation(self):
        """Тест автогенерации SEO описания"""
        long_content = "<p>" + "Длинный контент страницы. " * 20 + "</p>"
        page = Page.objects.create(title="Тест", content=long_content, is_published=True)

        self.assertEqual(len(page.seo_description), 160)
        self.assertNotIn("<p>", page.seo_description)
        self.assertNotIn("</p>", page.seo_description)

    def test_string_representation(self):
        """Тест строкового представления модели"""
        page = Page(title="Тестовая страница")
        self.assertEqual(str(page), "Тестовая страница")
