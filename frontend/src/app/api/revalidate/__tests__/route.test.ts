import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { NextRequest } from 'next/server';

vi.mock('next/cache', () => ({ revalidatePath: vi.fn() }));

import { revalidatePath } from 'next/cache';
import { POST } from '../route';

function makeRequest(secret: string | null, body: unknown = { path: '/oferta' }) {
  const headers: Record<string, string> = { 'content-type': 'application/json' };
  if (secret !== null) headers['x-revalidate-secret'] = secret;
  return new NextRequest('http://frontend:3000/api/revalidate', {
    method: 'POST',
    headers,
    body: JSON.stringify(body),
  });
}

describe('POST /api/revalidate', () => {
  beforeEach(() => {
    vi.mocked(revalidatePath).mockClear();
  });

  afterEach(() => {
    vi.unstubAllEnvs();
  });

  it('сбрасывает кэш пути при верном секрете', async () => {
    vi.stubEnv('REVALIDATE_SECRET', 's3cret');

    const response = await POST(makeRequest('s3cret'));

    expect(response.status).toBe(200);
    expect(await response.json()).toEqual({ revalidated: true, path: '/oferta' });
    expect(revalidatePath).toHaveBeenCalledWith('/oferta');
  });

  it('отклоняет неверный секрет', async () => {
    vi.stubEnv('REVALIDATE_SECRET', 's3cret');

    const response = await POST(makeRequest('wrong'));

    expect(response.status).toBe(401);
    expect(revalidatePath).not.toHaveBeenCalled();
  });

  it('отклоняет запрос без заголовка секрета', async () => {
    vi.stubEnv('REVALIDATE_SECRET', 's3cret');

    const response = await POST(makeRequest(null));

    expect(response.status).toBe(401);
    expect(revalidatePath).not.toHaveBeenCalled();
  });

  it.each([
    ['пустой', ''],
    ['незаданный', undefined],
  ])('закрыт, когда секрет на сервере %s, даже при пустом заголовке', async (_label, value) => {
    vi.stubEnv('REVALIDATE_SECRET', value);

    const response = await POST(makeRequest(''));

    expect(response.status).toBe(401);
    expect(revalidatePath).not.toHaveBeenCalled();
  });

  it('возвращает 400 без пути', async () => {
    vi.stubEnv('REVALIDATE_SECRET', 's3cret');

    const response = await POST(makeRequest('s3cret', {}));

    expect(response.status).toBe(400);
    expect(revalidatePath).not.toHaveBeenCalled();
  });
});
