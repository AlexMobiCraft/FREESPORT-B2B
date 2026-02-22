/**
 * News List Page (/news)
 * Story 20.2 - Frontend страницы новостей
 *
 * Список опубликованных новостей с пагинацией
 */

import React from 'react';
import type { Metadata } from 'next';
import Link from 'next/link';
import { Newspaper } from 'lucide-react';
import { Breadcrumb } from '@/components/ui';
import { NewsCard } from '@/components/home/NewsCard';
import { newsService } from '@/services/newsService';

export const metadata: Metadata = {
  title: 'Новости | FREESPORT',
  description: 'Новости компании FREESPORT. Акции, события, обновления каталога.',
  openGraph: {
    title: 'Новости | FREESPORT',
    description: 'Новости компании FREESPORT',
  },
};

interface NewsPageProps {
  searchParams: Promise<{ page?: string }>;
}

export default async function NewsPage({ searchParams }: NewsPageProps) {
  const params = await searchParams;
  const currentPage = Number(params.page) || 1;
  const breadcrumbItems = [{ label: 'Главная', href: '/' }, { label: 'Новости' }];

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
    <div className="min-h-screen bg-neutral-50">
      {/* Breadcrumb */}
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
        <Breadcrumb items={breadcrumbItems} />
      </div>

      {/* Hero Section */}
      <section className="bg-white py-12 sm:py-16">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 text-center">
          <h1 className="text-4xl sm:text-5xl font-bold text-text-primary mb-4">Новости</h1>
          <p className="text-lg text-text-secondary max-w-2xl mx-auto">
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
                      href={`/news?page=${currentPage - 1}`}
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
                        href={`/news?page=${page}`}
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
                      href={`/news?page=${currentPage + 1}`}
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
                <Newspaper className="w-8 h-8 text-neutral-400" aria-hidden="true" />
              </div>
              <h3 className="text-xl font-semibold text-text-primary mb-2">Новостей пока нет</h3>
              <p className="text-sm text-text-secondary max-w-sm">
                Скоро здесь появятся новости о наших акциях и событиях
              </p>
            </div>
          )}
        </div>
      </section>
    </div>
  );
}
