/**
 * Auth Service Tests
 */
import authService from '../authService';
import { useAuthStore } from '@/stores/authStore';
import { server } from '../../__mocks__/api/server';
import { http, HttpResponse } from 'msw';

describe('authService', () => {
  beforeEach(() => {
    useAuthStore.getState().logout();
    localStorage.clear();
  });

  describe('login', () => {
    test('successfully authenticates user', async () => {
      const result = await authService.login({
        email: 'test@example.com',
        password: 'password123',
      });

      expect(result.access).toBe('mock-access-token');
      expect(result.user.email).toBe('test@example.com');
      expect(useAuthStore.getState().isAuthenticated).toBe(true);
      expect(localStorage.getItem('refreshToken')).toBe('mock-refresh-token');
    });

    test('fails with invalid credentials', async () => {
      await expect(
        authService.login({
          email: 'wrong@example.com',
          password: 'wrong',
        })
      ).rejects.toThrow();
    });

    test('handles network error', async () => {
      server.use(
        http.post('http://localhost:8001/api/v1/auth/login/', () => {
          return HttpResponse.error();
        })
      );

      await expect(
        authService.login({
          email: 'test@example.com',
          password: 'password123',
        })
      ).rejects.toThrow();
    });
  });

  describe('logout', () => {
    test('clears tokens and store', async () => {
      // Setup: login first
      useAuthStore.getState().setTokens('test-access', 'test-refresh');

      await authService.logout();

      expect(useAuthStore.getState().isAuthenticated).toBe(false);
      expect(localStorage.getItem('refreshToken')).toBeNull();
    });
  });

  describe('refreshToken', () => {
    test('updates access token successfully', async () => {
      // Setup: set refresh token
      localStorage.setItem('refreshToken', 'mock-refresh-token');

      // Override handler to return specific token
      server.use(
        http.post('http://localhost:8001/api/v1/auth/refresh/', () => {
          return HttpResponse.json({ access: 'new-mock-access-token' });
        })
      );

      const result = await authService.refreshToken();

      expect(result.access).toBe('new-mock-access-token');
      expect(useAuthStore.getState().accessToken).toBe('new-mock-access-token');
    });

    test('throws error when refresh token is expired', async () => {
      localStorage.setItem('refreshToken', 'expired-token');

      await expect(authService.refreshToken()).rejects.toThrow();
    });

    test('throws error when no refresh token available', async () => {
      localStorage.removeItem('refreshToken');

      await expect(authService.refreshToken()).rejects.toThrow('No refresh token available');
    });
  });
});
