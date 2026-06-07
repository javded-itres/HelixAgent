# MAX — мессенджер

Helix интегрируется с [MAX](https://max.ru) — российской платформой мессенджера — чтобы запускать того же самообучающегося агента в личных и групповых чатах внутри отечественной экосистемы.

> **Статус:** доступно в ветке `feature/max-messenger` — Long Polling (`helix max`), production webhook (`helix gateway start`), файлы, inline approvals.

```bash
uv sync --extra max
export MAX_ACCESS_TOKEN=...
export HELIX_MAX_ALLOWED_USERS=123456789
helix max setup
helix max
# или через gateway (webhook для продакшена):
helix gateway start
```

В production (`HELIX_ENV=production`) обязателен `HELIX_MAX_ALLOWED_USERS`.

## Зачем MAX

| Преимущество | Описание |
|--------------|----------|
| **Отечественный мессенджер** | Доступ к пользователям MAX без зависимости от Telegram |
| **Тот же агент** | Память, навыки, MCP, слэш-команды и подтверждения инструментов — как в TUI/Telegram |
| **Webhook для продакшена** | Режим `helix gateway start` + HTTPS webhook |
| **Inline-подтверждения** | Кнопки Allow / Deny / Allow always для опасных действий |

Официальная документация API: [dev.max.ru/docs-api](https://dev.max.ru/docs-api)

## Быстрая настройка

### 1. Создайте бота

1. Откройте [business.max.ru](https://business.max.ru/self) → **Чат-боты** → **Интеграция**
2. Скопируйте **access token** бота
3. Запомните username бота из `GET /me`

### 2. Настройте Helix

```bash
helix max setup
```

Или задайте переменные окружения вручную:

```bash
MAX_ACCESS_TOKEN=your_token_here
HELIX_MAX_ALLOWED_USERS=123456789,987654321
HELIX_MAX_PROFILE=default
HELIX_MAX_MODE=polling          # только dev/test
# HELIX_MAX_MODE=webhook        # продакшен (по умолчанию с gateway)
# HELIX_MAX_WEBHOOK_URL=https://your-host.example/max/webhook
# HELIX_MAX_WEBHOOK_SECRET=random_secret
```

### 3. Запуск

**Разработка (Long Polling):**

```bash
helix max
```

**Продакшен (Webhook через gateway):**

```bash
helix gateway start
```

Gateway регистрирует webhook в MAX (`POST /subscriptions`) и обслуживает `POST /max/webhook`.

## Переменные окружения

| Переменная | Обязательно | Описание |
|------------|-------------|----------|
| `MAX_ACCESS_TOKEN` | Да | Токен бота с business.max.ru |
| `HELIX_MAX_ALLOWED_USERS` | Prod | Allowlist `user_id` через запятую |
| `HELIX_MAX_MODE` | Нет | `webhook` (prod) или `polling` (dev/test) |
| `HELIX_MAX_WEBHOOK_URL` | Webhook | Публичный HTTPS URL для событий |
| `HELIX_MAX_WEBHOOK_SECRET` | Webhook | Секрет для заголовка `X-Max-Bot-Api-Secret` |
| `HELIX_MAX_PROFILE` | Нет | Профиль Helix (по умолчанию — активный) |

Токен передаётся в заголовке `Authorization` — query-параметры **не** поддерживаются API MAX.

## Команды CLI

| Команда | Описание |
|---------|----------|
| `helix max setup` | Мастер: токен, allowlist, режим, сохранение в `~/.helix/max.env` |
| `helix max` | Запуск бота (Long Polling — только dev/test) |
| `helix max status` | `GET /me`, подписки webhook |
| `helix gateway start` | Gateway + MAX webhook companion |

См. [CLI.md](CLI.md#helix-max).

## Режимы доставки событий

MAX поддерживает **один** режим одновременно:

| Режим | Когда использовать | Команда Helix |
|-------|-------------------|---------------|
| **Webhook** | Продакшен | `helix gateway start` |
| **Long Polling** | Локальная разработка | `helix max` |

Long Polling (`GET /updates`) ограничен по скорости и не подходит для продакшена. MAX рекомендует HTTPS webhook на порту 443 с доверенным TLS-сертификатом.

## Возможности

### Диалоги с агентом

- Одно live-сообщение на задачу (редактирование через `PUT /messages` при стриминге)
- ID сессии: `max_{profile}_{user_id}`
- Общие слэш-команды с TUI: `/help`, `/profile`, `/models`, `/new`, `/stop` — см. [SLASH_COMMANDS.md](SLASH_COMMANDS.md)

### Inline-подтверждения

Когда агент запрашивает подтверждение опасного инструмента, Helix отправляет inline-клавиатуру. Нажатие кнопки → событие `message_callback` → ответ через `POST /answers`.

### Файлы

Отправка и приём вложений через `POST /uploads`. Извлечение текста из файлов — общий пайплайн с Telegram.

### Markdown в ответах

Форматирование ответов агента в markdown MAX (`**жирный**`, `*курсив*`, `` `код` ``, ссылки). Длинные ответы разбиваются на части.

## Архитектура

```
integrations/max/
├── client.py      # REST-клиент (platform-api.max.ru)
├── bot.py         # диспетчер событий
├── session.py     # чат → conversation_id
├── webhook.py     # FastAPI route POST /max/webhook
├── polling.py     # цикл GET /updates (dev)
├── approvals.py   # callback-кнопки
└── main.py        # точка входа helix max
```

Паттерн повторяет `integrations/telegram/`, но использует лёгкий HTTP-клиент (`aiohttp`) вместо aiogram.

## Чеклист для продакшена

1. Публичный **HTTPS** endpoint на порту 443 (reverse proxy → gateway)
2. `HELIX_MAX_MODE=webhook` и корректный `HELIX_MAX_WEBHOOK_URL`
3. Задан `HELIX_MAX_ALLOWED_USERS`
4. `HELIX_ENV=production`
5. Лимит MAX: **30 rps** на `platform-api.max.ru`

См. [DEPLOYMENT.md](DEPLOYMENT.md) и [SECURITY.md](SECURITY.md).

## Решение проблем

| Симптом | Решение |
|---------|---------|
| `401` от MAX API | Проверьте `MAX_ACCESS_TOKEN`; перезапустите `helix max setup` |
| Нет событий webhook | Проверьте HTTPS URL, `POST /subscriptions`, логи gateway |
| Polling перестал работать после webhook | Активен только один режим — сначала удалите подписку webhook |
| Пользователь игнорируется | Добавьте `user_id` в `HELIX_MAX_ALLOWED_USERS` |
| Ошибки `429` | Снизьте частоту отправки; клиент Helix ограничивает ≤30 rps |

Запустите `helix doctor` для проверки токена, webhook и allowlist.

## См. также

- [TELEGRAM.md](TELEGRAM.md) — параллельная интеграция с Telegram
- [GATEWAY.md](GATEWAY.md) — HTTP gateway и companions
- [SLASH_COMMANDS.md](SLASH_COMMANDS.md) — команды `/` в чатах MAX