/**
 * Blog List Loading State
 * Skeleton loader для страницы списка блога
 */

import React from 'react';

export default function BlogListLoading() {
  return (
    <div className="min-h-screen bg-neutral-50">
      {/* Breadcrumb Skeleton */}
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
        <div className="h-4 w-48 bg-neutral-200 rounded animate-pulse" />
      </div>

      {/* Hero Section Skeleton */}
      <section className="bg-white py-12 sm:py-16">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 text-center">
          <div className="h-12 w-64 bg-neutral-200 rounded mx-auto mb-4 animate-pulse" />
          <div className="h-6 w-96 bg-neutral-200 rounded mx-auto animate-pulse" />
        </div>
      </section>

      {/* Blog Grid Skeleton */}
      <section className="py-12">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {Array.from({ length: 6 }).map((_, index) => (
              <div key={index} className="bg-white rounded-lg overflow-hidden shadow-sm">
                {/* Image Skeleton */}
                <div className="aspect-video bg-neutral-200 animate-pulse" />

                {/* Content Skeleton */}
                <div className="p-6 space-y-3">
                  <div className="h-4 w-24 bg-neutral-200 rounded animate-pulse" />
                  <div className="h-6 bg-neutral-200 rounded animate-pulse" />
                  <div className="space-y-2">
                    <div className="h-4 bg-neutral-200 rounded animate-pulse" />
                    <div className="h-4 bg-neutral-200 rounded animate-pulse" />
                    <div className="h-4 w-3/4 bg-neutral-200 rounded animate-pulse" />
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>
    </div>
  );
}
