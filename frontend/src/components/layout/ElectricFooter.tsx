'use client';

import React from 'react';
import Link from 'next/link';
import { Facebook, Instagram, Youtube, Mail, Phone, MapPin } from 'lucide-react';

const ElectricFooter: React.FC = () => {
  return (
    <footer className="bg-[var(--bg-card)] text-[var(--foreground)] pt-10 md:pt-16 pb-6 md:pb-8 border-t border-[var(--border-default)]">
      <div className="max-w-[1200px] mx-auto px-5">
        {/* Main Footer Content */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-8 md:gap-12 mb-10 md:mb-16">
          {/* Column 1: About */}
          <div>
            <h3 className="font-roboto-condensed font-bold text-[16px] md:text-[20px] uppercase transform -skew-x-12 mb-4 md:mb-6 text-[var(--foreground)] border-b-2 border-[var(--color-primary)] inline-block pb-1">
              <span className="transform skew-x-12 inline-block">О КОМПАНИИ</span>
            </h3>
            <p className="font-inter text-[var(--color-text-secondary)] text-[12px] md:text-[14px] leading-relaxed mb-4 md:mb-6">
              FREESPORT — ваш надежный партнер в мире спорта. Мы предлагаем только качественное
              оборудование и экипировку для профессионалов и любителей.
            </p>
            <div className="flex gap-4">
              <Link
                href="#"
                className="w-10 h-10 flex items-center justify-center border border-[var(--border-default)] transform -skew-x-12 hover:bg-[var(--color-primary)] hover:border-[var(--color-primary)] hover:text-black transition-all group"
              >
                <Facebook className="w-5 h-5 transform skew-x-12" />
              </Link>
              <Link
                href="#"
                className="w-10 h-10 flex items-center justify-center border border-[var(--border-default)] transform -skew-x-12 hover:bg-[var(--color-primary)] hover:border-[var(--color-primary)] hover:text-black transition-all group"
              >
                <Instagram className="w-5 h-5 transform skew-x-12" />
              </Link>
              <Link
                href="#"
                className="w-10 h-10 flex items-center justify-center border border-[var(--border-default)] transform -skew-x-12 hover:bg-[var(--color-primary)] hover:border-[var(--color-primary)] hover:text-black transition-all group"
              >
                <Youtube className="w-5 h-5 transform skew-x-12" />
              </Link>
            </div>
          </div>

          {/* Column 2: Catalog */}
          <div>
            <h3 className="font-roboto-condensed font-bold text-[16px] md:text-[20px] uppercase transform -skew-x-12 mb-4 md:mb-6 text-[var(--foreground)] border-b-2 border-[var(--color-primary)] inline-block pb-1">
              <span className="transform skew-x-12 inline-block">КАТАЛОГ</span>
            </h3>
            <ul className="space-y-2 md:space-y-3 font-inter text-[12px] md:text-[14px]">
              {[
                'Единоборства',
                'Фитнес',
                'Тренажеры',
                'Спортивная одежда',
                'Аксессуары',
                'Распродажа',
              ].map(item => (
                <li key={item}>
                  <Link
                    href="/catalog"
                    className="text-[var(--color-text-secondary)] hover:text-[var(--color-primary)] transition-colors flex items-center gap-2 group"
                  >
                    <span className="w-1.5 h-1.5 bg-[var(--border-default)] group-hover:bg-[var(--color-primary)] transition-colors transform rotate-45"></span>
                    {item}
                  </Link>
                </li>
              ))}
            </ul>
          </div>

          {/* Column 3: Information */}
          <div>
            <h3 className="font-roboto-condensed font-bold text-[16px] md:text-[20px] uppercase transform -skew-x-12 mb-4 md:mb-6 text-[var(--foreground)] border-b-2 border-[var(--color-primary)] inline-block pb-1">
              <span className="transform skew-x-12 inline-block">ИНФОРМАЦИЯ</span>
            </h3>
            <ul className="space-y-2 md:space-y-3 font-inter text-[12px] md:text-[14px]">
              {[
                'О нас',
                'Доставка и оплата',
                'Возврат товара',
                'Контакты',
                'Блог',
                'Публичная оферта',
              ].map(item => (
                <li key={item}>
                  <Link
                    href="#"
                    className="text-[var(--color-text-secondary)] hover:text-[var(--color-primary)] transition-colors flex items-center gap-2 group"
                  >
                    <span className="w-1.5 h-1.5 bg-[var(--border-default)] group-hover:bg-[var(--color-primary)] transition-colors transform rotate-45"></span>
                    {item}
                  </Link>
                </li>
              ))}
            </ul>
          </div>

          {/* Column 4: Contacts */}
          <div>
            <h3 className="font-roboto-condensed font-bold text-[16px] md:text-[20px] uppercase transform -skew-x-12 mb-4 md:mb-6 text-[var(--foreground)] border-b-2 border-[var(--color-primary)] inline-block pb-1">
              <span className="transform skew-x-12 inline-block">КОНТАКТЫ</span>
            </h3>
            <ul className="space-y-3 md:space-y-4 font-inter text-[12px] md:text-[14px] text-[var(--color-text-secondary)]">
              <li className="flex items-start gap-3">
                <MapPin className="w-5 h-5 text-[var(--color-primary)] mt-0.5 flex-shrink-0" />
                <span>г. Ставрополь, ул. Коломийцева, 40/1</span>
              </li>
              <li className="flex items-center gap-3">
                <Phone className="w-5 h-5 text-[var(--color-primary)] flex-shrink-0" />
                <a
                  href="tel:+79682732168"
                  className="hover:text-[var(--foreground)] transition-colors"
                >
                  +7 968 273-21-68
                </a>
              </li>
              <li className="flex items-center gap-3">
                <Mail className="w-5 h-5 text-[var(--color-primary)] flex-shrink-0" />
                <a
                  href="mailto:info@freesport.ru"
                  className="hover:text-[var(--foreground)] transition-colors"
                >
                  info@freesport.ru
                </a>
              </li>
            </ul>
          </div>
        </div>

        {/* Bottom Bar */}
        <div className="border-t border-[var(--border-default)] pt-6 md:pt-8 flex flex-col md:flex-row justify-between items-center gap-4">
          <p className="font-inter text-[10px] md:text-[12px] text-[var(--color-text-muted)]">
            © 2026 FREESPORT. Все права защищены.
          </p>
          <div className="flex gap-6">
            <Link
              href="#"
              className="font-inter text-[10px] md:text-[12px] text-[var(--color-text-muted)] hover:text-[var(--foreground)] transition-colors"
            >
              Политика конфиденциальности
            </Link>
            <Link
              href="#"
              className="font-inter text-[10px] md:text-[12px] text-[var(--color-text-muted)] hover:text-[var(--foreground)] transition-colors"
            >
              Пользовательское соглашение
            </Link>
          </div>
        </div>
      </div>
    </footer>
  );
};

export default ElectricFooter;
