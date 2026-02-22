/**
 * Auth Schemas Unit Tests
 * Story 28.1 - Task 4.1
 * Story 28.3 - Task 6.1 (Password Reset schemas)
 *
 * Unit-тесты для Zod схем валидации
 *
 * AC 8: Unit Tests для loginSchema, registerSchema, passwordResetRequestSchema, passwordResetConfirmSchema
 */

import { describe, test, expect } from 'vitest';
import {
  loginSchema,
  passwordResetConfirmSchema,
  passwordResetRequestSchema,
  registerSchema,
} from '../authSchemas';

describe('loginSchema', () => {
  describe('valid data', () => {
    test('should validate correct email and password', () => {
      const validData = {
        email: 'user@example.com',
        password: 'SecurePass123',
      };

      const result = loginSchema.safeParse(validData);
      expect(result.success).toBe(true);
    });

    test('should validate email with different formats', () => {
      const emails = [
        'user@example.com',
        'user.name@example.com',
        'user+tag@example.co.uk',
        'user123@subdomain.example.com',
      ];

      emails.forEach(email => {
        const result = loginSchema.safeParse({
          email,
          password: 'SecurePass123',
        });
        expect(result.success).toBe(true);
      });
    });
  });

  describe('invalid email', () => {
    test('should reject empty email', () => {
      const result = loginSchema.safeParse({
        email: '',
        password: 'SecurePass123',
      });

      expect(result.success).toBe(false);
      if (!result.success) {
        expect(result.error.issues[0].message).toContain('Email обязателен');
      }
    });

    test('should reject invalid email formats', () => {
      const invalidEmails = ['invalid-email', '@example.com', 'user@', 'user@.com'];

      invalidEmails.forEach(email => {
        const result = loginSchema.safeParse({
          email,
          password: 'SecurePass123',
        });

        expect(result.success).toBe(false);
        if (!result.success) {
          expect(result.error.issues[0].message).toContain('Неверный формат email');
        }
      });
    });
  });

  describe('invalid password', () => {
    test('should reject password shorter than 8 characters', () => {
      const result = loginSchema.safeParse({
        email: 'user@example.com',
        password: 'Pass1',
      });

      expect(result.success).toBe(false);
      if (!result.success) {
        expect(result.error.issues[0].message).toContain('минимум 8 символов');
      }
    });

    test('should reject password without digit', () => {
      const result = loginSchema.safeParse({
        email: 'user@example.com',
        password: 'SecurePass',
      });

      expect(result.success).toBe(false);
      if (!result.success) {
        const messages = result.error.issues.map(i => i.message);
        expect(messages.some(m => m.includes('1 цифру'))).toBe(true);
      }
    });

    test('should reject password without uppercase letter', () => {
      const result = loginSchema.safeParse({
        email: 'user@example.com',
        password: 'securepass123',
      });

      expect(result.success).toBe(false);
      if (!result.success) {
        const messages = result.error.issues.map(i => i.message);
        expect(messages.some(m => m.includes('заглавную букву'))).toBe(true);
      }
    });
  });
});

describe('registerSchema', () => {
  describe('valid data', () => {
    test('should validate correct registration data', () => {
      const validData = {
        first_name: 'Иван',
        email: 'ivan@example.com',
        password: 'SecurePass123',
        confirmPassword: 'SecurePass123',
      };

      const result = registerSchema.safeParse(validData);
      expect(result.success).toBe(true);
    });

    test('should validate with long first name (150 chars)', () => {
      const longName = 'А'.repeat(150);
      const result = registerSchema.safeParse({
        first_name: longName,
        email: 'user@example.com',
        password: 'SecurePass123',
        confirmPassword: 'SecurePass123',
      });

      expect(result.success).toBe(true);
    });
  });

  describe('invalid first_name', () => {
    test('should reject empty first name', () => {
      const result = registerSchema.safeParse({
        first_name: '',
        email: 'user@example.com',
        password: 'SecurePass123',
        confirmPassword: 'SecurePass123',
      });

      expect(result.success).toBe(false);
      if (!result.success) {
        expect(result.error.issues[0].message).toContain('Имя обязательно');
      }
    });

    test('should reject first name longer than 150 characters', () => {
      const tooLongName = 'А'.repeat(151);
      const result = registerSchema.safeParse({
        first_name: tooLongName,
        email: 'user@example.com',
        password: 'SecurePass123',
        confirmPassword: 'SecurePass123',
      });

      expect(result.success).toBe(false);
      if (!result.success) {
        const messages = result.error.issues.map(i => i.message);
        expect(messages.some(m => m.includes('не должно превышать 150 символов'))).toBe(true);
      }
    });
  });

  describe('password confirmation', () => {
    test('should reject when passwords do not match', () => {
      const result = registerSchema.safeParse({
        first_name: 'Иван',
        email: 'user@example.com',
        password: 'SecurePass123',
        confirmPassword: 'DifferentPass456',
      });

      expect(result.success).toBe(false);
      if (!result.success) {
        const messages = result.error.issues.map(i => i.message);
        expect(messages.some(m => m.includes('Пароли не совпадают'))).toBe(true);
      }
    });

    test('should reject empty confirmPassword', () => {
      const result = registerSchema.safeParse({
        first_name: 'Иван',
        email: 'user@example.com',
        password: 'SecurePass123',
        confirmPassword: '',
      });

      expect(result.success).toBe(false);
      if (!result.success) {
        expect(result.error.issues.some(i => i.path.includes('confirmPassword'))).toBe(true);
      }
    });
  });

  describe('password strength requirements', () => {
    test('should reject password without digit', () => {
      const result = registerSchema.safeParse({
        first_name: 'Иван',
        email: 'user@example.com',
        password: 'SecurePass',
        confirmPassword: 'SecurePass',
      });

      expect(result.success).toBe(false);
      if (!result.success) {
        const messages = result.error.issues.map(i => i.message);
        expect(messages.some(m => m.includes('1 цифру'))).toBe(true);
      }
    });

    test('should reject password without uppercase letter', () => {
      const result = registerSchema.safeParse({
        first_name: 'Иван',
        email: 'user@example.com',
        password: 'securepass123',
        confirmPassword: 'securepass123',
      });

      expect(result.success).toBe(false);
      if (!result.success) {
        const messages = result.error.issues.map(i => i.message);
        expect(messages.some(m => m.includes('заглавную букву'))).toBe(true);
      }
    });
  });
});

