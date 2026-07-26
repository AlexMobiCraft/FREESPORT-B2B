/**
 * Страница «Политика обработки персональных данных» (/privacy-policy).
 */

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

const DEFAULT_TITLE = 'Политика обработки персональных данных | FREESPORT';
const PRIVACY_POLICY_ENDPOINT = '/pages/privacy-policy/';

function getApiUrl(): string {
  return (
    process.env.NEXT_PUBLIC_API_URL_INTERNAL ||
    process.env.NEXT_PUBLIC_API_URL ||
    'http://backend:8000/api/v1'
  );
}

function normalizePageData(data: unknown): PageData | null {
  if (!data || typeof data !== 'object') {
    return null;
  }

  const page = data as Record<string, unknown>;

  if (typeof page.title !== 'string' || page.title.trim() === '') {
    return null;
  }

  if (typeof page.content !== 'string' || page.content.trim() === '') {
    return null;
  }

  if (typeof page.slug !== 'string') {
    return null;
  }

  return {
    title: page.title,
    slug: page.slug,
    content: page.content,
    seo_title: typeof page.seo_title === 'string' ? page.seo_title : undefined,
    seo_description: typeof page.seo_description === 'string' ? page.seo_description : undefined,
  };
}

const fetchPrivacyPolicy = cache(async (): Promise<PageData | null> => {
  try {
    const res = await fetch(`${getApiUrl()}${PRIVACY_POLICY_ENDPOINT}`, {
      next: { revalidate: process.env.NODE_ENV === 'development' ? 0 : 3600 },
    });

    if (res.status >= 500) {
      throw new Error('Не удалось загрузить страницу политики ПДн');
    }

    if (!res.ok) {
      return null;
    }

    return normalizePageData(await res.json());
  } catch (error) {
    if (error instanceof Error && error.message === 'Не удалось загрузить страницу политики ПДн') {
      throw error;
    }
    return null;
  }
});

export async function generateMetadata(): Promise<Metadata> {
  const page = await fetchPrivacyPolicy();

  return {
    title: page?.seo_title || DEFAULT_TITLE,
    description: page?.seo_description || '',
  };
}

const breadcrumbItems = [
  { label: 'Главная', href: '/' },
  { label: 'Политика обработки персональных данных' },
];

export default async function PrivacyPolicyPage() {
  const page = await fetchPrivacyPolicy();

  if (!page) {
    notFound();
  }

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
            className="prose prose-neutral max-w-none text-text-primary"
            dangerouslySetInnerHTML={{ __html: extractBodyContent(page.content) }}
          />
        </Card>
      </section>
    </div>
  );
}
