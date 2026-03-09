/**
 * Health check endpoint для Docker и мониторинга
 * Возвращает статус приложения
 */
import { NextResponse } from 'next/server';

export async function GET() {
  try {
    // Базовая проверка работоспособности
    const healthData = {
      status: 'healthy',
      timestamp: new Date().toISOString(),
      service: 'freesport-frontend',
      version: process.env.npm_package_version || '1.0.0',
      environment: process.env.NODE_ENV || 'development',
    };

    return NextResponse.json(healthData, { status: 200 });
  } catch (error) {
    // В случае ошибки возвращаем unhealthy статус
    return NextResponse.json(
      {
        status: 'unhealthy',
        timestamp: new Date().toISOString(),
        service: 'freesport-frontend',
        error: error instanceof Error ? error.message : 'Unknown error',
      },
      { status: 503 }
    );
  }
}