/**
 * Password Reset Request Schema Tests
 * Story 28.3 - Task 6.1
 * AC 8: Unit-тесты для passwordResetRequestSchema
 */
describe('passwordResetRequestSchema', () => {
  describe('valid data', () => {
    test('should validate correct email', () => {
      const validData = {
        email: 'user@example.com',
      };

      const result = passwordResetRequestSchema.safeParse(validData);
      expect(result.success).toBe(true);
    });

    test('should validate various email formats', () => {
      const emails = [
        'user@example.com',
        'user.name@example.com',
        'user+tag@example.co.uk',
        'user123@subdomain.example.com',
      ];

      emails.forEach(email => {
        const result = passwordResetRequestSchema.safeParse({ email });
        expect(result.success).toBe(true);
      });
    });
  });

  describe('invalid email', () => {
    test('should reject empty email', () => {
      const result = passwordResetRequestSchema.safeParse({
        email: '',
      });

      expect(result.success).toBe(false);
      if (!result.success) {
        expect(result.error.issues[0].message).toContain('Email обязателен');
      }
    });

    test('should reject invalid email formats', () => {
      const invalidEmails = ['invalid-email', '@example.com', 'user@', 'user@.com', 'user'];

      invalidEmails.forEach(email => {
        const result = passwordResetRequestSchema.safeParse({ email });

        expect(result.success).toBe(false);
        if (!result.success) {
          expect(result.error.issues[0].message).toContain('Введите корректный email');
        }
      });
    });
  });
});

/**
 * Password Reset Confirm Schema Tests
 * Story 28.3 - Task 6.1
 * AC 8: Unit-тесты для passwordResetConfirmSchema
 */
describe('passwordResetConfirmSchema', () => {
  describe('valid data', () => {
    test('should validate matching strong passwords', () => {
      const validData = {
        password: 'SecurePass123',
        confirmPassword: 'SecurePass123',
      };

      const result = passwordResetConfirmSchema.safeParse(validData);
      expect(result.success).toBe(true);
    });

    test('should validate password with special characters', () => {
      const validData = {
        password: 'Secure@Pass123!',
        confirmPassword: 'Secure@Pass123!',
      };

      const result = passwordResetConfirmSchema.safeParse(validData);
      expect(result.success).toBe(true);
    });
  });

  describe('password strength validation', () => {
    test('should reject password shorter than 8 characters', () => {
      const result = passwordResetConfirmSchema.safeParse({
        password: 'Pass1',
        confirmPassword: 'Pass1',
      });

      expect(result.success).toBe(false);
      if (!result.success) {
        expect(result.error.issues[0].message).toContain('минимум 8 символов');
      }
    });

    test('should reject password without digit', () => {
      const result = passwordResetConfirmSchema.safeParse({
        password: 'SecurePass',
        confirmPassword: 'SecurePass',
      });

      expect(result.success).toBe(false);
      if (!result.success) {
        const messages = result.error.issues.map(i => i.message);
        expect(messages.some(m => m.includes('1 цифру'))).toBe(true);
      }
    });

    test('should reject password without uppercase letter', () => {
      const result = passwordResetConfirmSchema.safeParse({
        password: 'securepass123',
        confirmPassword: 'securepass123',
      });

      expect(result.success).toBe(false);
      if (!result.success) {
        const messages = result.error.issues.map(i => i.message);
        expect(messages.some(m => m.includes('заглавную букву'))).toBe(true);
      }
    });
  });

  describe('password confirmation matching', () => {
    test('should reject when passwords do not match', () => {
      const result = passwordResetConfirmSchema.safeParse({
        password: 'SecurePass123',
        confirmPassword: 'DifferentPass456',
      });

      expect(result.success).toBe(false);
      if (!result.success) {
        const messages = result.error.issues.map(i => i.message);
        expect(messages.some(m => m.includes('Пароли не совпадают'))).toBe(true);
      }
    });

    test('should reject empty confirmPassword', () => {
      const result = passwordResetConfirmSchema.safeParse({
        password: 'SecurePass123',
        confirmPassword: '',
      });

      expect(result.success).toBe(false);
      if (!result.success) {
        expect(result.error.issues.some(i => i.path.includes('confirmPassword'))).toBe(true);
      }
    });

    test('should reject when confirmPassword differs by case', () => {
      const result = passwordResetConfirmSchema.safeParse({
        password: 'SecurePass123',
        confirmPassword: 'securepass123',
      });

      expect(result.success).toBe(false);
      if (!result.success) {
        const messages = result.error.issues.map(i => i.message);
        expect(messages.some(m => m.includes('Пароли не совпадают'))).toBe(true);
      }
    });
  });
});
