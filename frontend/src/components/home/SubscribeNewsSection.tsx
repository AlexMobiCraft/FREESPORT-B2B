/**
 * SubscribeNewsSection Component
 * Адаптивный layout для формы подписки и блока «Наш блог»
 *
 * Desktop (lg: ≥1024px): grid 2 колонки (форма 1/3, новости 2/3)
 * Tablet/Mobile (<1024px): вертикальный stack
 *
 * @see Story 11.3 - AC 4
 */

import React from 'react';
import { SubscribeForm } from './SubscribeForm';
import { BlogSection } from './BlogSection';

export const SubscribeNewsSection: React.FC = () => {
  return (
    <section className="py-12">
      <div className="max-w-[1280px] mx-auto px-6">
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          {/* Desktop: 1/3 ширины, Tablet/Mobile: full width */}
          <div className="lg:col-span-1">
            <SubscribeForm />
          </div>

          {/* Desktop: 2/3 ширины, Tablet/Mobile: full width */}
          <div className="lg:col-span-2">
            <BlogSection />
          </div>
        </div>
      </div>
    </section>
  );
};
