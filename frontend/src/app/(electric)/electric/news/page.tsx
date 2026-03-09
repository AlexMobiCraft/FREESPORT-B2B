/**
 * News List Page (/electric/news)
 * Electric Orange Theme
 */

import React from 'react';
import type { Metadata } from 'next';
import Link from 'next/link';
import { Newspaper } from 'lucide-react';
import { Breadcrumb } from '@/components/ui';
import { NewsCard } from '@/components/home/NewsCard';
import { newsService } from '@/services/newsService';

export const metadata: Metadata = {
  title: 'Новости | FREESPORT (Electric)',
  description: 'Новости компании FREESPORT. Акции, события, обновления каталога.',
};

interface NewsPageProps {
  searchParams: Promise<{ page?: string }>;
}

export default async function ElectricNewsPage({ searchParams }: NewsPageProps) {
  const params = await searchParams;
  const currentPage = Number(params.page) || 1;
  const breadcrumbItems = [{ label: 'Главная', href: '/electric' }, { label: 'Новости' }];

  // Fetch news data
  let newsData;
  try {
    newsData = await newsService.getNewsList({ page: currentPage });
  } catch (error) {
    console.error('Failed to fetch news:', error);
    newsData = { count: 0, next: null, previous: null, results: [] };
  }

  const totalPages = Math.ceil(newsData.count / 12);
  const hasNews = newsData.results.length > 0;

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
            <span className="inline-block transform skew-x-12">Новости</span>
          </h1>
          <p className="text-lg text-[var(--color-text-secondary)] max-w-2xl mx-auto">
            Актуальные новости, акции и события компании FREESPORT
          </p>
        </div>
      </section>

      {/* News Grid */}
      <section className="py-12">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          {hasNews ? (
            <>
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6 mb-12">
                {newsData.results.map(news => (
                  <NewsCard
                    key={news.id}
                    title={news.title}
                    excerpt={news.excerpt}
                    image={news.image || '/images/new/running-shoes.jpg'}
                    publishedAt={news.published_at}
                    slug={news.slug}
                  />
                ))}
              </div>

              {/* Pagination */}
              {totalPages > 1 && (
                <div className="flex justify-center items-center gap-2">
                  {/* Previous Button */}
                  {currentPage > 1 ? (
                    <Link
                      href={`/electric/news?page=${currentPage - 1}`}
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
                        href={`/electric/news?page=${page}`}
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
                      href={`/electric/news?page=${currentPage + 1}`}
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
                <Newspaper
                  className="w-8 h-8 text-[var(--color-primary)] transform skew-x-12"
                  aria-hidden="true"
                />
              </div>
              <h3 className="text-xl font-bold text-[var(--foreground)] mb-2 uppercase">
                Новостей пока нет
              </h3>
              <p className="text-sm text-[var(--color-text-secondary)] max-w-sm">
                Скоро здесь появятся новости о наших акциях и событиях
              </p>
            </div>
          )}
        </div>
      </section>
    </div>
  );
}
