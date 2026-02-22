/**
 * Компонент Header с навигацией для FREESPORT Platform
 * Поддержка B2B/B2C интерфейсов и аутентификации
 * Design System v2.1.0 - сине-голубая цветовая схема
 */
'use client';

import React, { useState, useRef, useEffect } from 'react';
import Link from 'next/link';
import Image from 'next/image';
import { usePathname, useRouter } from 'next/navigation';
import { Heart, ShoppingCart, Menu, X, Search, User, LogOut } from 'lucide-react';
import { authSelectors, useAuthStore } from '@/stores/authStore';
import { useCartStore } from '@/stores/cartStore';
import { Button } from '@/components/ui/Button';

const Header: React.FC = () => {
  const pathname = usePathname();
  const router = useRouter();
  const isAuthenticated = authSelectors.useIsAuthenticated();
  const user = authSelectors.useUser();
  const isB2BUser = authSelectors.useIsB2BUser();
  const logout = useAuthStore(state => state.logout);

  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);
  const mobileMenuRef = useRef<HTMLDivElement>(null);
  const menuButtonRef = useRef<HTMLButtonElement>(null);

  // Закрытие меню при клике вне его области
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (
        isMobileMenuOpen &&
        mobileMenuRef.current &&
        menuButtonRef.current &&
        !mobileMenuRef.current.contains(event.target as Node) &&
        !menuButtonRef.current.contains(event.target as Node)
      ) {
        setIsMobileMenuOpen(false);
      }
    };

    document.addEventListener('mousedown', handleClickOutside);
    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
    };
  }, [isMobileMenuOpen]);

  /**
   * Обработчик выхода из аккаунта
   * Вызывает API logout, очищает токены и редиректит на главную
   */
  const handleLogout = async () => {
    await logout();
    router.push('/');
  };

  // Получаем количество товаров из корзины
  const cartItemsCount = useCartStore(state => state.totalItems);

  // Навигационные элементы
  const navigationItems = [
    { href: '/home', label: 'Главная' },
    { href: '/catalog', label: 'Каталог' },
    { href: '/news', label: 'Новости' },
    { href: '/blog', label: 'Блог' },
    { href: '/partners', label: 'Партнёрам' },
  ];

  const isActivePage = (href: string) => {
    if (href === '/home') return pathname === href;
    return pathname.startsWith(href);
  };

  return (
    <header className="bg-white sticky top-0 left-0 right-0 z-50 shadow-[0_6px_16px_rgba(31,42,68,0.05)]">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex justify-between items-center h-[60px]">
          {/* Логотип */}
          <div className="flex-shrink-0">
            <Link href="/home" className="flex items-center gap-2">
              <Image
                src="/Freesport_logo.svg"
                alt="FREESPORT"
                width={120}
                height={32}
                className="h-8 w-auto"
                priority
              />
              {isB2BUser && (
                <span className="px-2 py-1 text-[10px] bg-accent-danger-bg text-accent-danger rounded-full font-bold">
                  B2B
                </span>
              )}
            </Link>
          </div>

          {/* Основная навигация (десктоп) */}
          <nav aria-label="Основная навигация" className="hidden md:flex items-center gap-6">
            {navigationItems.map(item => (
              <Link
                key={item.href}
                href={item.href}
                className={`relative text-body-m font-medium transition-colors duration-short ${isActivePage(item.href)
                  ? "text-primary after:content-[''] after:absolute after:bottom-[-4px] after:left-0 after:right-0 after:h-[3px] after:bg-primary after:rounded-full"
                  : 'text-text-primary hover:text-text-secondary'
                  }`}
              >
                {item.label}
              </Link>
            ))}
          </nav>

          {/* Правая часть - иконки действий и аутентификация */}
          <div className="flex items-center gap-4 flex-shrink-0">
            {/* Action Icons (desktop) */}
            <div className="hidden md:flex items-center gap-4">
              {/* Поиск */}
              <Link
                href="/catalog?focusSearch=true"
                aria-label="Поиск"
                className="p-2 text-text-primary hover:text-text-secondary transition-colors duration-short focus:outline-none focus:ring-2 focus:ring-primary focus:ring-offset-2 rounded-sm"
              >
                <Search className="w-6 h-6" />
              </Link>

              {/* Избранное */}
              <Link
                href="/profile/favorites"
                aria-label="Избранное"
                className="p-2 text-text-primary hover:text-text-secondary transition-colors duration-short focus:outline-none focus:ring-2 focus:ring-primary focus:ring-offset-2 rounded-sm"
              >
                <Heart className="w-6 h-6" />
              </Link>

              {/* Корзина с Badge */}
              <Link
                href="/cart"
                aria-label={`Корзина (${cartItemsCount} товаров)`}
                className="relative p-2 text-text-primary hover:text-text-secondary transition-colors duration-short focus:outline-none focus:ring-2 focus:ring-primary focus:ring-offset-2 rounded-sm"
              >
                <ShoppingCart className="w-6 h-6" />
                {cartItemsCount > 0 && (
                  <span
                    data-testid="cart-count"
                    className="absolute top-0 right-0 flex items-center justify-center min-w-[18px] h-[18px] px-1 text-[10px] font-bold bg-accent-danger-bg text-accent-danger rounded-full"
                  >
                    {cartItemsCount > 99 ? '99+' : cartItemsCount}
                  </span>
                )}
              </Link>
            </div>

            {/* Авторизация/Профиль (desktop) */}
            <div className="hidden md:flex items-center gap-2">
              {isAuthenticated && user ? (
                <>
                  <span className="text-body-s text-text-secondary">
                    Привет, {user.first_name}!
                  </span>
                  <Link
                    href="/profile"
                    aria-label="Профиль"
                    className="p-2 text-text-primary hover:text-text-secondary transition-colors duration-short focus:outline-none focus:ring-2 focus:ring-primary focus:ring-offset-2 rounded-sm"
                  >
                    <User className="w-6 h-6" />
                  </Link>
                  <button
                    onClick={handleLogout}
                    data-testid="logout-button"
                    aria-label="Выйти из аккаунта"
                    className="p-2 text-text-primary hover:text-text-secondary transition-colors duration-short focus:outline-none focus:ring-2 focus:ring-primary focus:ring-offset-2 rounded-sm"
                  >
                    <LogOut className="w-6 h-6" />
                  </button>
                </>
              ) : (
                <>
                  <Link href="/register">
                    <Button variant="secondary" size="small">
                      Регистрация
                    </Button>
                  </Link>
                  <Link href="/login">
                    <Button variant="primary" size="small">
                      Войти
                    </Button>
                  </Link>
                </>
              )}
            </div>

            {/* Мобильное меню - кнопка */}
            <button
              ref={menuButtonRef}
              className="md:hidden p-2 text-text-primary hover:text-text-secondary transition-colors duration-short focus:outline-none focus:ring-2 focus:ring-primary focus:ring-offset-2 rounded-sm"
              onClick={() => setIsMobileMenuOpen(!isMobileMenuOpen)}
              aria-label={isMobileMenuOpen ? 'Закрыть меню' : 'Открыть меню'}
              aria-expanded={isMobileMenuOpen}
            >
              {isMobileMenuOpen ? <X className="w-6 h-6" /> : <Menu className="w-6 h-6" />}
            </button>
          </div>
        </div>

        {/* Мобильная навигация */}
        {isMobileMenuOpen && (
          <div ref={mobileMenuRef} className="md:hidden py-4 border-t border-neutral-300">
            <nav aria-label="Мобильная навигация" className="flex flex-col space-y-2">
              {/* Основная навигация */}
              {navigationItems.map(item => (
                <Link
                  key={item.href}
                  href={item.href}
                  className={`block px-3 py-2 text-body-m font-medium rounded-sm transition-colors duration-short ${isActivePage(item.href)
                    ? 'text-text-primary bg-neutral-200'
                    : 'text-text-primary hover:text-text-secondary hover:bg-neutral-200'
                    }`}
                  onClick={() => setIsMobileMenuOpen(false)}
                >
                  {item.label}
                </Link>
              ))}

              {/* Мобильные иконки действий и авторизация */}
              <div className="flex flex-col gap-2 px-3 py-2 border-t border-neutral-300 mt-2 pt-4">
                {isAuthenticated && user ? (
                  <>
                    {/* Приветствие сверху */}
                    <span className="text-body-s text-text-secondary mb-2">
                      Привет, {user.first_name}!
                    </span>
                    {/* Все иконки в одном ряду */}
                    <div className="flex items-center gap-4">
                      <Link
                        href="/catalog?focusSearch=true"
                        onClick={() => setIsMobileMenuOpen(false)}
                        aria-label="Поиск"
                        className="p-2 text-text-primary hover:text-text-secondary transition-colors"
                      >
                        <Search className="w-6 h-6" />
                      </Link>
                      <Link
                        href="/profile/favorites"
                        onClick={() => setIsMobileMenuOpen(false)}
                        aria-label="Избранное"
                        className="p-2 text-text-primary hover:text-text-secondary transition-colors"
                      >
                        <Heart className="w-6 h-6" />
                      </Link>
                      <Link
                        href="/cart"
                        onClick={() => setIsMobileMenuOpen(false)}
                        aria-label="Корзина"
                        className="relative p-2 text-text-primary hover:text-text-secondary transition-colors"
                      >
                        <ShoppingCart className="w-6 h-6" />
                        {cartItemsCount > 0 && (
                          <span
                            data-testid="cart-count"
                            className="absolute top-0 right-0 flex items-center justify-center min-w-[18px] h-[18px] px-1 text-[10px] font-bold bg-accent-danger-bg text-accent-danger rounded-full"
                          >
                            {cartItemsCount > 99 ? '99+' : cartItemsCount}
                          </span>
                        )}
                      </Link>
                      <Link
                        href="/profile"
                        onClick={() => setIsMobileMenuOpen(false)}
                        aria-label="Профиль"
                        className="p-2 text-text-primary hover:text-text-secondary transition-colors"
                      >
                        <User className="w-6 h-6" />
                      </Link>
                      <button
                        onClick={() => {
                          handleLogout();
                          setIsMobileMenuOpen(false);
                        }}
                        data-testid="logout-button-mobile"
                        aria-label="Выйти из аккаунта"
                        className="p-2 text-text-primary hover:text-text-secondary transition-colors"
                      >
                        <LogOut className="w-6 h-6" />
                      </button>
                    </div>
                  </>
                ) : (
                  <>
                    {/* Иконки для неавторизованных */}
                    <div className="flex items-center gap-4 mb-4">
                      <Link
                        href="/catalog?focusSearch=true"
                        onClick={() => setIsMobileMenuOpen(false)}
                        aria-label="Поиск"
                        className="p-2 text-text-primary hover:text-text-secondary transition-colors"
                      >
                        <Search className="w-6 h-6" />
                      </Link>
                      <Link
                        href="/profile/favorites"
                        onClick={() => setIsMobileMenuOpen(false)}
                        aria-label="Избранное"
                        className="p-2 text-text-primary hover:text-text-secondary transition-colors"
                      >
                        <Heart className="w-6 h-6" />
                      </Link>
                      <Link
                        href="/cart"
                        onClick={() => setIsMobileMenuOpen(false)}
                        aria-label="Корзина"
                        className="relative p-2 text-text-primary hover:text-text-secondary transition-colors"
                      >
                        <ShoppingCart className="w-6 h-6" />
                        {cartItemsCount > 0 && (
                          <span
                            data-testid="cart-count"
                            className="absolute top-0 right-0 flex items-center justify-center min-w-[18px] h-[18px] px-1 text-[10px] font-bold bg-accent-danger-bg text-accent-danger rounded-full"
                          >
                            {cartItemsCount > 99 ? '99+' : cartItemsCount}
                          </span>
                        )}
                      </Link>
                    </div>
                    {/* Кнопки авторизации */}
                    <Link href="/register" onClick={() => setIsMobileMenuOpen(false)}>
                      <Button variant="secondary" size="small" className="w-full">
                        Регистрация
                      </Button>
                    </Link>
                    <Link href="/login" onClick={() => setIsMobileMenuOpen(false)}>
                      <Button variant="primary" size="small" className="w-full">
                        Войти
                      </Button>
                    </Link>
                  </>
                )}
              </div>
            </nav>
          </div>
        )}
      </div>
    </header>
  );
};

export default Header;
