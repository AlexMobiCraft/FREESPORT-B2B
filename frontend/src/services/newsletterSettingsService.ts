import apiClient from './api-client';
import type { components } from '@/types/api.generated';

/** Статус подписки адреса учётной записи; форма ответа — из контракта. */
export type NewsletterStatus = components['schemas']['NewsletterStatusResponse'];

/**
 * Рассылка в личном кабинете. Подписка ищется сервером по email учётной
 * записи — адрес в запрос не передаётся.
 */
export const newsletterSettingsService = {
  async getStatus(): Promise<NewsletterStatus> {
    const { data } = await apiClient.get<NewsletterStatus>('/newsletter/me/');
    return data;
  },

  async unsubscribe(): Promise<NewsletterStatus> {
    const { data } = await apiClient.post<NewsletterStatus>('/newsletter/me/unsubscribe/');
    return data;
  },
};
