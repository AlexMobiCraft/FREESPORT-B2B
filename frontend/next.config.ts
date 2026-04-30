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
        hostname: 'freesport.ru',
      },
      {
        protocol: 'https',
        hostname: 'cdn.freesport.ru',
      },
      {
        protocol: 'https',
        hostname: '**.freesport.ru',
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

  // Заголовки безопасности
  async headers() {
    return [
      {
        source: '/(.*)',
        headers: [
          {
            key: 'X-Frame-Options',
            value: 'DENY',
          },
          {
            key: 'X-Content-Type-Options',
            value: 'nosniff',
          },
          {
            key: 'Referrer-Policy',
            value: 'strict-origin-when-cross-origin',
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

  // ESLint настройки
  eslint: {
    ignoreDuringBuilds: false,
  },
};

export default nextConfig;
