import { beforeEach, describe, expect, it, vi } from 'vitest';
import apiClient from '../api-client';
import { UnsubscribeServiceError, unsubscribeService } from '../unsubscribeService';

vi.mock('../api-client');

describe('unsubscribeService', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('отправляет только токен без JWT и cookies', async () => {
    vi.mocked(apiClient.post).mockResolvedValueOnce({ data: { status: 'processed' } });

    await unsubscribeService.unsubscribe('opaque-token');

    expect(apiClient.post).toHaveBeenCalledWith(
      '/newsletter/unsubscribe/',
      { token: 'opaque-token' },
      { skipAuth: true, withCredentials: false }
    );
  });

  it.each([
    [400, 'invalid_token'],
    [429, 'throttled'],
    [503, 'server_error'],
  ] as const)('преобразует HTTP %i в %s', async (httpStatus, expectedMessage) => {
    vi.mocked(apiClient.post).mockRejectedValueOnce({ response: { status: httpStatus } });

    await expect(unsubscribeService.unsubscribe('opaque-token')).rejects.toMatchObject({
      message: expectedMessage,
    });
  });

  it('преобразует сетевой отказ в восстанавливаемую ошибку', async () => {
    vi.mocked(apiClient.post).mockRejectedValueOnce(new Error('network'));

    const request = unsubscribeService.unsubscribe('opaque-token');
    await expect(request).rejects.toBeInstanceOf(UnsubscribeServiceError);
    await expect(request).rejects.toMatchObject({ message: 'network_error' });
  });
});
