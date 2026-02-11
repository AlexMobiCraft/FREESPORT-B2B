# Настройка Email для FREESPORT

> Документация по настройке email сервера для отправки уведомлений.
> Story 29.3: Email Server Configuration

## Обзор

FREESPORT использует email для:

- Уведомления администраторов о новых B2B заявках
- Отправка верификационных писем пользователям
- Системные уведомления об ошибках

## Конфигурация

### Переменные окружения

| Переменная | Описание | Пример |
|------------|----------|--------|
| `EMAIL_BACKEND` | Django email backend | `django.core.mail.backends.smtp.EmailBackend` |
| `EMAIL_HOST` | SMTP сервер | `smtp.yandex.ru` |
| `EMAIL_PORT` | Порт SMTP | `587` |
| `EMAIL_USE_TLS` | Использовать TLS | `True` |
| `EMAIL_USE_SSL` | Использовать SSL | `False` |
| `EMAIL_HOST_USER` | Логин SMTP | `noreply@freesport.ru` |
| `EMAIL_HOST_PASSWORD` | Пароль SMTP | `your-app-password` |
| `DEFAULT_FROM_EMAIL` | Адрес отправителя | `noreply@freesport.ru` |
| `SERVER_EMAIL` | Email сервера для ошибок | `noreply@freesport.ru` |
| `ADMIN_EMAILS` | Список админов (через запятую) | `admin1@freesport.ru,admin2@freesport.ru` |

### Development окружение

В development по умолчанию используется **console backend** — письма выводятся в консоль Docker контейнера:

```bash
# Просмотр логов backend контейнера
docker logs freesport-backend -f
```

Для тестирования с реальной отправкой используйте **Mailhog**:

```bash
# В .env добавьте:
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=mailhog
EMAIL_PORT=1025
EMAIL_USE_TLS=False
```

**Mailhog UI:** <http://localhost:8025>

### Production окружение

#### 1. Yandex.Connect (Яндекс 360 для бизнеса)

**Рекомендуется для домена freesport.ru**

**Шаг 1: Подключение домена**

1. Перейдите в [Яндекс 360 для бизнеса](https://360.yandex.ru/business/) и войдите/зарегистрируйтесь.
2. Добавьте домен (например, `freesport.ru`).
3. **Подтверждение владения:** Добавьте TXT-запись в DNS регистратора (значение выдаст Яндекс).
4. **MX-записи:** Удалите старые MX и добавьте новую:
   - Host: `@`
   - Value: `mx.yandex.net.`
   - Priority: `10`
5. **SPF и DKIM (Важно для анти-спама):**
   - SPF (TXT): `v=spf1 include:_spf.yandex.net ~all`
   - DKIM: В админке 360 -> Почта -> DKIM, скопируйте ключ и добавьте TXT-запись `mail._domainkey`.

**Шаг 2: Создание ящика и пароля**

1. Создайте сотрудника с логином `noreply` (итоговый адрес `noreply@freesport.ru`).
2. Войдите под этим аккаунтом в Яндекс ID.
3. Перейдите в **Управление аккаунтом -> Безопасность -> Пароли приложений**.
4. Создайте новый пароль "Django Backend". **Скопируйте 16-значный код.**

**Шаг 3: Конфигурация `.env.prod`**

```bash
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp.yandex.ru
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=noreply@freesport.ru
EMAIL_HOST_PASSWORD=ваш_16_значный_пароль_приложения
DEFAULT_FROM_EMAIL=FREESPORT <noreply@freesport.ru>
ADMIN_EMAILS=admin@freesport.ru
```

#### 2. Google Workspace (Свой домен) или Gmail

**Альтернативный вариант**

**Вариант А: Google Workspace (Свой домен)**

1. Зарегистрируйтесь в [Google Workspace](https://workspace.google.com/).
2. Подтвердите домен и настройте MX-записи Google (`ASPMX.L.GOOGLE.COM` и др.).
3. Настройте SPF (`v=spf1 include:_spf.google.com ~all`) и DKIM в Google Admin.

**Вариант Б: Обычный Gmail (Для тестов/разработки)**

1. Используйте обычный аккаунт `@gmail.com`.
2. Включите **2-Step Verification** в [настройках безопасности](https://myaccount.google.com/security).

**Общий шаг: Создание App Password**

1. Перейдите в [Google Account Security](https://myaccount.google.com/security).
2. Найдите "App passwords" (Пароли приложений).
   - *Если нет в меню, воспользуйтесь поиском по настройкам.*
3. Создайте пароль "Django Backend".
4. Скопируйте 16-значный код.

**Конфигурация `.env`**

```bash
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=your-email@gmail.com
EMAIL_HOST_PASSWORD=xxxx-xxxx-xxxx-xxxx
DEFAULT_FROM_EMAIL=your-email@gmail.com
```

## Rate Limits провайдеров

> ⚠️ **Важно:** Учитывайте лимиты при высокой нагрузке

| Provider | Лимит | Рекомендация |
|----------|-------|--------------|
| Gmail | 500 emails/день | Только для development/testing |
| Yandex Mail | 100-500/день | Подходит для небольшого объема |
| SendGrid Free | 100/день | Альтернатива для production |
| SendGrid Paid | 40,000+/месяц | Рекомендуется для масштабирования |

## Тестирование

### Management command

```bash
# В Docker контейнере
docker exec -it freesport-backend python manage.py test_email --to admin@freesport.ru

# Локально (с активированным venv)
cd backend
python manage.py test_email --to admin@freesport.ru
```

### Django Shell

```python
docker exec -it freesport-backend python manage.py shell

>>> from django.core.mail import send_mail
>>> send_mail(
...     'Test Email',
...     'Тестовое сообщение от FREESPORT',
...     None,  # Использует DEFAULT_FROM_EMAIL
...     ['admin@freesport.ru'],
...     fail_silently=False,
... )
1  # Возвращает 1 при успехе
```

### Проверка конфигурации

```python
>>> from django.conf import settings
>>> print(f"EMAIL_BACKEND: {settings.EMAIL_BACKEND}")
>>> print(f"EMAIL_HOST: {settings.EMAIL_HOST}")
>>> print(f"DEFAULT_FROM_EMAIL: {settings.DEFAULT_FROM_EMAIL}")
>>> print(f"ADMINS: {settings.ADMINS}")
```

## Troubleshooting

### Ошибка аутентификации (535)

- Проверьте правильность `EMAIL_HOST_USER` и `EMAIL_HOST_PASSWORD`
- Для Gmail: убедитесь, что используете App Password, а не обычный пароль
- Для Yandex: проверьте, что почтовый ящик существует и активен

### Ошибка подключения (Connection refused)

- Проверьте `EMAIL_HOST` и `EMAIL_PORT`
- В Docker: убедитесь, что mailhog сервис запущен
- Проверьте firewall настройки

### Письма не доставляются

- Проверьте spam/junk папку получателя
- Убедитесь, что `DEFAULT_FROM_EMAIL` соответствует домену
- Проверьте SPF/DKIM записи домена

## См. также

- [Story 29.4: Email Notification System](../stories/epic-29/29.4.email-notification-system.md)
- [Django Email Documentation](https://docs.djangoproject.com/en/4.2/topics/email/)
