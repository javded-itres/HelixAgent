# API Gateway

HTTP API (OpenAI-совместимый), Hermes-compatible surface, Helix Management API и companion-сервисы (Telegram + cron при настройке).

**Полный справочник API:** [GATEWAY_API.md](GATEWAY_API.md) — Hermes mapping, `/api/helix/` management, auth, SaaS curl-примеры.

## Команды

Команды gateway относятся к **активному профилю**. Для `default` флаг `-p` не нужен:

```bash
helix gateway start              # фон (host по умолчанию 127.0.0.1)
helix gateway start -f           # передний план
helix gateway start --reload     # dev auto-reload
helix gateway status
helix gateway stop
helix gateway reload
```

Другие профили: `helix -p alice gateway start` и т.д.

У каждого профиля своё состояние и логи:

- Состояние: `~/.helix/profiles/<имя>/gateway/state.json`
- Логи: `~/.helix/profiles/<имя>/gateway/gateway.log` — `helix logs -s gateway -f` ([LOGS.md](LOGS.md))

**Несколько gateway** одновременно (разные профили, разные порты):

```bash
# profiles/alice/.env
HELIX_GATEWAY_PORT=8001

# profiles/bob/.env
HELIX_GATEWAY_PORT=8002

helix -p alice gateway start
helix -p bob gateway start
```

Supervisor также запускает **cron** и **Telegram** (если настроены для этого профиля) как companion-процессы.

## Multi-profile gateway (v0.2+)

Один процесс uvicorn обслуживает **несколько профилей Helix**:

- Роутинг: `X-Helix-Profile` → поле `model` → host profile
- Per-profile reload: `POST /api/helix/profiles/{id}/reload` (agent + Telegram + cron)
- Management API: `/api/helix/` — профили, модели, MCP, навыки, Telegram admin

Таблицы эндпоинтов и аутентификация: [GATEWAY_API.md](GATEWAY_API.md).

## Переменные окружения

Задаются в **`.env` профиля** (`helix profile env --edit`):

| Переменная | По умолчанию | Описание |
|------------|--------------|----------|
| `HELIX_GATEWAY_HOST` | `127.0.0.1` | Адрес bind |
| `HELIX_GATEWAY_PORT` | `8000` | Порт |
| `HELIX_REQUIRE_AUTH` | `true` | API key обязателен (кроме `/health`, `/v1/health`) |
| `HELIX_ENV=production` | — | Включает auth и строгие проверки |

Маршруты `/admin/*` **всегда** требуют admin API key.

## Краткая карта эндпоинтов

| Группа | Примеры |
|--------|---------|
| Health | `GET /health`, `GET /v1/health`, `GET /health/detailed` |
| Chat | `POST /v1/chat/completions` |
| Hermes | `GET /v1/models`, `/v1/capabilities`, `/v1/runs`, `/api/sessions`, `/api/jobs` |
| Management | `GET/POST /api/helix/profiles`, `…/models`, `…/telegram`, `…/reload` |
| Admin | `POST /admin/api-keys`, `GET /metrics` |

Создание первого admin-ключа:

```bash
# Однократно с HELIX_REQUIRE_AUTH=false или через CLI
export HELIX_REQUIRE_AUTH=false
helix gateway start -f
# POST /admin/api-keys с правом admin
# Затем HELIX_REQUIRE_AUTH=true и перезапуск
```

Интерактивная документация: `http://127.0.0.1:8000/docs` (OpenAPI).