/**
 * Address Service Tests
 * Story 16.3: Управление адресами доставки (AC: 8)
 */

import { describe, it, expect } from 'vitest';
import { http, HttpResponse } from 'msw';
import { server } from '@/__mocks__/api/server';
import {
  getAddresses,
  createAddress,
  updateAddress,
  deleteAddress,
  AddressValidationError,
} from '../addressService';
import type { Address, AddressFormData } from '@/types/address';

// Mock API URL
const API_URL = 'http://localhost:8001/api/v1';

// Mock data
const mockAddresses: Address[] = [
  {
    id: 1,
    address_type: 'shipping',
    full_name: 'Иван Иванов',
    phone: '+79001234567',
    city: 'Москва',
    street: 'Тверская',
    building: '12',
    building_section: '',
    apartment: '45',
    postal_code: '123456',
    is_default: true,
    full_address: '123456, Москва, Тверская 12, кв. 45',
    created_at: '2025-01-01T00:00:00Z',
    updated_at: '2025-01-01T00:00:00Z',
  },
];

const mockFormData: AddressFormData = {
  address_type: 'shipping',
  full_name: 'Петр Петров',
  phone: '+79009876543',
  city: 'Санкт-Петербург',
  street: 'Невский',
  building: '1',
  apartment: '10',
  postal_code: '191186',
  is_default: false,
};

describe('addressService', () => {
  describe('getAddresses', () => {
    it('returns list of addresses on success', async () => {
      // ARRANGE
      server.use(
        http.get(`${API_URL}/users/addresses/`, () => {
          return HttpResponse.json(mockAddresses);
        })
      );

      // ACT
      const result = await getAddresses();

      // ASSERT
      expect(result).toEqual(mockAddresses);
      expect(result).toHaveLength(1);
    });

    it('throws error on 401 unauthorized', async () => {
      // ARRANGE
      server.use(
        http.get(`${API_URL}/users/addresses/`, () => {
          return HttpResponse.json(
            { detail: 'Authentication credentials were not provided.' },
            { status: 401 }
          );
        })
      );

      // ACT & ASSERT
      await expect(getAddresses()).rejects.toThrow('Требуется авторизация');
    });
  });

  describe('createAddress', () => {
    it('creates new address on success', async () => {
      // ARRANGE
      const newAddress: Address = {
        ...mockFormData,
        id: 2,
        full_address: '191186, Санкт-Петербург, Невский 1, кв. 10',
        created_at: '2025-01-02T00:00:00Z',
        updated_at: '2025-01-02T00:00:00Z',
        building_section: mockFormData.building_section || '',
        apartment: mockFormData.apartment || '',
        is_default: mockFormData.is_default || false,
      };

      server.use(
        http.post(`${API_URL}/users/addresses/`, () => {
          return HttpResponse.json(newAddress, { status: 201 });
        })
      );

      // ACT
      const result = await createAddress(mockFormData);

      // ASSERT
      expect(result.id).toBe(2);
      expect(result.full_name).toBe('Петр Петров');
    });

    it('throws AddressValidationError on 400', async () => {
      // ARRANGE
      server.use(
        http.post(`${API_URL}/users/addresses/`, () => {
          return HttpResponse.json(
            { phone: ['Номер телефона должен быть в формате: +79001234567'] },
            { status: 400 }
          );
        })
      );

      // ACT & ASSERT
      await expect(createAddress(mockFormData)).rejects.toThrow(AddressValidationError);
    });
  });

  describe('updateAddress', () => {
    it('updates address on success', async () => {
      // ARRANGE
      const updatedAddress: Address = {
        ...mockAddresses[0],
        city: 'Екатеринбург',
      };

      server.use(
        http.put(`${API_URL}/users/addresses/1/`, () => {
          return HttpResponse.json(updatedAddress);
        })
      );

      // ACT
      const result = await updateAddress(1, { ...mockFormData, city: 'Екатеринбург' });

      // ASSERT
      expect(result.city).toBe('Екатеринбург');
    });

    it('throws error on 404 not found', async () => {
      // ARRANGE
      server.use(
        http.put(`${API_URL}/users/addresses/999/`, () => {
          return HttpResponse.json({ detail: 'Not found.' }, { status: 404 });
        })
      );

      // ACT & ASSERT
      await expect(updateAddress(999, mockFormData)).rejects.toThrow('Адрес не найден');
    });
  });

  describe('deleteAddress', () => {
    it('deletes address on success', async () => {
      // ARRANGE
      server.use(
        http.delete(`${API_URL}/users/addresses/1/`, () => {
          return new HttpResponse(null, { status: 204 });
        })
      );

      // ACT & ASSERT
      await expect(deleteAddress(1)).resolves.toBeUndefined();
    });

    it('throws error on 404 not found', async () => {
      // ARRANGE
      server.use(
        http.delete(`${API_URL}/users/addresses/999/`, () => {
          return HttpResponse.json({ detail: 'Not found.' }, { status: 404 });
        })
      );

      // ACT & ASSERT
      await expect(deleteAddress(999)).rejects.toThrow('Адрес не найден');
    });
  });
});
