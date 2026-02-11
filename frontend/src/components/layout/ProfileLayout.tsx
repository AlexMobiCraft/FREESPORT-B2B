'use client';

/**
 * ProfileLayout Component
 * Layout компонент для личного кабинета с боковой навигацией (desktop) и табами (mobile)
 * Story 16.1 - AC: 1
 */

import React from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { User, ShoppingBag, MapPin, Heart, Building } from 'lucide-react';
import { authSelectors } from '@/stores/authStore';

/**
 * Элемент навигации профиля
 */
interface NavigationItem {
  label: string;
  href: string;
  icon: React.ElementType;
  b2bOnly?: boolean;
}

/**
 * Props для ProfileLayout компонента
 */
interface ProfileLayoutProps {
  children: React.ReactNode;
}

/**
 * Список навигационных элементов личного кабинета
 */
const navigationItems: NavigationItem[] = [
  { label: 'Профиль', href: '/profile', icon: User },
  { label: 'Заказы', href: '/profile/orders', icon: ShoppingBag },
  { label: 'Адреса', href: '/profile/addresses', icon: MapPin },
  { label: 'Избранное', href: '/profile/favorites', icon: Heart },
  { label: 'Реквизиты', href: '/profile/requisites', icon: Building, b2bOnly: true },
];

/**
 * Компонент навигационного элемента для sidebar (desktop)
 */
const SidebarNavItem: React.FC<{ item: NavigationItem; isActive: boolean }> = ({
  item,
  isActive,
}) => {
  const Icon = item.icon;

  return (
    <Link
      href={item.href}
      className={`
        flex items-center gap-3 px-4 py-3 rounded-lg transition-colors duration-150
        ${
          isActive
            ? 'bg-primary-subtle text-primary font-semibold'
            : 'text-neutral-700 hover:bg-neutral-200 hover:text-neutral-900'
        }
      `}
    >
      <Icon size={20} className={isActive ? 'text-primary' : 'text-neutral-500'} />
      <span className="text-body-m">{item.label}</span>
    </Link>
  );
};

/**
 * Компонент табов для мобильной навигации
 */
const MobileTabItem: React.FC<{ item: NavigationItem; isActive: boolean }> = ({
  item,
  isActive,
}) => {
  const Icon = item.icon;

  return (
    <Link
      href={item.href}
      className={`
        flex flex-col items-center justify-center gap-1 px-4 py-2 min-w-[80px]
        border-b-2 transition-colors duration-150 snap-start
        ${
          isActive
            ? 'border-primary text-primary'
            : 'border-transparent text-neutral-600 hover:text-neutral-900'
        }
      `}
    >
      <Icon size={20} />
      <span className="text-body-s whitespace-nowrap">{item.label}</span>
    </Link>
  );
};

/**
 * ProfileLayout - основной компонент layout личного кабинета
 * Desktop: боковое меню 280px с навигацией
 * Mobile/Tablet: горизонтальные Tabs с scroll-snap
 */
const ProfileLayout: React.FC<ProfileLayoutProps> = ({ children }) => {
  const pathname = usePathname();
  const isB2B = authSelectors.useIsB2BUser();

  /**
   * Определяет, является ли путь активным
   * Для /profile — точное совпадение, для остальных — startsWith
   */
  const isActiveRoute = (href: string): boolean => {
    if (href === '/profile') {
      return pathname === '/profile';
    }
    return pathname.startsWith(href);
  };

  // Фильтруем навигацию: B2B-only пункты показываем только для B2B пользователей
  const filteredNavItems = navigationItems.filter(item => !item.b2bOnly || isB2B);

  return (
    <div className="min-h-screen bg-canvas">
      {/* Mobile/Tablet Tabs - видны до lg breakpoint */}
      <nav className="lg:hidden sticky top-[60px] left-0 right-0 z-40 bg-white border-b border-neutral-300">
        <div className="flex overflow-x-auto scroll-snap-x-mandatory scrollbar-hide">
          {filteredNavItems.map(item => (
            <MobileTabItem key={item.href} item={item} isActive={isActiveRoute(item.href)} />
          ))}
        </div>
      </nav>

      {/* Desktop Layout: Sidebar + Content */}
      <div className="max-w-[1280px] mx-auto px-4 lg:px-6 py-6 lg:py-8 lg:pt-6">
        <div className="lg:grid lg:grid-cols-[280px_1fr] lg:gap-6">
          {/* Desktop Sidebar - скрыт на mobile/tablet */}
          <aside className="hidden lg:block">
            <div className="sticky top-[76px]">
              <nav className="bg-panel rounded-2xl p-4 shadow-default">
                <h2 className="text-title-m text-neutral-900 mb-4 px-4">Личный кабинет</h2>
                <div className="flex flex-col gap-1">
                  {filteredNavItems.map(item => (
                    <SidebarNavItem
                      key={item.href}
                      item={item}
                      isActive={isActiveRoute(item.href)}
                    />
                  ))}
                </div>
              </nav>
            </div>
          </aside>

          {/* Main Content Area */}
          <main className="min-w-0">
            <div className="bg-panel rounded-2xl p-6 shadow-default">{children}</div>
          </main>
        </div>
      </div>
    </div>
  );
};

export default ProfileLayout;
