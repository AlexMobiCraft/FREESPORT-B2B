/**
 * Footer Component (Story 12.7 - обновлено под Design System v2.0)
 */

import React from 'react';
import Link from 'next/link';

export interface FooterColumn {
  title: string;
  links: { label: string; href: string }[];
}

export interface SocialLink {
  name: string;
  href: string;
  icon: React.ReactNode;
}

export interface FooterProps {
  columns?: FooterColumn[];
  socialLinks?: SocialLink[];
  copyright?: string;
}

const DEFAULT_COLUMNS: FooterColumn[] = [
  {
    title: 'Каталог',
    links: [
      { label: 'Фитнес и атлетика', href: '/catalog?category=fitnes-i-atletika' },
      { label: 'Спортивные игры', href: '/catalog?category=sportivnye-igry' },
      { label: 'Единоборства', href: '/catalog?category=edinoborstva' },
      { label: 'Плавание', href: '/catalog?category=plavanie' },
      { label: 'Гимнастика и танцы', href: '/catalog?category=gimnastika-i-tantsy' },
      { label: 'Зимние товары', href: '/catalog?category=zimnie-tovary' },
      { label: 'Оборудование', href: '/catalog?category=oborudovanie' },
      { label: 'Детский транспорт', href: '/catalog?category=detskiy-transport' },
      { label: 'Спортивные комплексы и батуты', href: '/catalog?category=sportivnye-kompleksy-i-batuty' },
      { label: 'Бассейны, пляж, аксессуары', href: '/catalog?category=basseyny-plyazh-aksessuary' },
      { label: 'Туризм', href: '/catalog?category=turizm' },
      { label: 'Сувенирная продукция', href: '/catalog?category=suvenirnaya-produktsiya' },
    ],
  },
  {
    title: 'Компания',
    links: [
      { label: 'Личный кабинет', href: ' /profile' },
      { label: 'Реквизиты', href: '/requisites' },
      { label: 'Политика конфиденциальности', href: '/policy' },
    ],
  },
  {
    title: 'Клиентам',
    links: [
      { label: 'Памятка клиенту', href: ' /home' },
      { label: 'Маркетинговые материалы', href: '/home' },
      { label: 'Условия сотрудничества', href: '/home' },
      { label: 'Условия доставки', href: '/delivery' },
      { label: 'Розница', href: '/home' },
    ],
  },
  {
    title: 'Информация',
    links: [
      { label: 'О нас', href: '/about' },
      { label: 'Доставка', href: '/delivery' },
      { label: 'Возврат', href: '/returns' },
    ],
  },
  {
    title: 'Контакты',
    links: [
      { label: '+7 968 273-21-68', href: 'tel:+79682732168' },
      { label: 'info@freesport.ru', href: 'mailto:info@freesport.ru' },
      { label: 'г. Ставрополь, ул. Коломийцева, 40/1', href: '#' },
    ],
  },
];

