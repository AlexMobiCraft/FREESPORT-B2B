import type { Metadata } from 'next';
import Link from 'next/link';

// Страница рендерится внутри корневого layout, поэтому своих <html>/<body> здесь быть
// не должно — вложенный документ ломает разметку 404-ответа.
export const metadata: Metadata = {
  title: 'Страница не найдена | OPTISPORT',
  robots: { index: false, follow: false },
};

export default function NotFound() {
  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        minHeight: '100vh',
        fontFamily: 'sans-serif',
        textAlign: 'center',
        padding: '1rem',
      }}
    >
      <h1 style={{ fontSize: '6rem', fontWeight: 700, margin: 0, color: '#111' }}>404</h1>
      <p style={{ fontSize: '1.25rem', color: '#555', margin: '1rem 0 2rem' }}>
        Страница не найдена
      </p>
      <Link
        href="/"
        style={{
          padding: '0.75rem 1.5rem',
          background: '#111',
          color: '#fff',
          borderRadius: '0.375rem',
          textDecoration: 'none',
          fontSize: '0.875rem',
        }}
      >
        На главную
      </Link>
    </div>
  );
}
