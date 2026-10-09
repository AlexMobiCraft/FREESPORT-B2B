/**
 * Address Service - API сервис для управления адресами доставки
 * Story 16.3: Управление адресами доставки
 *
 * Endpoints:
 * - GET /api/v1/addresses/ - получить все адреса пользователя
 * - POST /api/v1/addresses/ - создать новый адрес
 * - PUT /api/v1/addresses/{id}/ - обновить адрес
 * - DELETE /api/v1/addresses/{id}/ - удалить адрес
 */

import apiClient from './api-client';
import type { Address, AddressFormData, AddressValidationErrors } from '@/types/address';
import { AxiosError } from 'axios';

/**
 * Класс ошибки валидации адреса
 */
export class AddressValidationError extends Error {
  errors: AddressValidationErrors;

  constructor(errors: AddressValidationErrors) {
    super('Ошибка валидации адреса');
    this.name = 'AddressValidationError';
    this.errors = errors;
  }
}

/**
 * Интерфейс пагинированного ответа от DRF
 */
interface PaginatedResponse<T> {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
}

/**
 * Получить все адреса текущего пользователя
 */
export async function getAddresses(): Promise<Address[]> {
  try {
    const response = await apiClient.get<PaginatedResponse<Address> | Address[]>(
      '/users/addresses/'
    );
    // Поддержка как пагинированного, так и простого ответа
    const data = response.data;
    if (Array.isArray(data)) {
      return data;
    }
    // Пагинированный ответ - извлекаем results
    return data.results || [];
  } catch (error) {
    if (error instanceof AxiosError) {
      if (error.response?.status === 401) {
        throw new Error('Требуется авторизация');
      }
    }
    throw new Error('Не удалось загрузить адреса. Попробуйте снова.');
  }
}

/**
 * Создать новый адрес
 */
export async function createAddress(data: AddressFormData): Promise<Address> {
  try {
    const response = await apiClient.post<Address>('/users/addresses/', data);
    return response.data;
  } catch (error) {
    if (error instanceof AxiosError && error.response) {
      if (error.response.status === 400) {
        throw new AddressValidationError(error.response.data as AddressValidationErrors);
      }
      if (error.response.status === 401) {
        throw new Error('Требуется авторизация');
      }
      if (error.response.status === 403) {
        throw new Error('Доступ запрещен');
      }
    }
    throw new Error('Не удалось создать адрес. Попробуйте снова.');
  }
}

/**
 * Обновить существующий адрес
 */
export async function updateAddress(id: number, data: AddressFormData): Promise<Address> {
  try {
    const response = await apiClient.put<Address>(`/users/addresses/${id}/`, data);
    return response.data;
  } catch (error) {
    if (error instanceof AxiosError && error.response) {
      if (error.response.status === 400) {
        throw new AddressValidationError(error.response.data as AddressValidationErrors);
      }
      if (error.response.status === 401) {
        throw new Error('Требуется авторизация');
      }
      if (error.response.status === 403) {
        throw new Error('Доступ запрещен');
      }
      if (error.response.status === 404) {
        throw new Error('Адрес не найден');
      }
    }
    throw new Error('Не удалось обновить адрес. Попробуйте снова.');
  }
}

/**
 * Удалить адрес
 */
export async function deleteAddress(id: number): Promise<void> {
  try {
    await apiClient.delete(`/users/addresses/${id}/`);
  } catch (error) {
    if (error instanceof AxiosError && error.response) {
      if (error.response.status === 401) {
        throw new Error('Требуется авторизация');
      }
      if (error.response.status === 403) {
        throw new Error('Доступ запрещен');
      }
      if (error.response.status === 404) {
        throw new Error('Адрес не найден');
      }
    }
    throw new Error('Не удалось удалить адрес. Попробуйте снова.');
  }
}

/**
 * Объект сервиса для удобного импорта
 */
export const addressService = {
  getAddresses,
  createAddress,
  updateAddress,
  deleteAddress,
};

export default addressService;
