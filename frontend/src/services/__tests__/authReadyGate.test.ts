/**
 * authReadyGate + request interceptor apiClient:
 * пока AuthProvider восстанавливает сессию, клиентские запросы ждут.
 */

import { describe, test, expect, vi, beforeAll, afterAll, afterEach } from 'vitest';
import { http, HttpResponse } from 'msw';
import { server } from '@/__mocks__/api/server';
import apiClient from '@/services/api-client';
import { holdUntilAuthReady, waitForAuthReady } from '@/services/authReadyGate';

beforeAll(() => server.listen({ onUnhandledRequest: 'warn' }));
afterAll(() => server.close());

/** Дать отработать микрозадачам и таймерам MSW */
const flush = () => new Promise(resolve => setTimeout(resolve, 30));

describe('authReadyGate', () => {
  test('без hold ожидание уже выполнено', async () => {
    const resolved = vi.fn();
    waitForAuthReady().then(resolved);
    await flush();
    expect(resolved).toHaveBeenCalled();
  });

  test('hold держит ожидание до release', async () => {
    const release = holdUntilAuthReady();
    const resolved = vi.fn();
    waitForAuthReady().then(resolved);

    try {
      await flush();
      expect(resolved).not.toHaveBeenCalled();
    } finally {
      release();
    }

    await flush();
    expect(resolved).toHaveBeenCalled();
  });

  test('несколько держателей: запросы уходят, когда отпустили все', async () => {
    const releaseFirst = holdUntilAuthReady();
    const releaseSecond = holdUntilAuthReady();
    const resolved = vi.fn();
    waitForAuthReady().then(resolved);

    try {
      releaseFirst();
      // Повторный release того же держателя не считается за второй
      releaseFirst();
      await flush();
      expect(resolved).not.toHaveBeenCalled();
    } finally {
      releaseFirst();
      releaseSecond();
    }

    await flush();
    expect(resolved).toHaveBeenCalled();
  });

  test('после полного освобождения новый hold начинает новое ожидание', async () => {
    holdUntilAuthReady()();
    const release = holdUntilAuthReady();
    const resolved = vi.fn();
    waitForAuthReady().then(resolved);

    try {
      await flush();
      expect(resolved).not.toHaveBeenCalled();
    } finally {
      release();
    }

    await flush();
    expect(resolved).toHaveBeenCalled();
  });
});

describe('apiClient ждёт восстановления сессии', () => {
  afterEach(() => {
    server.resetHandlers();
  });

  function trackProbe() {
    const hits = vi.fn();
    server.use(
      http.get('*/gate/probe/', () => {
        hits();
        return HttpResponse.json({ ok: true });
      })
    );
    return hits;
  }

  test('запрос не уходит, пока сессия восстанавливается', async () => {
    const hits = trackProbe();
    const release = holdUntilAuthReady();

    const request = apiClient.get('/gate/probe/');
    try {
      await flush();
      expect(hits).not.toHaveBeenCalled();
    } finally {
      // Модульное ожидание переживает тест: не снятое, оно подвесит соседние
      release();
    }

    await request;
    expect(hits).toHaveBeenCalled();
  });

  test('skipAuthWait: запрос инициализации идёт сразу', async () => {
    const hits = trackProbe();
    const release = holdUntilAuthReady();

    try {
      await apiClient.get('/gate/probe/', { skipAuthWait: true });
      expect(hits).toHaveBeenCalled();
    } finally {
      release();
    }
  });

  test('skipAuth: анонимный по замыслу запрос не ждёт', async () => {
    const hits = trackProbe();
    const release = holdUntilAuthReady();

    try {
      await apiClient.get('/gate/probe/', { skipAuth: true });
      expect(hits).toHaveBeenCalled();
    } finally {
      release();
    }
  });
});
