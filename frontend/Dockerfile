# Простой Dockerfile для Next.js frontend
FROM node:22-alpine

# Метаданные образа
LABEL maintainer="FREESPORT Dev Team"
LABEL version="1.0"
LABEL description="Next.js frontend для FREESPORT Platform"

# Проверка libc6-compat для совместимости
RUN apk add --no-cache libc6-compat

WORKDIR /app

# Копирование файлов зависимостей и вспомогательных скриптов
COPY package.json package-lock.json* ./
COPY scripts ./scripts

# Установка зависимостей
RUN npm ci --prefer-offline

# Установка Next.js глобально
RUN npm install -g next

# Копирование исходного кода
COPY . .

# Создание .env.local для сборки
ARG NEXT_PUBLIC_API_URL=http://localhost:8001/api/v1
# metadataBase (canonical/OG-ссылки) вычисляется на этапе сборки, поэтому нужен ARG, а не только env
ARG NEXT_PUBLIC_APP_URL=http://localhost:3000
# Внутренний адрес API ДЛЯ MIDDLEWARE: в edge-бандл переменные подставляются на
# этапе сборки, и попадают туда только NEXT_PUBLIC_*. Без этого ARG middleware
# в проде остаётся без внутреннего адреса backend и уходит наружу через nginx.
#
# Переменная выделенная, а не общий NEXT_PUBLIC_API_URL_INTERNAL, и это принципиально:
# подстановка на этапе сборки действует на ВЕСЬ код, включая серверные компоненты.
# Общее имя переключило бы на внутренний http://backend:8000 и страницы /oferta,
# /privacy-policy, а они не шлют X-Forwarded-Proto — при штатном SECURE_SSL_REDIRECT=True
# их запрос уехал бы на https://backend:8000, где TLS нет, и CMS-страницы остались бы
# без данных. Заголовок протокола ставит только запрос из middleware.
ARG NEXT_PUBLIC_MIDDLEWARE_API_URL=http://backend:8000/api/v1
ARG NODE_ENV=production

ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL
ENV NEXT_PUBLIC_APP_URL=$NEXT_PUBLIC_APP_URL
ENV NEXT_PUBLIC_MIDDLEWARE_API_URL=$NEXT_PUBLIC_MIDDLEWARE_API_URL
ENV NODE_ENV=$NODE_ENV
ENV NEXT_TELEMETRY_DISABLED=1

# Сборка Next.js приложения
RUN npm run build

# Открытие порта для Next.js
EXPOSE 3000

# Установка переменных окружения
ENV PORT=3000
ENV HOST=0.0.0.0
ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1

# Проверка работоспособности
HEALTHCHECK --interval=30s --timeout=10s --start-period=45s --retries=5 \
    CMD node -e "require('http').get('http://127.0.0.1:3000/api/health', (res) => { if (res.statusCode === 200) { process.exit(0); } process.exit(1); }).on('error', () => process.exit(1));"

# Запуск приложения
CMD ["npx", "next", "start"]