const DEFAULT_SOCIAL_LINKS: SocialLink[] = [
  {
    name: 'VK',
    href: 'https://vk.com/freesport',
    icon: (
      <svg className="w-6 h-6" fill="currentColor" viewBox="0 0 24 24" aria-hidden="true">
        <path d="M15.07 2H8.93C3.33 2 2 3.33 2 8.93v6.14C2 20.67 3.33 22 8.93 22h6.14c5.6 0 6.93-1.33 6.93-6.93V8.93C22 3.33 20.67 2 15.07 2zm3.35 14.63h-1.4c-.46 0-.6-.37-1.44-1.2-.72-.72-1.04-.82-1.22-.82-.25 0-.32.07-.32.4v1.1c0 .3-.09.47-1.01.47-1.48 0-3.11-.89-4.26-2.53-1.73-2.31-2.2-4.05-2.2-4.41 0-.18.07-.35.4-.35h1.4c.3 0 .41.13.52.45.57 1.58 1.53 2.96 1.92 2.96.15 0 .21-.07.21-.44v-1.73c-.06-.98-.57-1.06-.57-1.41 0-.15.13-.3.32-.3h2.2c.25 0 .34.13.34.43v2.33c0 .25.11.34.18.34.15 0 .27-.09.54-.36 1.01-1.12 1.73-2.86 1.73-2.86.09-.2.23-.35.53-.35h1.4c.35 0 .43.18.35.43-.15.69-1.61 2.95-1.61 2.95-.12.2-.16.29 0 .51.12.15.49.48.74.77.46.52.82.96.92 1.26.09.3-.07.45-.38.45z" />
      </svg>
    ),
  },
  {
    name: 'Telegram',
    href: 'https://t.me/freesport',
    icon: (
      <svg className="w-6 h-6" fill="currentColor" viewBox="0 0 24 24" aria-hidden="true">
        <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm4.64 6.8c-.15 1.58-.8 5.42-1.13 7.19-.14.75-.42 1-.68 1.03-.58.05-1.02-.38-1.58-.75-.88-.58-1.38-.94-2.23-1.5-.99-.65-.35-1.01.22-1.59.15-.15 2.71-2.48 2.76-2.69.01-.03.01-.14-.07-.2-.08-.06-.19-.04-.27-.02-.12.02-1.97 1.25-5.56 3.67-.53.36-.99.53-1.39.52-.46-.01-1.34-.26-1.99-.47-.8-.26-1.43-.4-1.38-.85.03-.23.38-.47 1.06-.7 4.15-1.81 6.92-3 8.3-3.58 3.96-1.65 4.78-1.94 5.32-1.95.12 0 .38.03.55.17.14.11.18.27.2.38-.01.06.01.24 0 .38z" />
      </svg>
    ),
  },
  {
    name: 'YouTube',
    href: 'https://youtube.com/@freesport',
    icon: (
      <svg className="w-6 h-6" fill="currentColor" viewBox="0 0 24 24" aria-hidden="true">
        <path d="M23.498 6.186a3.016 3.016 0 0 0-2.122-2.136C19.505 3.545 12 3.545 12 3.545s-7.505 0-9.377.505A3.017 3.017 0 0 0 .502 6.186C0 8.07 0 12 0 12s0 3.93.502 5.814a3.016 3.016 0 0 0 2.122 2.136c1.871.505 9.376.505 9.376.505s7.505 0 9.377-.505a3.015 3.015 0 0 0 2.122-2.136C24 15.93 24 12 24 12s0-3.93-.502-5.814zM9.545 15.568V8.432L15.818 12l-6.273 3.568z" />
      </svg>
    ),
  },
];

export const Footer: React.FC<FooterProps> = ({
  columns = DEFAULT_COLUMNS,
  socialLinks = DEFAULT_SOCIAL_LINKS,
  copyright = '© 2026 FREESPORT. Все права защищены.',
}) => {
  return (
    <footer className="bg-[#111827] text-white py-12" role="contentinfo">
      <div className="max-w-[1280px] mx-auto px-3 md:px-4 lg:px-6">
        {/* Колонки */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-8 mb-8">
          {columns.map((column, index) => (
            <div key={index}>
              <h3 className="font-semibold mb-4">{column.title}</h3>
              <ul className="space-y-2">
                {column.links.map((link, linkIndex) => (
                  <li key={linkIndex}>
                    <Link
                      href={link.href}
                      className="text-sm text-[#9ca3af] hover:text-white transition-colors"
                    >
                      {link.label}
                    </Link>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>

        {/* Социальные сети и copyright */}
        <div className="border-t border-neutral-700 pt-8 flex flex-col md:flex-row justify-between items-center gap-4">
          {/* Социальные иконки */}
          <div className="flex gap-4">
            {socialLinks.map((social, index) => (
              <a
                key={index}
                href={social.href}
                target="_blank"
                rel="noopener noreferrer"
                className="hover:opacity-80 transition-opacity"
                aria-label={social.name}
              >
                {social.icon}
              </a>
            ))}
          </div>

          {/* Copyright */}
          <p className="text-xs text-neutral-500">{copyright}</p>
        </div>
      </div>
    </footer>
  );
};

Footer.displayName = 'Footer';

export default Footer;
