/**
 * Tests for blogService
 * Story 21.3 - Frontend страницы блога
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { blogService } from '../blogService';
import apiClient from '../api-client';
import type { BlogList, BlogItem } from '@/types/api';

// Mock apiClient
vi.mock('../api-client');

describe('blogService', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('getBlogPosts', () => {
    it('должен возвращать список статей блога с пагинацией', async () => {
      const mockBlogList: BlogList = {
        count: 2,
        next: null,
        previous: null,
        results: [
          {
            id: 1,
            title: 'Тестовая статья 1',
            slug: 'test-post-1',
            excerpt: 'Описание статьи 1',
            image: '/images/blog1.jpg',
            published_at: '2025-01-01T12:00:00Z',
            created_at: '2025-01-01T10:00:00Z',
            updated_at: '2025-01-01T10:00:00Z',
          },
          {
            id: 2,
            title: 'Тестовая статья 2',
            slug: 'test-post-2',
            excerpt: 'Описание статьи 2',
            image: '/images/blog2.jpg',
            published_at: '2025-01-02T12:00:00Z',
            created_at: '2025-01-02T10:00:00Z',
            updated_at: '2025-01-02T10:00:00Z',
          },
        ],
      };

      vi.mocked(apiClient.get).mockResolvedValue({ data: mockBlogList });

      const result = await blogService.getBlogPosts({ page: 1 });

      expect(apiClient.get).toHaveBeenCalledWith('/blog', {
        params: {
          page_size: 12,
          page: 1,
        },
      });
      expect(result).toEqual(mockBlogList);
      expect(result.results).toHaveLength(2);
    });

    it('должен использовать параметры по умолчанию', async () => {
      const mockBlogList: BlogList = {
        count: 0,
        next: null,
        previous: null,
        results: [],
      };

      vi.mocked(apiClient.get).mockResolvedValue({ data: mockBlogList });

      await blogService.getBlogPosts();

      expect(apiClient.get).toHaveBeenCalledWith('/blog', {
        params: {
          page_size: 12,
        },
      });
    });

    it('должен поддерживать кастомный page_size', async () => {
      const mockBlogList: BlogList = {
        count: 0,
        next: null,
        previous: null,
        results: [],
      };

      vi.mocked(apiClient.get).mockResolvedValue({ data: mockBlogList });

      await blogService.getBlogPosts({ page_size: 6 });

      expect(apiClient.get).toHaveBeenCalledWith('/blog', {
        params: {
          page_size: 6,
        },
      });
    });
  });

  describe('getBlogPostBySlug', () => {
    it('должен возвращать детальную статью по slug', async () => {
      const mockBlogPost: BlogItem = {
        id: 1,
        title: 'Детальная статья',
        slug: 'detailed-post',
        subtitle: 'Подзаголовок статьи',
        excerpt: 'Краткое описание',
        content: '<p>Полный контент статьи</p>',
        image: '/images/blog-detail.jpg',
        author: 'Автор статьи',
        category: 'Тренировки',
        published_at: '2025-01-01T12:00:00Z',
        created_at: '2025-01-01T10:00:00Z',
        updated_at: '2025-01-01T10:00:00Z',
        meta_title: 'SEO заголовок',
        meta_description: 'SEO описание',
      };

      vi.mocked(apiClient.get).mockResolvedValue({ data: mockBlogPost });

      const result = await blogService.getBlogPostBySlug('detailed-post');

      expect(apiClient.get).toHaveBeenCalledWith('/blog/detailed-post/');
      expect(result).toEqual(mockBlogPost);
      expect(result.slug).toBe('detailed-post');
    });

    it('должен бросать ошибку при 404', async () => {
      const error = {
        response: {
          status: 404,
        },
      };

      vi.mocked(apiClient.get).mockRejectedValue(error);

      await expect(blogService.getBlogPostBySlug('non-existent')).rejects.toThrow(
        'Blog post not found'
      );
    });

    it('должен пробрасывать другие ошибки', async () => {
      const error = {
        response: {
          status: 500,
        },
        message: 'Server error',
      };

      vi.mocked(apiClient.get).mockRejectedValue(error);

      await expect(blogService.getBlogPostBySlug('some-slug')).rejects.toEqual(error);
    });
  });
});
