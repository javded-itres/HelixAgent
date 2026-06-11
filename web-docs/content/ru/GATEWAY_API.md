# Справочник Gateway API

Gateway Helix предоставляет **два слоя HTTP API** в **одном multi-profile процессе**:

1. **Hermes-compatible API** — совместимость с Open WebUI, LobeChat и другими Hermes-клиентами
2. **Helix Management API** — control plane для SaaS: профили, модели, MCP, навыки, Telegram admin

Эксплуатация (start/stop, порты, логи): [GATEWAY.md](GATEWAY.md).

---

## Базовый URL и версия

```text
http://127.0.0.1:8000
```

Версия gateway: `GET /` (`version`, `host_profile`, `loaded_profiles`).

---

## Аутентификация

### API key (уровень 1)

Все маршруты **кроме** `GET /health` и `GET /v1/health` требуют валидный API key при `HELIX_REQUIRE_AUTH=true` (по умолчанию).

| Заголовок | Пример |
|-----------|--------|
| `Authorization` | `Bearer hx_…` |
| `X-API-Key` | `hx_…` |

Права: `read`, `write`, `execute`, `admin` — см. [SECURITY.md](SECURITY.md).

Создание ключей: `POST /admin/api-keys` (нужно право admin).

### Ключ доступа к профилю (уровень 2)

Маршруты `/api/helix/*` дополнительно требуют авторизацию профиля:

| Кто | Заголовки | Область |
|-----|-----------|---------|
| Владелец профиля | `X-Helix-Profile-Key: hp_…` | Только свой профиль |
| Админ gateway | API key с `admin` **или** master key admin-профиля | Все профили |

Имя admin-профиля по умолчанию: `admin` (`HELIX_TELEGRAM_ADMIN_PROFILE`).

### Публичные эндпоинты

| Метод | Путь |
|-------|------|
| GET | `/health` |
| GET | `/v1/health` |

---

## Роутинг профиля (chat / Hermes surface)

Приоритет (первый непустой wins):

1. `X-Helix-Profile` или `X-Hermes-Profile`
2. Поле `model` в `/v1/chat/completions` или `/v1/responses` (имя профиля)
3. Host profile процесса gateway (`HELIX_PROFILE` при старте)

### Сессии (алиасы заголовков)

| Назначение | Helix | Hermes (алиас) |
|------------|-------|----------------|
| ID разговора / транскрипт | `X-Helix-Session-Id` | `X-Hermes-Session-Id` |
| Стабильная область памяти | `X-Helix-Session-Key` | `X-Hermes-Session-Key` |

Ключ сессии — до 256 символов; control-символы отклоняются.

---

## SaaS workflow (curl)

```bash
export HELIX_URL=http://127.0.0.1:8000
export ADMIN_KEY=hx_admin_…
export ADMIN_PROFILE_KEY=hp_…   # master key профиля admin

# 1. Создать tenant-профиль (admin)
curl -sS -X POST "$HELIX_URL/api/helix/profiles" \
  -H "Authorization: Bearer $ADMIN_KEY" \
  -H "Content-Type: application/json" \
  -d '{"name":"tenant-42","with_access_key":true}'

# 2. Добавить LLM-провайдер
curl -sS -X POST "$HELIX_URL/api/helix/profiles/tenant-42/models/providers" \
  -H "Authorization: Bearer $ADMIN_KEY" \
  -H "X-Helix-Profile-Key: $ADMIN_PROFILE_KEY" \
  -H "Content-Type: application/json" \
  -d '{"preset_id":"openrouter","skip_test":true}'

# 3. Reload agent + companions для tenant
curl -sS -X POST "$HELIX_URL/api/helix/profiles/tenant-42/reload" \
  -H "Authorization: Bearer $ADMIN_KEY" \
  -H "X-Helix-Profile-Key: $ADMIN_PROFILE_KEY"

# 4. Chat от имени tenant (OpenAI client: model = имя профиля)
curl -sS "$HELIX_URL/v1/chat/completions" \
  -H "Authorization: Bearer $TENANT_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"model":"tenant-42","messages":[{"role":"user","content":"привет"}]}'

# 5. Настройка Telegram для профиля бота
curl -sS -X POST "$HELIX_URL/api/helix/profiles/tenant-42/telegram/setup" \
  -H "Authorization: Bearer $ADMIN_KEY" \
  -H "X-Helix-Profile-Key: $TENANT_PROFILE_KEY" \
  -H "Content-Type: application/json" \
  -d '{"bot_token":"123456789:AAH…"}'

# 6. Одобрить пользователя Telegram (только admin)
curl -sS -X POST "$HELIX_URL/api/helix/profiles/tenant-42/telegram/requests/12345/approve" \
  -H "Authorization: Bearer $ADMIN_KEY" \
  -H "X-Helix-Profile-Key: $ADMIN_PROFILE_KEY" \
  -H "Content-Type: application/json" \
  -d '{"profile":"tenant-42"}'
```

Изменения конфигурации возвращают `"reload_required": true`. Вызовите `POST /api/helix/profiles/{id}/reload` — без рестарта uvicorn.

---

## Hermes-compatible API

