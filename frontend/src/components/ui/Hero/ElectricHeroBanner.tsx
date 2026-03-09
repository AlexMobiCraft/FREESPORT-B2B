'use client';

import React from 'react';
import Link from 'next/link';

const ElectricHeroBanner: React.FC = () => {
  return (
    <section className="relative h-[480px] w-full overflow-hidden bg-[var(--bg-body)]">
      {/* Background Gradient / Image Overlay */}
      <div className="absolute inset-0 bg-gradient-to-r from-[var(--bg-body)] via-[var(--bg-card)] to-[var(--bg-body)] z-0"></div>

      {/* Decorative skewed line */}
      <div className="absolute top-0 right-[-10%] w-[50%] h-full bg-[var(--bg-card)] transform -skew-x-12 z-0 border-l border-[var(--bg-card-hover)]"></div>

      {/* Content Container */}
      <div className="relative z-10 max-w-[1200px] mx-auto px-5 h-full flex items-center">
        <div className="max-w-[800px]">
          {/* Subtitle */}
          <h2 className="font-roboto-condensed font-bold text-[24px] text-[var(--color-primary)] uppercase transform -skew-x-12 mb-2 tracking-wide">
            <span className="inline-block transform skew-x-12">Новая Коллекция 2026</span>
          </h2>

          {/* Main Title */}
          <h1 className="font-roboto-condensed font-black text-[48px] md:text-[64px] leading-[0.9] text-[var(--foreground)] uppercase transform -skew-x-12 mb-6 drop-shadow-lg">
            <span className="block transform skew-x-12">Преодолей</span>
            <span className="block transform skew-x-12 text-transparent bg-clip-text bg-gradient-to-r from-[var(--foreground)] to-[var(--color-text-secondary)]">
              Свои Границы
            </span>
          </h1>

          {/* Description */}
          <p className="font-inter text-[var(--color-text-secondary)] text-[16px] max-w-[500px] mb-8 leading-relaxed border-l-2 border-[var(--color-primary)] pl-4">
            Профессиональная экипировка для тех, кто не привык отступать. Качество, проверенное
            чемпионами.
          </p>

          {/* CTA Button */}
          <div className="relative group inline-block">
            <Link href="/catalog">
              <button className="relative bg-[var(--color-primary)] text-black font-roboto-condensed font-extrabold text-[16px] uppercase py-3 px-8 transform -skew-x-12 hover:bg-[var(--color-primary-hover)] hover:shadow-[var(--shadow-hover)] transition-all duration-300">
                <span className="inline-block transform skew-x-12">Смотреть Каталог</span>
              </button>
            </Link>
            {/* Decorative element behind button */}
            <div className="absolute top-2 left-2 w-full h-full border border-[var(--foreground)] transform -skew-x-12 -z-10 transition-transform group-hover:translate-x-1 group-hover:translate-y-1"></div>
          </div>
        </div>
      </div>

      {/* Floating / Decorative Elements */}
      <div className="absolute bottom-10 right-10 text-[var(--border-default)] font-roboto-condensed font-black text-[120px] opacity-10 select-none transform -skew-x-12 pointer-events-none">
        FREESPORT
      </div>
    </section>
  );
};

export default ElectricHeroBanner;
