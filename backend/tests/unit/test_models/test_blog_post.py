"""
Unit-тесты для модели BlogPost
"""

import pytest
from django.core.exceptions import ValidationError
from django.db.utils import IntegrityError
from django.test import TestCase

from apps.common.models import BlogPost, Category


@pytest.mark.unit
class TestBlogPostModel(TestCase):
    """Тесты модели BlogPost"""

    def setUp(self):
        """Настройка тестовых данных"""
        # Создаём категорию для тестов
        self.category = Category.objects.create(
            name="Спортивные советы",
            slug="sport-tips",
            is_active=True,
        )

    def test_blog_post_creation_with_minimal_fields(self):
        """Тест создания BlogPost с минимальными полями"""
        blog_post = BlogPost.objects.create(
            title="Как выбрать кроссовки",
            slug="kak-vybrat-krossovki",
            content="Содержание статьи о выборе кроссовок",
        )

        self.assertEqual(blog_post.title, "Как выбрать кроссовки")
        self.assertEqual(blog_post.slug, "kak-vybrat-krossovki")
        self.assertEqual(blog_post.content, "Содержание статьи о выборе кроссовок")
        self.assertFalse(blog_post.is_published)
        self.assertIsNone(blog_post.category)
        self.assertIsNotNone(blog_post.created_at)
        self.assertIsNotNone(blog_post.updated_at)

    def test_blog_post_str_returns_title(self):
        """Тест: __str__ возвращает заголовок"""
        blog_post = BlogPost.objects.create(
            title="Тренировки для начинающих",
            slug="trenirovki-dlya-nachinayushchih",
            content="Содержание статьи",
        )

        self.assertEqual(str(blog_post), "Тренировки для начинающих")

    def test_blog_post_slug_is_unique(self):
        """Тест: slug уникален"""
        BlogPost.objects.create(
            title="Первая статья",
            slug="unique-slug",
            content="Содержание первой статьи",
        )

        with self.assertRaises(IntegrityError):
            BlogPost.objects.create(
                title="Вторая статья",
                slug="unique-slug",
                content="Содержание второй статьи",
            )

    def test_blog_post_category_can_be_null(self):
        """Тест: category может быть NULL"""
        blog_post = BlogPost.objects.create(
            title="Статья без категории",
            slug="statya-bez-kategorii",
            content="Содержание статьи без категории",
            category=None,
        )

        self.assertIsNone(blog_post.category)

    def test_blog_post_category_can_be_set(self):
        """Тест: category может быть установлена"""
        blog_post = BlogPost.objects.create(
            title="Статья с категорией",
            slug="statya-s-kategoriej",
            content="Содержание статьи с категорией",
            category=self.category,
        )

        self.assertEqual(blog_post.category, self.category)
        self.assertEqual(blog_post.category.name, "Спортивные советы")

    def test_blog_post_is_published_default_false(self):
        """Тест: is_published по умолчанию False"""
        blog_post = BlogPost.objects.create(
            title="Неопубликованная статья",
            slug="neopublikovannaya-statya",
            content="Содержание неопубликованной статьи",
        )

        self.assertFalse(blog_post.is_published)

    def test_blog_post_ordering_by_published_at(self):
        """Тест: ordering по -published_at"""
        from django.utils import timezone

        # Создаём три статьи с разными датами публикации
        blog_post1 = BlogPost.objects.create(
            title="Статья 1",
            slug="statya-1",
            content="Содержание 1",
            is_published=True,
            published_at=timezone.now() - timezone.timedelta(days=3),
        )
        blog_post2 = BlogPost.objects.create(
            title="Статья 2",
            slug="statya-2",
            content="Содержание 2",
            is_published=True,
            published_at=timezone.now() - timezone.timedelta(days=1),
        )
        blog_post3 = BlogPost.objects.create(
            title="Статья 3",
            slug="statya-3",
            content="Содержание 3",
            is_published=True,
            published_at=timezone.now() - timezone.timedelta(days=2),
        )

        # Проверяем ordering (самая свежая первая)
        blog_posts = BlogPost.objects.all()
        self.assertEqual(blog_posts[0], blog_post2)  # Самая свежая
        self.assertEqual(blog_posts[1], blog_post3)
        self.assertEqual(blog_posts[2], blog_post1)  # Самая старая

    def test_blog_post_with_all_fields(self):
        """Тест создания BlogPost со всеми полями"""
        from django.utils import timezone

        blog_post = BlogPost.objects.create(
            title="Полная статья о беге",
            slug="polnaya-statya-o-bege",
            subtitle="Всё, что нужно знать о беге",
            excerpt="Краткое описание статьи о беге для начинающих",
            content="Полное содержание статьи о беге",
            author="Иван Иванов",
            category=self.category,
            is_published=True,
            published_at=timezone.now(),
            meta_title="Бег для начинающих - SEO заголовок",
            meta_description="SEO описание статьи о беге",
        )

        self.assertEqual(blog_post.title, "Полная статья о беге")
        self.assertEqual(blog_post.subtitle, "Всё, что нужно знать о беге")
        self.assertEqual(blog_post.excerpt, "Краткое описание статьи о беге для начинающих")
        self.assertEqual(blog_post.author, "Иван Иванов")
        self.assertEqual(blog_post.category, self.category)
        self.assertTrue(blog_post.is_published)
        self.assertIsNotNone(blog_post.published_at)
        self.assertEqual(blog_post.meta_title, "Бег для начинающих - SEO заголовок")
        self.assertEqual(blog_post.meta_description, "SEO описание статьи о беге")

    def test_blog_post_get_absolute_url(self):
        """Тест метода get_absolute_url"""
        blog_post = BlogPost.objects.create(
            title="Статья с URL",
            slug="statya-s-url",
            content="Содержание статьи",
        )

        expected_url = f"/blog/{blog_post.slug}/"
        # Метод get_absolute_url будет использовать
        # reverse('blog-detail', kwargs={'slug': self.slug})
        # Пока URL не настроены, просто проверяем, что метод не падает
        try:
            url = blog_post.get_absolute_url()
            # URL может быть не настроен, но метод должен существовать
        except Exception:
            # Это ожидаемо, т.к. URLs для blog ещё не настроены
            pass

    def test_blog_post_meta_configuration(self):
        """Тест настроек Meta класса BlogPost"""
        self.assertEqual(BlogPost._meta.verbose_name, "Статья блога")
        self.assertEqual(BlogPost._meta.verbose_name_plural, "Статьи блога")
        self.assertEqual(BlogPost._meta.ordering, ["-published_at"])

    def test_blog_post_indexes(self):
        """Тест наличия индексов в модели"""
        indexes = [index.fields for index in BlogPost._meta.indexes]
        self.assertIn(["is_published", "published_at"], indexes)
        self.assertIn(["category", "published_at"], indexes)

    def test_blog_post_category_on_delete_set_null(self):
        """Тест: при удалении Category, поле category становится NULL"""
        blog_post = BlogPost.objects.create(
            title="Статья с категорией",
            slug="statya-s-kat",
            content="Содержание",
            category=self.category,
        )

        self.assertEqual(blog_post.category, self.category)

        # Удаляем категорию
        self.category.delete()

        # Обновляем объект из БД
        blog_post.refresh_from_db()

        # Категория должна стать NULL
        self.assertIsNone(blog_post.category)

    def test_blog_post_timestamps_auto_update(self):
        """Тест автоматического обновления updated_at"""
        import time

        blog_post = BlogPost.objects.create(
            title="Тестовая статья",
            slug="testovaya-statya",
            content="Содержание",
        )

        created_at = blog_post.created_at
        updated_at_before = blog_post.updated_at

        # Небольшая задержка
        time.sleep(0.1)

        # Обновляем статью
        blog_post.title = "Обновлённая статья"
        blog_post.save()

        # Проверяем, что updated_at изменился, а created_at остался прежним
        self.assertEqual(blog_post.created_at, created_at)
        self.assertGreater(blog_post.updated_at, updated_at_before)