Соответствие [Hermes API Server](https://github.com/NousResearch/hermes-agent/blob/main/website/docs/user-guide/features/api-server.md).

| Hermes | Helix | Примечание |
|--------|-------|------------|
| `GET /v1/models` | ✅ | Имена профилей как model id |
| `GET /v1/capabilities` | ✅ | Возможности агента |
| `GET /v1/health` | ✅ | Публичный |
| `GET /health/detailed` | ✅ | Расширенный health |
| `GET /v1/toolsets` | ✅ | Инструменты агента |
| `GET /v1/skills` | ✅ | `[{name, description, category}]` |
| `POST /v1/responses` | ✅ | SQLite, LRU 100 |
| `GET/DELETE /v1/responses/{id}` | ✅ | |
| `POST/GET /v1/runs`, SSE events | ✅ | |
| `POST /v1/runs/{id}/stop\|approval` | ✅ | |
| `/api/jobs` CRUD + pause/resume/run | ✅ | Cron на профиль |
| `/api/sessions` CRUD + chat/stream | ✅ | |

### Расширения Helix (`/v1`)

| Метод | Путь | Описание |
|--------|------|----------|
| POST | `/v1/chat/completions` | OpenAI-совместимый чат |
| GET | `/v1/conversations/{id}` | История |
| GET | `/v1/tools` | Список инструментов |
| POST | `/v1/search` | Поиск по памяти |
| POST/GET/DELETE | `/v1/permissions/*` | Права на инструменты |
| POST | `/v1/confirmations/resolve` | Подтверждение рискованных действий |
| POST/GET | `/v1/plan/*` | Ревью плана |

---

## Helix Management API (`/api/helix/`)

Control plane. Все маршруты: API key + доступ к профилю.

### Профили — `/api/helix/profiles`

| Метод | Путь | Описание |
|--------|------|----------|
| GET | `/api/helix/profiles` | Список (admin) |
| POST | `/api/helix/profiles` | Создать (admin) |
| GET | `/api/helix/profiles/{id}` | Детали |
| GET | `/api/helix/profiles/{id}/status` | Статус agent + companions |
| DELETE | `/api/helix/profiles/{id}` | Удалить (admin) |
| POST | `/api/helix/profiles/{id}/reload` | Reload agent + Telegram + cron |
| GET/POST | `…/key/status\|init\|rotate\|disable` | Ключ доступа к профилю |
| GET/POST | `…/jail`, `…/jail/enable\|disable` | Workspace jail |

### Модели — `…/models`

| Метод | Путь | Описание |
|--------|------|----------|
| GET | `…/presets` | Каталог провайдеров |
| GET/POST/DELETE | `…/providers` | CRUD провайдеров |
| POST | `…/providers/{name}/test` | Проверка + список моделей |
| GET/PATCH | `…/agent-models`, `…/fallbacks` | Маршрутизация моделей |

### Навыки — `…/skills`

| Метод | Путь | Описание |
|--------|------|----------|
| GET | `…/skills` | Список |
| GET | `…/skills/search?q=` | Поиск |
| GET | `…/skills/{name}` | Детали |
| GET/PATCH | `…/skills/assignments` | Назначения по агентам |
| POST | `…/skills/seed-bundled` | Установка bundled skills |

### MCP — `…/mcp`

| Метод | Путь | Описание |
|--------|------|----------|
| GET/POST/DELETE | `…/servers` | CRUD серверов |
| POST | `…/servers/{name}/test` | Тест подключения |
| GET/PATCH | `…/assignments` | Назначения |
| GET | `…/popular` | Популярные серверы |
| POST | `…/install` | Установка popular/git |

### Конфиг — `/api/helix/profiles/{id}`

| Метод | Путь | Описание |
|--------|------|----------|
| GET/PATCH | `…/config` | config.yaml (секреты замаскированы) |
| GET/PATCH | `…/env` | `.env` профиля |

### Global — `/api/helix/global` (только admin)

| Метод | Путь | Описание |
|--------|------|----------|
| POST | `/api/helix/global/init` | Инициализация global |
| GET/PATCH | `/api/helix/global/config` | `~/.helix/global/config.yaml` |
| GET/PATCH | `/api/helix/global/env` | `~/.helix/global/.env` |

### Telegram — `…/telegram`

Эквиваленты CLI: [TELEGRAM.md](TELEGRAM.md).

| Метод | Путь | CLI | Auth |
|--------|------|-----|------|
| GET | `…/status` | `telegram status` | owner/admin |
| POST | `…/setup` | `telegram setup` | owner/admin |
| GET | `…/requests` | `telegram requests list` | owner/admin |
| POST | `…/requests/{user_id}/approve` | `telegram requests approve` | **admin** |
| POST | `…/requests/{user_id}/reject` | `telegram requests reject` | **admin** |
| GET/DELETE | `…/admin` | `telegram admin show/clear` | clear — **admin** |
| GET/POST/DELETE | `…/map` | `telegram map` | owner/admin |
| POST | `…/sync-menu` | `telegram sync-menu` | owner/admin |

---

## Admin (`/admin`)

| Метод | Путь | Описание |
|--------|------|-------------|
| POST | `/admin/api-keys` | Создать ключ |
| GET | `/admin/api-keys` | Список |
| DELETE | `/admin/api-keys/{id}` | Отозвать |
| GET | `/metrics` | Prometheus (admin) |

---

## Multi-profile архитектура

Один uvicorn обслуживает **N профилей** через `ProfileAgentRegistry`:

- Агенты загружаются lazy по профилю
- `CompanionManager` — Telegram polling + cron на профиль
- `POST …/reload` перезапускает companions одного профиля без рестарта gateway

Host profile задаётся при старте (`HELIX_PROFILE`).

---

## Безопасность

- Секреты в ответах management API **маскируются**
- Ключи доступа возвращаются **один раз** при create/init/rotate
- `GET /metrics` — только admin API key
- Заголовки: `X-Content-Type-Options: nosniff`, `Referrer-Policy: no-referrer`
- Production: `HELIX_API_KEY_PEPPER`, bind `127.0.0.1`, TLS на reverse proxy

См. также: [SECURITY.md](SECURITY.md), [DEPLOYMENT.md](DEPLOYMENT.md), [PROFILES.md](PROFILES.md).