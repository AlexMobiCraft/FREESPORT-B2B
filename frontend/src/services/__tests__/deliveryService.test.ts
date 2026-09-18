/**
 * Delivery Service Tests
 * Story 15.3b: Frontend DeliveryOptions Component
 */
import { describe, test, expect } from 'vitest';
import { server } from '@/__mocks__/api/server';
import { http, HttpResponse } from 'msw';
import deliveryService from '../deliveryService';
import { mockDeliveryMethods } from '@/__mocks__/handlers/deliveryHandlers';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8001/api/v1';

describe('deliveryService', () => {
  describe('getDeliveryMethods', () => {
    test('returns list of delivery methods successfully', async () => {
      // Uses default handler from deliveryHandlers
      const methods = await deliveryService.getDeliveryMethods();

      expect(methods).toHaveLength(3);
      expect(methods[0].id).toBe('courier');
      expect(methods[0].name).toBe('Курьер');
      expect(methods[0].is_available).toBe(true);
    });

    test('returns methods with correct structure', async () => {
      const methods = await deliveryService.getDeliveryMethods();

      methods.forEach(method => {
        expect(method).toHaveProperty('id');
        expect(method).toHaveProperty('name');
        expect(method).toHaveProperty('description');
        expect(method).toHaveProperty('icon');
        expect(method).toHaveProperty('is_available');
      });
    });

    test('handles empty response', async () => {
      server.use(
        http.get(`${API_BASE_URL}/delivery/methods/`, () => {
          return HttpResponse.json([]);
        })
      );

      const methods = await deliveryService.getDeliveryMethods();

      expect(methods).toEqual([]);
      expect(methods).toHaveLength(0);
    });

    test('throws on network error', async () => {
      server.use(
        http.get(`${API_BASE_URL}/delivery/methods/`, () => {
          return HttpResponse.error();
        })
      );

      await expect(deliveryService.getDeliveryMethods()).rejects.toThrow();
    });

    test('handles unavailable delivery methods', async () => {
      const methodsWithUnavailable = [
        { ...mockDeliveryMethods[0] },
        { ...mockDeliveryMethods[1], is_available: false },
      ];

      server.use(
        http.get(`${API_BASE_URL}/delivery/methods/`, () => {
          return HttpResponse.json(methodsWithUnavailable);
        })
      );

      const methods = await deliveryService.getDeliveryMethods();

      expect(methods).toHaveLength(2);
      expect(methods[0].is_available).toBe(true);
      expect(methods[1].is_available).toBe(false);
    });
  });
});
