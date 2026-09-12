/**
 * Subscribe Service
 * API клиент для подписки на рассылку
 */

import apiClient from './api-client';
import type { SubscribeRequest, SubscribeResponse } from '@/types/api';

export type SubscribeValidationDetails = Record<string, string[]>;

type SubscribeErrorResponse = {
  error?: unknown;
  details?: SubscribeValidationDetails;
};

/**
 * Машинный код отказа с верхнего уровня ответа (например `consent_text_outdated`).
 * Он и есть устойчивый признак случая: текст сообщения правят, HTTP-статус общий
 * для всей валидации.
 */
const getErrorCode = (data: unknown): string | undefined => {
  if (!data || typeof data !== 'object') {
    return undefined;
  }

  const { error } = data as SubscribeErrorResponse;
  return typeof error === 'string' ? error : undefined;
};

const isValidationDetails = (value: unknown): value is SubscribeValidationDetails => {
  if (!value || typeof value !== 'object') {
    return false;
  }

  return Object.values(value).every(
    fieldErrors =>
      Array.isArray(fieldErrors) && fieldErrors.every(message => typeof message === 'string')
  );
};

const getValidationDetails = (data: unknown): SubscribeValidationDetails | undefined => {
  if (!data || typeof data !== 'object') {
    return undefined;
  }

  const errorData = data as SubscribeErrorResponse;
  if (isValidationDetails(errorData.details)) {
    return errorData.details;
  }

  if (isValidationDetails(data)) {
    return data;
  }

  return undefined;
};

export class SubscribeServiceError extends Error {
  details?: SubscribeValidationDetails;
  /** Машинный код с верхнего уровня ответа сервера, если он был. */
  code?: string;

  constructor(message: string, details?: SubscribeValidationDetails, code?: string) {
    super(message);
    this.name = 'SubscribeServiceError';
    this.details = details;
    this.code = code;
  }
}

export const subscribeService = {
  /**
   * Подписаться на email-рассылку
   */
  async subscribe(payload: SubscribeRequest): Promise<SubscribeResponse> {
    try {
      const { data } = await apiClient.post<SubscribeResponse>('/subscribe', payload);
      return data;
    } catch (error: unknown) {
      // Проброс ошибки для обработки в компоненте
      if (error && typeof error === 'object' && 'response' in error) {
        const axiosError = error as {
          response?: { status?: number; data?: unknown };
        };
        const details = getValidationDetails(axiosError.response?.data);
        const code = getErrorCode(axiosError.response?.data);
        if (axiosError.response?.status === 400) {
          throw new SubscribeServiceError('validation_error', details, code);
        }
        if (axiosError.response?.status === 429) {
          throw new SubscribeServiceError('throttled', details, code);
        }
        if (axiosError.response?.status && axiosError.response.status >= 500) {
          throw new SubscribeServiceError('server_error', details, code);
        }
      }
      throw new SubscribeServiceError('network_error');
    }
  },
};
