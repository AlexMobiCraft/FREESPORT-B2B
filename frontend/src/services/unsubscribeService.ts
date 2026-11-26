import apiClient from './api-client';

export type UnsubscribeResponse = { status: 'processed' };
export type UnsubscribeErrorKind = 'invalid_token' | 'throttled' | 'server_error' | 'network_error';

export class UnsubscribeServiceError extends Error {
  constructor(kind: UnsubscribeErrorKind) {
    super(kind);
    this.name = 'UnsubscribeServiceError';
  }
}

export const unsubscribeService = {
  async unsubscribe(token: string): Promise<UnsubscribeResponse> {
    try {
      const { data } = await apiClient.post<UnsubscribeResponse>(
        '/newsletter/unsubscribe/',
        { token },
        { skipAuth: true, withCredentials: false }
      );
      return data;
    } catch (error: unknown) {
      if (error && typeof error === 'object' && 'response' in error) {
        const status = (error as { response?: { status?: number } }).response?.status;
        if (status === 400) throw new UnsubscribeServiceError('invalid_token');
        if (status === 429) throw new UnsubscribeServiceError('throttled');
        if (status && status >= 500) throw new UnsubscribeServiceError('server_error');
      }
      throw new UnsubscribeServiceError('network_error');
    }
  },
};
