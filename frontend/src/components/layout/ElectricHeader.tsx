'use client';

import React, { useState } from 'react';
import Link from 'next/link';
import Image from 'next/image';
import { Search, Heart, ShoppingCart, Menu, X } from 'lucide-react';
import { useCartStore } from '@/stores/cartStore';

const ElectricHeader: React.FC = () => {
  const [isMenuOpen, setIsMenuOpen] = useState(false);

  // Mock data for cart count
  const cartItemsCount = useCartStore(state => state.totalItems);

  // Navigation Links
  const navLinks = [
    { label: 'ГЛАВНАЯ', href: '/electric' },
    { label: 'КАТАЛОГ', href: '/electric/catalog' },
    { label: 'НОВОСТИ', href: '/electric/news' },
    { label: 'БЛОГ', href: '/electric/blog' },
    { label: 'ПАРТНЁРАМ', href: '/electric/partners' },
  ];

  return (
    <header className="fixed top-0 left-0 right-0 z-50 bg-[var(--bg-body)] border-b border-[var(--border-default)]">
      <div className="max-w-[1200px] mx-auto px-5">
        <div className="flex items-center justify-between h-[80px]">
          {/* Logo Area */}
          <Link href="/electric" className="flex items-center -ml-2 group">
            {/* Logo Image */}
            <div className="relative h-8 w-auto transform -skew-x-12 transition-transform group-hover:scale-105">
              <Image
                src="/Freesport_logo.svg"
                alt="FREESPORT"
                width={150}
                height={32}
                className="h-full w-auto object-contain"
                priority
              />
            </div>
          </Link>

          {/* Desktop Navigation */}
          <nav className="hidden md:flex items-center gap-8">
            {navLinks.map(link => (
              <Link
                key={link.href}
                href={link.href}
                className="font-inter font-medium text-[14px] text-[var(--color-text-secondary)] hover:text-[var(--color-primary)] transition-colors uppercase tracking-wide"
              >
                {link.label}
              </Link>
            ))}
          </nav>

          {/* Actions Area */}
          <div className="flex items-center gap-6">
            {/* Icons */}
            <div className="flex items-center gap-4">
              <button className="text-[var(--foreground)] hover:text-[var(--color-primary)] transition-colors">
                <Search className="w-6 h-6" />
              </button>

              <Link
                href="/favorites"
                className="text-[var(--foreground)] hover:text-[var(--color-primary)] transition-colors"
              >
                <Heart className="w-6 h-6" />
              </Link>

              <Link
                href="/cart"
                className="relative group text-[var(--foreground)] hover:text-[var(--color-primary)] transition-colors"
              >
                <ShoppingCart className="w-6 h-6" />
                {cartItemsCount > 0 && (
                  <span className="absolute -top-1.5 -right-1.5 flex items-center justify-center w-[18px] h-[18px] bg-[var(--color-primary)] text-black text-[10px] font-bold rounded-full">
                    {cartItemsCount}
                  </span>
                )}
              </Link>

              <button
                className="md:hidden text-[var(--foreground)] hover:text-[var(--color-primary)] transition-colors"
                onClick={() => setIsMenuOpen(!isMenuOpen)}
              >
                {isMenuOpen ? <X className="w-6 h-6" /> : <Menu className="w-6 h-6" />}
              </button>
            </div>

            {/* Auth Buttons (Desktop Only) - Moved AFTER icons */}
            <div className="hidden md:flex items-center gap-6 ml-4 border-l border-[var(--border-default)] pl-6">
              <Link href="/register" className="group relative">
                <span className="block font-roboto-condensed font-bold text-[14px] text-[var(--foreground)] uppercase transform -skew-x-12 tracking-wide transition-colors group-hover:text-[var(--color-primary)]">
                  Регистрация
                </span>
                <span className="absolute bottom-[-4px] left-0 w-0 h-[2px] bg-[var(--color-primary)] transform -skew-x-12 transition-all duration-300 group-hover:w-full"></span>
              </Link>

              <Link href="/login" className="group relative">
                <span className="block font-roboto-condensed font-bold text-[14px] text-[var(--foreground)] uppercase transform -skew-x-12 tracking-wide transition-colors group-hover:text-[var(--color-primary)]">
                  Войти
                </span>
                <span className="absolute bottom-[-4px] left-0 w-0 h-[2px] bg-[var(--color-primary)] transform -skew-x-12 transition-all duration-300 group-hover:w-full"></span>
              </Link>
            </div>
          </div>
        </div>
      </div>

      {/* Mobile Menu Overlay */}
      {isMenuOpen && (
        <div className="md:hidden absolute top-[80px] left-0 w-full bg-[var(--bg-card)] border-b border-[var(--border-default)] p-5 flex flex-col gap-4 shadow-xl">
          {navLinks.map(link => (
            <Link
              key={link.href}
              href={link.href}
              className="font-inter font-medium text-[16px] text-[var(--foreground)] hover:text-[var(--color-primary)] uppercase tracking-wide py-2 border-b border-[var(--border-default)]"
              onClick={() => setIsMenuOpen(false)}
            >
              {link.label}
            </Link>
          ))}
          <div className="flex flex-col gap-4 mt-2">
            <Link
              href="/register"
              className="font-roboto-condensed font-bold text-[16px] text-[var(--foreground)] uppercase transform -skew-x-12 hover:text-[var(--color-primary)]"
              onClick={() => setIsMenuOpen(false)}
            >
              Регистрация
            </Link>
            <Link
              href="/login"
              className="font-roboto-condensed font-bold text-[16px] text-[var(--foreground)] uppercase transform -skew-x-12 hover:text-[var(--color-primary)]"
              onClick={() => setIsMenuOpen(false)}
            >
              Войти
            </Link>
          </div>
        </div>
      )}
    </header>
  );
};

export default ElectricHeader;
