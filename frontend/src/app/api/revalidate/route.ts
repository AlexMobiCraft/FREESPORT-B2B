import { revalidatePath } from 'next/cache';
import { NextRequest, NextResponse } from 'next/server';

export async function POST(request: NextRequest) {
  const expected = process.env.REVALIDATE_SECRET;
  const secret = request.headers.get('x-revalidate-secret');

  // Незаданный секрет закрывает маршрут: иначе пустой заголовок совпал бы
  // с пустой переменной окружения и сброс кэша стал бы доступен без секрета.
  if (!expected || secret !== expected) {
    return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
  }

  const { path } = await request.json();

  if (!path || typeof path !== 'string') {
    return NextResponse.json({ error: 'Missing path' }, { status: 400 });
  }

  revalidatePath(path);

  return NextResponse.json({ revalidated: true, path });
}
