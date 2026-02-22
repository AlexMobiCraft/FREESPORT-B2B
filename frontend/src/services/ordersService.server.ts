/**
 * Orders Service - Server-side methods для SSR
 * Story 16.2: SSR для первичной загрузки данных заказов
 *
 * Использует cookies из request для авторизации на сервере
 */

import { cookies } from 'next/headers';
import type { Order } from '@/types/order';
import type { PaginatedResponse } from '@/types/api';

/**
 * Получает базовый URL API для серверных запросов
 */
function getServerApiUrl(): string {
  // INTERNAL_API_URL - серверная переменная для Docker-сети
  // Fallback на публичный URL
  return (
    process.env.INTERNAL_API_URL ||
    process.env.NEXT_PUBLIC_API_URL_INTERNAL ||
    process.env.NEXT_PUBLIC_API_URL ||
    'http://backend:8000'
  );
}

/**
 * Выполняет серверный fetch с авторизацией через cookies
 */
async function serverFetch<T>(endpoint: string): Promise<T> {
  const cookieStore = await cookies();
  const accessToken = cookieStore.get('accessToken')?.value;

  const baseUrl = getServerApiUrl();
  const url = `${baseUrl}/api/v1${endpoint}`;

  const headers: HeadersInit = {
    'Content-Type': 'application/json',
  };

  // Добавляем Authorization header если есть access token
  if (accessToken) {
    headers['Authorization'] = `Bearer ${accessToken}`;
  }

  // Передаём cookies для сессии
  const cookieHeader = cookieStore
    .getAll()
    .map(c => `${c.name}=${c.value}`)
    .join('; ');

  if (cookieHeader) {
    headers['Cookie'] = cookieHeader;
  }

  const response = await fetch(url, {
    headers,
    cache: 'no-store', // Отключаем кэширование для персонализированных данных
  });

  if (!response.ok) {
    throw new Error(`HTTP ${response.status}: ${response.statusText}`);
  }

  return response.json();
}

/**
 * Получить заказ по ID (Server-side)
 * Используется в Server Components для SSR
 */
export async function getOrderByIdServer(orderId: string): Promise<Order | null> {
  try {
    return await serverFetch<Order>(`/orders/${orderId}/`);
  } catch (error) {
    console.error('Server fetch order error:', error);
    return null;
  }
}

/**
 * Получить список заказов (Server-side)
 * Используется в Server Components для SSR
 */
export async function getOrdersServer(params?: {
  page?: number;
  page_size?: number;
  status?: string;
}): Promise<PaginatedResponse<Order> | null> {
  try {
    const searchParams = new URLSearchParams();
    if (params?.page) searchParams.set('page', String(params.page));
    if (params?.page_size) searchParams.set('page_size', String(params.page_size));
    if (params?.status) searchParams.set('status', params.status);

    const query = searchParams.toString();
    const endpoint = `/orders/${query ? `?${query}` : ''}`;

    return await serverFetch<PaginatedResponse<Order>>(endpoint);
  } catch (error) {
    console.error('Server fetch orders error:', error);
    return null;
  }
}
