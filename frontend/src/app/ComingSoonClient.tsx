'use client';

import { ShoppingCart, Users, TrendingUp } from 'lucide-react';
import { motion } from 'motion/react';
import CookieSettingsButton from '@/components/layout/CookieSettingsButton';

const backgroundImage = '/coming-soon-bg.png';

export default function ComingSoon() {
  const progress = 95; // Development progress percentage

  return (
    <div className="min-h-screen relative flex items-center justify-center p-4 overflow-hidden">
      {/* Background Image */}
      <div
        className="absolute inset-0 bg-cover bg-center"
        style={{
          backgroundImage: `url(${backgroundImage})`,
        }}
      >
        <div className="absolute inset-0 bg-[#3d4f5f]/80 backdrop-blur-sm"></div>
      </div>

      {/* Content */}
      <div className="relative z-10 w-full max-w-4xl">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6 }}
          className="text-center"
        >
          {/* Logo */}
          <motion.div
            initial={{ opacity: 0, scale: 0.9 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ delay: 0.2, duration: 0.5 }}
            className="mb-8"
          >
            <h1 className="text-5xl md:text-7xl text-white mb-2 tracking-tight font-bold">
              OPTI<span className="text-[var(--color-primary)]">SPORT</span>
              .RU
            </h1>
            <div className="w-32 h-1 bg-[var(--color-primary)] mx-auto"></div>
          </motion.div>

          {/* Main Card */}
          <motion.div
            initial={{ opacity: 0, y: 30 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.4, duration: 0.6 }}
            className="bg-white rounded-2xl shadow-2xl p-8 md:p-12 mb-8"
          >
            <h2 className="text-3xl md:text-4xl text-gray-900 mb-4 font-bold">МЫ СКОРО ВЕРНЕМСЯ</h2>
            <p className="text-gray-600 text-lg mb-8">
              Платформа для оптовых и розничных
              <br />
              продаж спортивных товаров
            </p>

            {/* Features */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
              <div className="flex flex-col items-center p-4">
                <div className="w-12 h-12 bg-orange-100 rounded-full flex items-center justify-center mb-3">
                  <ShoppingCart className="w-6 h-6 text-[var(--color-primary)]" />
                </div>
                <h3 className="text-gray-900 mb-1 font-semibold">B2C Магазин</h3>
                <p className="text-sm text-gray-500 text-center">Розничные продажи для всех</p>
              </div>
              <div className="flex flex-col items-center p-4">
                <div className="w-12 h-12 bg-orange-100 rounded-full flex items-center justify-center mb-3">
                  <Users className="w-6 h-6 text-[var(--color-primary)]" />
                </div>
                <h3 className="text-gray-900 mb-1 font-semibold">B2B Решения</h3>
                <p className="text-sm text-gray-500 text-center">Оптовые поставки для бизнеса</p>
              </div>
              <div className="flex flex-col items-center p-4">
                <div className="w-12 h-12 bg-orange-100 rounded-full flex items-center justify-center mb-3">
                  <TrendingUp className="w-6 h-6 text-[var(--color-primary)]" />
                </div>
                <h3 className="text-gray-900 mb-1 font-semibold">Лучшие цены</h3>
                <p className="text-sm text-gray-500 text-center">Конкурентные предложения</p>
              </div>
            </div>

            {/* Progress Bar */}
            <div>
              <div className="flex items-center justify-between mb-2">
                <span className="text-sm text-gray-600 font-medium">РАЗРАБОТКА ИДЕТ ПО ПЛАНУ!</span>
                <span className="text-sm text-[var(--color-primary)] font-bold">{progress}%</span>
              </div>
              <div className="w-full h-3 bg-gray-200 rounded-full overflow-hidden">
                <motion.div
                  initial={{ width: 0 }}
                  animate={{ width: `${progress}%` }}
                  transition={{
                    delay: 0.8,
                    duration: 1.5,
                    ease: 'easeOut',
                  }}
                  className="h-full bg-[var(--color-primary)] rounded-full"
                ></motion.div>
              </div>
            </div>
          </motion.div>

          {/* Footer */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 1, duration: 0.6 }}
            className="text-white/80 text-sm"
          >
            <p>© 2025-2026 OPTISPORT — Все права защищены</p>
            <p className="mt-2">По вопросам сотрудничества: info@optisport.ru</p>
            <CookieSettingsButton className="mt-2 text-white/80 hover:text-white underline-offset-2 hover:underline transition-colors" />
          </motion.div>
        </motion.div>
      </div>
    </div>
  );
}
