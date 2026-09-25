/**
 * Login Page — серверная часть (Story 41.18)
 *
 * Читает cookie точки возврата `loginReturnTo` из запроса и передаёт значение
 * клиентской части. Из JS такую cookie надёжно не прочитать: после клиентской
 * навигации (клик по ссылке, редирект middleware на RSC-запрос) Chromium не
 * показывает в `document.cookie` cookie с `Path=/login`, хотя адрес уже `/login`.
 * Запрос на `/login` несёт её всегда. Страница из-за этого динамическая.
 */

import { cookies } from 'next/headers';

import { LOGIN_RETURN_COOKIE } from '@/utils/loginReturn';

import LoginPageClient from './LoginPageClient';

export default async function LoginPage() {
  const cookieStore = await cookies();
  return <LoginPageClient returnCookie={cookieStore.get(LOGIN_RETURN_COOKIE)?.value ?? null} />;
}
