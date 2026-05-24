/**
 * Blog List Page (/electric/blog)
 * Electric Orange Theme
 */

import React from 'react';
import type { Metadata } from 'next';
import Link from 'next/link';
import { BookOpen } from 'lucide-react';
import { Breadcrumb } from '@/components/ui';
import { BlogPostCard } from '@/components/home/BlogPostCard';
import { blogService } from '@/services/blogService';

export const metadata: Metadata = {
  title: 'Блог | FREESPORT (Electric)',
  description: 'Полезные статьи о спорте, тренировках и экипировке от экспертов FREESPORT.',
};

interface BlogPageProps {
  searchParams: Promise<{ page?: string }>;
}

export default async function ElectricBlogPage({ searchParams }: BlogPageProps) {
  const params = await searchParams;
  const currentPage = Number(params.page) || 1;
  const breadcrumbItems = [{ label: 'Главная', href: '/electric' }, { label: 'Блог' }];

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
    <div className="min-h-screen bg-[var(--bg-body)]">
      {/* Breadcrumb */}
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
        <Breadcrumb items={breadcrumbItems} />
      </div>

      {/* Hero Section */}
      <section className="bg-[var(--bg-card)] py-12 sm:py-16">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 text-center">
          <h1 className="text-4xl sm:text-5xl font-bold text-[var(--foreground)] mb-4 uppercase transform -skew-x-12">
            <span className="inline-block transform skew-x-12">Блог</span>
          </h1>
          <p className="text-lg text-[var(--color-text-secondary)] max-w-2xl mx-auto">
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
                      href={`/electric/blog?page=${currentPage - 1}`}
                      className="px-4 py-2 border border-[var(--border-default)] rounded-none transform -skew-x-12 hover:bg-[var(--color-primary)] hover:text-black transition-colors text-[var(--foreground)]"
                    >
                      <span className="inline-block transform skew-x-12">← Назад</span>
                    </Link>
                  ) : (
                    <span className="px-4 py-2 border border-[var(--border-default)] rounded-none transform -skew-x-12 text-[var(--color-text-muted)] cursor-not-allowed">
                      <span className="inline-block transform skew-x-12">← Назад</span>
                    </span>
                  )}

                  {/* Page Numbers */}
                  <div className="flex gap-2">
                    {Array.from({ length: totalPages }, (_, i) => i + 1).map(page => (
                      <Link
                        key={page}
                        href={`/electric/blog?page=${page}`}
                        className={`px-4 py-2 rounded-none transform -skew-x-12 transition-colors ${
                          page === currentPage
                            ? 'bg-[var(--color-primary)] text-black font-bold'
                            : 'border border-[var(--border-default)] hover:bg-[var(--bg-card)] text-[var(--foreground)]'
                        }`}
                      >
                        <span className="inline-block transform skew-x-12">{page}</span>
                      </Link>
                    ))}
                  </div>

                  {/* Next Button */}
                  {currentPage < totalPages ? (
                    <Link
                      href={`/electric/blog?page=${currentPage + 1}`}
                      className="px-4 py-2 border border-[var(--border-default)] rounded-none transform -skew-x-12 hover:bg-[var(--color-primary)] hover:text-black transition-colors text-[var(--foreground)]"
                    >
                      <span className="inline-block transform skew-x-12">Вперёд →</span>
                    </Link>
                  ) : (
                    <span className="px-4 py-2 border border-[var(--border-default)] rounded-none transform -skew-x-12 text-[var(--color-text-muted)] cursor-not-allowed">
                      <span className="inline-block transform skew-x-12">Вперёд →</span>
                    </span>
                  )}
                </div>
              )}
            </>
          ) : (
            // Empty State
            <div className="flex flex-col items-center justify-center py-16 text-center">
              <div className="w-16 h-16 rounded-none bg-[var(--bg-card)] flex items-center justify-center mb-4 transform -skew-x-12 border border-[var(--border-default)]">
                <BookOpen
                  className="w-8 h-8 text-[var(--color-primary)] transform skew-x-12"
                  aria-hidden="true"
                />
              </div>
              <h3 className="text-xl font-bold text-[var(--foreground)] mb-2 uppercase">
                Статей пока нет
              </h3>
              <p className="text-sm text-[var(--color-text-secondary)] max-w-sm">
                Скоро здесь появятся полезные статьи о спорте и тренировках
              </p>
            </div>
          )}
        </div>
      </section>
    </div>
  );
}
