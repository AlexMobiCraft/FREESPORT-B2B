"""
Модели для статических страниц
"""

import bleach
from django.core.validators import RegexValidator
from django.db import models
from django.utils.text import slugify
from transliterate import translit


class Page(models.Model):
    """Модель статической страницы"""

    title = models.CharField(max_length=200, verbose_name="Заголовок")
    slug = models.SlugField(unique=True, max_length=200, verbose_name="URL slug")
    content = models.TextField(verbose_name="Содержимое")

    # SEO fields
    seo_title = models.CharField(max_length=60, blank=True, verbose_name="SEO заголовок")
    seo_description = models.TextField(max_length=160, blank=True, verbose_name="SEO описание")

    # Publication
    is_published = models.BooleanField(default=False, verbose_name="Опубликовано")

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Страница"
        verbose_name_plural = "Страницы"
        ordering = ["title"]

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        """Автогенерация slug и SEO полей, HTML sanitization"""
        # Автогенерация slug если не задан
        if not self.slug:
            # Транслитерация русского текста в латиницу для slug
            try:
                transliterated = translit(self.title, "ru", reversed=True)
                self.slug = slugify(transliterated)
            except:
                # Fallback на стандартный slugify если translit не сработал
                self.slug = slugify(self.title)

        # Автогенерация SEO полей
        if not self.seo_title:
            self.seo_title = self.title[:60]

        if not self.seo_description:
            # Извлекаем первые 160 символов из content без HTML
            clean_content = bleach.clean(self.content, tags=[], strip=True)
            self.seo_description = clean_content[:160]

        # HTML sanitization
        allowed_tags = [
            "p",
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
            "br",
        ]
        allowed_attributes = {"a": ["href", "title"]}
        self.content = bleach.clean(
            self.content,
            tags=allowed_tags,
            attributes=allowed_attributes,
            strip=True,  # Полностью удаляем запрещенные теги вместо экранирования
        )

        super().save(*args, **kwargs)
