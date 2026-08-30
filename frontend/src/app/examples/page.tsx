/**
 * Страница примеров (HTML-файлов из public/examples)
 * Отображает список файлов с поддержкой серверной пагинации
 */

import React from 'react';
import { readdirSync } from 'fs';
import { join } from 'path';
import Link from 'next/link';
import { FileCode, ChevronRight } from 'lucide-react';

import { PaginationWrapper } from './PaginationWrapper';
import { Suspense } from 'react';

const EXAMPLES_DIR = join(process.cwd(), 'public/examples');
const ITEMS_PER_PAGE = 5;

interface ExamplesPageProps {
  searchParams: Promise<{ page?: string }>;
}

/**
 * Получает список HTML файлов из директории примеров
 */
function getExampleFiles(): string[] {
  try {
    const files = readdirSync(EXAMPLES_DIR);
    return (
      files
        .filter(file => file.endsWith('.html'))
        // Сортировка по имени (числовая, если возможно)
        .sort((a, b) => {
          const numA = parseInt(a);
          const numB = parseInt(b);
          if (!isNaN(numA) && !isNaN(numB)) {
            return numA - numB;
          }
          return a.localeCompare(b);
        })
    );
  } catch (error) {
    console.error('Error reading examples directory:', error);
    return [];
  }
}

export default async function ExamplesPage({ searchParams }: ExamplesPageProps) {
  const { page } = await searchParams;
  const currentPage = parseInt(page || '1') || 1;

  const allFiles = getExampleFiles();
  const totalFiles = allFiles.length;
  const totalPages = Math.ceil(totalFiles / ITEMS_PER_PAGE);

  // Клэмп текущей страницы
  const validatedPage = Math.max(1, Math.min(currentPage, totalPages || 1));

  // Срез файлов для текущей страницы
  const startIndex = (validatedPage - 1) * ITEMS_PER_PAGE;
  const paginatedFiles = allFiles.slice(startIndex, startIndex + ITEMS_PER_PAGE);

  return (
    <main className="bg-[#F5F7FB] min-h-screen py-12">
      <div className="max-w-4xl mx-auto px-4 sm:px-6">
        <header className="mb-10">
          <h1 className="text-4xl font-bold text-gray-900 mb-2">Примеры страниц</h1>
          <p className="text-neutral-600">
            Список статических HTML-примеров из директории{' '}
            <code className="bg-white px-2 py-0.5 rounded border border-neutral-200">
              public/examples
            </code>
          </p>
        </header>

        <div className="bg-white rounded-3xl shadow-sm border border-neutral-100 overflow-hidden">
          {totalFiles > 0 ? (
            <>
              <ul className="divide-y divide-neutral-100">
                {paginatedFiles.map(file => (
                  <li key={file} className="group hover:bg-neutral-50 transition-colors">
                    <Link
                      href={`/examples/${file}`}
                      className="flex items-center justify-between px-6 py-5"
                    >
                      <div className="flex items-center gap-4">
                        <div className="w-10 h-10 rounded-xl bg-primary/5 flex items-center justify-center text-primary group-hover:bg-primary group-hover:text-white transition-all">
                          <FileCode size={20} />
                        </div>
                        <div>
                          <span className="text-lg font-medium text-neutral-800">{file}</span>
                          <p className="text-sm text-neutral-500">HTML Документ</p>
                        </div>
                      </div>
                      <div className="text-neutral-300 group-hover:text-primary transition-colors">
                        <ChevronRight size={24} />
                      </div>
                    </Link>
                  </li>
                ))}
              </ul>

              {totalPages > 1 && (
                <div className="p-6 bg-neutral-50/50 border-t border-neutral-100">
                  <Suspense
                    fallback={
                      <div className="h-10 animate-pulse bg-neutral-200 rounded-sm w-full" />
                    }
                  >
                    <PaginationWrapper currentPage={validatedPage} totalPages={totalPages} />
                  </Suspense>
                </div>
              )}
            </>
          ) : (
            <div className="p-12 text-center">
              <div className="inline-flex items-center justify-center w-16 h-16 rounded-full bg-neutral-100 text-neutral-400 mb-4">
                <FileCode size={32} />
              </div>
              <h3 className="text-lg font-medium text-neutral-900">Файлы не найдены</h3>
              <p className="text-neutral-500 mt-1">
                Убедитесь, что в папке <code className="text-xs">public/examples</code> есть
                HTML-файлы.
              </p>
            </div>
          )}
        </div>

        <div className="mt-8 text-center text-sm text-neutral-400">Всего файлов: {totalFiles}</div>
      </div>
    </main>
  );
}
