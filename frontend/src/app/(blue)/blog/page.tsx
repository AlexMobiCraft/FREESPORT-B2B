/**
 * Blog List Page (/blog)
 * Story 21.3 - Frontend страницы блога
 *
 * Список опубликованных статей блога с пагинацией
 */

import React from 'react';
import type { Metadata } from 'next';
import Link from 'next/link';
import { BookOpen } from 'lucide-react';
import { Breadcrumb } from '@/components/ui';
import { BlogPostCard } from '@/components/home/BlogPostCard';
import { blogService } from '@/services/blogService';

export const metadata: Metadata = {
  title: 'Блог | FREESPORT',
  description: 'Полезные статьи о спорте, тренировках и экипировке от экспертов FREESPORT.',
  openGraph: {
    title: 'Блог | FREESPORT',
    description: 'Полезные статьи о спорте, тренировках и экипировке от экспертов FREESPORT',
  },
};

interface BlogPageProps {
  searchParams: Promise<{ page?: string }>;
}

export default async function BlogPage({ searchParams }: BlogPageProps) {
  const params = await searchParams;
  const currentPage = Number(params.page) || 1;
  const breadcrumbItems = [{ label: 'Главная', href: '/' }, { label: 'Блог' }];

  // Fetch blog data
  let blogData;
  try {
    blogData = await blogService.getBlogPosts({ page: currentPage });
  } catch (error) {
    console.error('Failed to fetch blog posts:', error);
    blogData = { count: 0, next: null, previous: null, results: [] };
  }

  const totalPages = Math.ceil(blogData.count / 12);
  const hasPosts = blogData.results.length > 0;

  return (
    <div className="min-h-screen bg-neutral-50">
      {/* Breadcrumb */}
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
        <Breadcrumb items={breadcrumbItems} />
      </div>

      {/* Hero Section */}
      <section className="bg-white py-12 sm:py-16">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 text-center">
          <h1 className="text-4xl sm:text-5xl font-bold text-text-primary mb-4">Блог</h1>
          <p className="text-lg text-text-secondary max-w-2xl mx-auto">
            Полезные статьи о спорте, тренировках и экипировке от экспертов FREESPORT
          </p>
        </div>
      </section>

      {/* Blog Grid */}
      <section className="py-12">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          {hasPosts ? (
            <>
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6 mb-12">
                {blogData.results.map(post => (
                  <BlogPostCard
                    key={post.id}
                    id={String(post.id)}
                    title={post.title}
                    excerpt={post.excerpt}
                    image={post.image || '/images/new/running-shoes.jpg'}
                    date={post.published_at}
                    slug={post.slug}
                  />
                ))}
              </div>

              {/* Pagination */}
              {totalPages > 1 && (
                <div className="flex justify-center items-center gap-2">
                  {/* Previous Button */}
                  {currentPage > 1 ? (
                    <Link
                      href={`/blog?page=${currentPage - 1}`}
                      className="px-4 py-2 border border-neutral-300 rounded-lg hover:bg-neutral-100 transition-colors text-text-primary"
                    >
                      ← Назад
                    </Link>
                  ) : (
                    <span className="px-4 py-2 border border-neutral-200 rounded-lg text-text-disabled cursor-not-allowed">
                      ← Назад
                    </span>
                  )}

                  {/* Page Numbers */}
                  <div className="flex gap-2">
                    {Array.from({ length: totalPages }, (_, i) => i + 1).map(page => (
                      <Link
                        key={page}
                        href={`/blog?page=${page}`}
                        className={`px-4 py-2 rounded-lg transition-colors ${
                          page === currentPage
                            ? 'bg-primary text-white font-semibold'
                            : 'border border-neutral-300 hover:bg-neutral-100 text-text-primary'
                        }`}
                      >
                        {page}
                      </Link>
                    ))}
                  </div>

                  {/* Next Button */}
                  {currentPage < totalPages ? (
                    <Link
                      href={`/blog?page=${currentPage + 1}`}
                      className="px-4 py-2 border border-neutral-300 rounded-lg hover:bg-neutral-100 transition-colors text-text-primary"
                    >
                      Вперёд →
                    </Link>
                  ) : (
                    <span className="px-4 py-2 border border-neutral-200 rounded-lg text-text-disabled cursor-not-allowed">
                      Вперёд →
                    </span>
                  )}
                </div>
              )}
            </>
          ) : (
            // Empty State
            <div className="flex flex-col items-center justify-center py-16 text-center">
              <div className="w-16 h-16 rounded-full bg-neutral-200 flex items-center justify-center mb-4">
                <BookOpen className="w-8 h-8 text-neutral-400" aria-hidden="true" />
              </div>
              <h3 className="text-xl font-semibold text-text-primary mb-2">Статей пока нет</h3>
              <p className="text-sm text-text-secondary max-w-sm">
                Скоро здесь появятся полезные статьи о спорте и тренировках
              </p>
            </div>
          )}
        </div>
      </section>
    </div>
  );
}
