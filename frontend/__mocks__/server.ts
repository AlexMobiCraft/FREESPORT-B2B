/**
 * MSW Server Setup для Node.js окружения (тесты)
 */
import { setupServer } from 'msw/node';
import { handlers } from './handlers';

export const server = setupServer(...handlers);
