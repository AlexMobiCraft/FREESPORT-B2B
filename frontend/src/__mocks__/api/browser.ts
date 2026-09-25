/**
 * MSW Browser Setup для разработки
 */

import { setupWorker } from 'msw/browser';
import { handlers } from './handlers';

// Создаём MSW worker для браузера
export const worker = setupWorker(...handlers);
