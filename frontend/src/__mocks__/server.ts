/**
 * MSW Server Setup
 * Story 28.4 - Защищенные маршруты и управление сессиями
 *
 * Настройка MSW server для тестирования
 */

import { setupServer } from 'msw/node';
import { handlers } from './handlers';

// Setup MSW server с handlers
export const server = setupServer(...handlers);
