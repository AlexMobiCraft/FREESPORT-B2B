/**
 * MSW Server Setup для Node.js (тестирование)
 */

import { setupServer } from 'msw/node';
import { handlers } from './handlers';

// Создаём MSW server с дефолтными handlers
export const server = setupServer(...handlers);
