import React, { cache } from 'react';
import type { Metadata } from 'next';
import { notFound } from 'next/navigation';
import { Breadcrumb, Card } from '@/components/ui';
import { extractBodyContent } from '@/utils/htmlContent';

interface PageData {
  title: string;
  slug: string;
  content: string;
  seo_title?: string;
  seo_description?: string;
}

function getApiUrl(): string {
  return (
    process.env.NEXT_PUBLIC_API_URL_INTERNAL ||
    process.env.NEXT_PUBLIC_API_URL ||
    'http://backend:8000/api/v1'
  );
}

function normalizePageData(data: unknown): PageData | null {
  if (!data || typeof data !== 'object') return null;
  const p = data as Record<string, unknown>;
  if (typeof p.title !== 'string' || p.title.trim() === '') return null;
  if (typeof p.content !== 'string' || p.content.trim() === '') return null;
  if (typeof p.slug !== 'string') return null;
  return {
    title: p.title,
    slug: p.slug,
    content: p.content,
    seo_title: typeof p.seo_title === 'string' ? p.seo_title : undefined,
    seo_description: typeof p.seo_description === 'string' ? p.seo_description : undefined,
  };
}

const fetchPage = cache(async (slug: string): Promise<PageData | null> => {
  try {
    const res = await fetch(`${getApiUrl()}/pages/${slug}/`, {
      next: { revalidate: process.env.NODE_ENV === 'development' ? 0 : 3600 },
    });
    if (res.status >= 500) throw new Error('server_error');
    if (!res.ok) return null;
    return normalizePageData(await res.json());
  } catch (error) {
    if (error instanceof Error && error.message === 'server_error') throw error;
    return null;
  }
});

interface Props {
  params: Promise<{ slug: string }>;
}

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { slug } = await params;
  const page = await fetchPage(slug);
  if (!page) return {};
  return {
    title: page.seo_title || `${page.title} | FREESPORT`,
    description: page.seo_description || '',
  };
}

export default async function CmsPage({ params }: Props) {
  const { slug } = await params;
  const page = await fetchPage(slug);

  if (!page) notFound();

  const breadcrumbItems = [{ label: 'Главная', href: '/' }, { label: page.title }];

  return (
    <div className="min-h-screen bg-neutral-100">
      <div className="container mx-auto px-4 py-4">
        <Breadcrumb items={breadcrumbItems} />
      </div>

      <section className="bg-white py-8 sm:py-12">
        <div className="container mx-auto px-4 text-center">
          <h1 className="text-headline-l sm:text-headline-xl font-bold text-text-primary">
            {page.title}
          </h1>
        </div>
      </section>

      <section className="container mx-auto px-4 py-8 sm:py-12">
        <Card className="p-6 sm:p-10">
          <div
            className="max-w-none text-text-primary [&_p]:mb-4 [&_h1]:text-2xl [&_h1]:font-bold [&_h1]:mb-4 [&_h2]:text-xl [&_h2]:font-semibold [&_h2]:mb-3 [&_h3]:text-lg [&_h3]:font-semibold [&_h3]:mb-2 [&_ul]:list-disc [&_ul]:pl-6 [&_ul]:mb-4 [&_ol]:list-decimal [&_ol]:pl-6 [&_ol]:mb-4 [&_li]:mb-1 [&_table]:w-full [&_table]:border-collapse [&_td]:border [&_td]:border-neutral-300 [&_td]:px-4 [&_td]:py-2 [&_td]:align-top [&_th]:border [&_th]:border-neutral-300 [&_th]:px-4 [&_th]:py-2 [&_th]:bg-neutral-200 [&_th]:font-semibold [&_th]:text-left [&_a]:text-primary [&_a]:underline"
            dangerouslySetInnerHTML={{ __html: extractBodyContent(page.content) }}
          />
        </Card>
      </section>
    </div>
  );
}
