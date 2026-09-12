import path from 'path';
import type { NextConfig } from 'next';

const nextConfig: NextConfig = {
  // Настройки для Docker deployment
  // output: 'standalone', // Отключено: вызывает проблемы с next start

  // Experimental features
  experimental: {
    // Убрана оптимизация CSS из-за ошибки с critters
  },

  // Настройки Turbopack (теперь стабильная функция)
  turbopack: {
    rules: {
      '*.svg': ['@svgr/webpack'],
    },
  },

  // Настройки изображений
  images: {
    // Отключаем оптимизацию изображений (unoptimized: true) для всех окружений,
    // чтобы ссылки на изображения всегда были прямыми (например, /media/...),
    // как того требует конфигурация проекта.
    unoptimized: true,
    remotePatterns: [
      {
        protocol: 'http',
        hostname: 'localhost',
      },
      {
        protocol: 'http',
        hostname: '127.0.0.1',
      },
      {
        protocol: 'http',
        hostname: 'backend',
      },
      {
        protocol: 'http',
        hostname: 'nginx',
      },
      {
        protocol: 'https',
        hostname: 'optisport.ru',
      },
      {
        protocol: 'https',
        hostname: 'cdn.optisport.ru',
      },
      {
        protocol: 'https',
        hostname: '**.optisport.ru',
      },
      {
        protocol: 'https',
        hostname: 'example.com', // Для тестов
      },
    ],
    formats: ['image/webp', 'image/avif'],
  },

  // Разрешённые origin для dev окружения (Next.js 15 warning)
  allowedDevOrigins: ['localhost', '127.0.0.1'],

  // Переписывание URL для API прокси в разработке
  async rewrites() {
    return [
      {
        source: '/api/:path*',
        destination: process.env.INTERNAL_API_URL
          ? `${process.env.INTERNAL_API_URL}/api/v1/:path*`
          : process.env.NEXT_PUBLIC_API_URL
            ? `${process.env.NEXT_PUBLIC_API_URL}/:path*`
            : 'http://localhost:8001/api/v1/:path*',
      },
      {
        source: '/media/:path*',
        destination: process.env.NEXT_PUBLIC_MEDIA_URL_INTERNAL
          ? `${process.env.NEXT_PUBLIC_MEDIA_URL_INTERNAL}/media/:path*`
          : 'http://localhost:8001/media/:path*',
      },
      {
        source: '/electric-orange',
        destination: '/electric-orange/index.html',
      },
    ];
  },

  // Редиректы для SEO и миграции URL
  async redirects() {
    return [
      {
        source: '/promotions',
        destination: '/blog',
        permanent: true,
      },
    ];
  },

  // Заголовки безопасности HTML фронтенда (стори 41.5).
  //
  // Граница ответственности: на `location /` nginx выставляет ТОЛЬКО
  // Strict-Transport-Security, и этот одиночный add_header вытесняет там весь
  // унаследованный серверный набор. Значит всё остальное на HTML обязан
  // поставить этот файл — включая X-XSS-Protection, который Django перестал
  // отдавать в 4.0, а nginx на этой локации больше не добавляет.
  //
  // CSP и Permissions-Policy обязаны совпадать ПОСИМВОЛЬНО с
  // docker/nginx/snippets/security-headers*.conf. Общего файла у Next и nginx
  // нет и быть не может, поэтому расхождение ловит тест-страж
  // src/__tests__/next-config-headers.test.ts.
  //
  // Cache-Control здесь НЕ задаётся: в production Next перезаписывает значение
  // из конфига. Срок жизни HTML управляется сегментной опцией `revalidate`
  // (см. src/app/layout.tsx).
  async headers() {
    return [
      {
        source: '/(.*)',
        headers: [
          {
            // SAMEORIGIN, а не DENY: запас на встраивание CMS-страниц сайта
            // друг в друга. Обязан идти согласованно с frame-ancestors ниже —
            // в поддерживающих браузерах CSP перекрывает X-Frame-Options,
            // и пара «SAMEORIGIN + 'none'» молча свела бы запас на нет.
            key: 'X-Frame-Options',
            value: 'SAMEORIGIN',
          },
          {
            key: 'X-Content-Type-Options',
            value: 'nosniff',
          },
          {
            key: 'Referrer-Policy',
            value: 'strict-origin-when-cross-origin',
          },
          {
            // Заголовок устарел (браузеры его не применяют), но его удаление
            // не входит в объём эпика и отдельно объяснялось бы перед
            // регулятором. Источник ровно один — здесь для HTML, сниппеты
            // nginx для остальных поверхностей.
            key: 'X-XSS-Protection',
            value: '1; mode=block',
          },
          {
            // default-src переносится посимвольно из прежнего конфига nginx;
            // добавлена ровно одна директива — frame-ancestors. Ужесточение
            // политики вынесено в tech-debt п. 23: любое сужение default-src
            // ломает встроенную карту Яндекса на /delivery.
            key: 'Content-Security-Policy',
            value:
              "default-src 'self' http: https: data: blob: 'unsafe-inline'; frame-ancestors 'self'",
          },
          {
            // Без interest-cohort: директива снята в Chrome 115+ и даёт
            // "Unrecognized feature" в консоли.
            key: 'Permissions-Policy',
            value:
              'camera=(), microphone=(), geolocation=(), payment=(), usb=(), magnetometer=(), gyroscope=(), accelerometer=()',
          },
        ],
      },
    ];
  },

  // Настройки компиляции
  compiler: {
    // Удаление console.log в продакшене
    removeConsole: process.env.NODE_ENV === 'production',
  },

  // Оптимизация бандла
  webpack: config => {
    config.resolve.alias = {
      ...config.resolve.alias,
      '@': path.resolve(__dirname, 'src'),
      '@/components': path.resolve(__dirname, 'src/components'),
      '@/hooks': path.resolve(__dirname, 'src/hooks'),
      '@/services': path.resolve(__dirname, 'src/services'),
      '@/stores': path.resolve(__dirname, 'src/stores'),
      '@/types': path.resolve(__dirname, 'src/types'),
      '@/utils': path.resolve(__dirname, 'src/utils'),
    };

    return config;
  },

  // Переменные окружения для клиента
  env: {
    CUSTOM_KEY: process.env.CUSTOM_KEY,
  },

  // Настройки TypeScript
  typescript: {
    // Не останавливать сборку при ошибках TypeScript в разработке
    ignoreBuildErrors: false,
  },
};

export default nextConfig;
