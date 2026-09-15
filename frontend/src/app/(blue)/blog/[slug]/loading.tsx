/**
 * Blog Detail Loading State
 * Skeleton loader для детальной страницы блога
 */

import React from 'react';

export default function BlogDetailLoading() {
  return (
    <div className="min-h-screen bg-neutral-50">
      {/* Breadcrumb Skeleton */}
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
        <div className="h-4 w-64 bg-neutral-200 rounded animate-pulse" />
      </div>

      {/* Article Content Skeleton */}
      <article className="bg-white">
        <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
          {/* Hero Image Skeleton */}
          <div className="relative aspect-video w-full mb-8 rounded-xl bg-neutral-200 animate-pulse" />

          {/* Meta Info Skeleton */}
          <div className="flex items-center gap-3 mb-6">
            <div className="h-4 w-32 bg-neutral-200 rounded animate-pulse" />
            <div className="h-4 w-24 bg-neutral-200 rounded animate-pulse" />
          </div>

          {/* Title Skeleton */}
          <div className="space-y-3 mb-8">
            <div className="h-10 bg-neutral-200 rounded animate-pulse" />
            <div className="h-10 w-3/4 bg-neutral-200 rounded animate-pulse" />
          </div>

          {/* Content Skeleton */}
          <div className="space-y-4">
            <div className="h-4 bg-neutral-200 rounded animate-pulse" />
            <div className="h-4 bg-neutral-200 rounded animate-pulse" />
            <div className="h-4 bg-neutral-200 rounded animate-pulse" />
            <div className="h-4 w-5/6 bg-neutral-200 rounded animate-pulse" />

            <div className="h-4 bg-neutral-200 rounded animate-pulse mt-8" />
            <div className="h-4 bg-neutral-200 rounded animate-pulse" />
            <div className="h-4 w-4/5 bg-neutral-200 rounded animate-pulse" />

            <div className="h-4 bg-neutral-200 rounded animate-pulse mt-8" />
            <div className="h-4 bg-neutral-200 rounded animate-pulse" />
            <div className="h-4 bg-neutral-200 rounded animate-pulse" />
            <div className="h-4 w-2/3 bg-neutral-200 rounded animate-pulse" />
          </div>

          {/* Back Link Skeleton */}
          <div className="mt-12 pt-8 border-t border-neutral-200">
            <div className="h-6 w-40 bg-neutral-200 rounded animate-pulse" />
          </div>
        </div>
      </article>
    </div>
  );
}
