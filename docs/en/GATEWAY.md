# API Gateway

OpenAI-compatible HTTP API, Hermes-compatible surface, Helix Management API, and companion services (Telegram + cron when configured).

**Full API reference:** [GATEWAY_API.md](GATEWAY_API.md) — Hermes mapping, `/api/helix/` management, auth, SaaS curl examples.

## Commands

Gateway commands apply to the **active profile**. For `default`, omit `-p`:

```bash
helix gateway start              # background (default host 127.0.0.1)
helix gateway start -f           # foreground
helix gateway start --reload     # dev auto-reload
helix gateway status
helix gateway stop
helix gateway reload
```

Other profiles: `helix -p alice gateway start`, etc.

Each profile has its own gateway state and logs:

- State: `~/.helix/profiles/<name>/gateway/state.json`
- Logs: `~/.helix/profiles/<name>/gateway/gateway.log` — `helix logs -s gateway -f` ([LOGS.md](LOGS.md))

**Multiple gateways** can run at once (different profiles, different ports):

```bash
# profiles/alice/.env
HELIX_GATEWAY_PORT=8001

# profiles/bob/.env
HELIX_GATEWAY_PORT=8002

helix -p alice gateway start
helix -p bob gateway start
```

The supervisor also runs **cron** and **Telegram** (when configured for that profile) as companion processes.

## Multi-profile gateway (v0.2+)

A single uvicorn process can serve **multiple Helix profiles**:

- Profile routing: `X-Helix-Profile` → `model` field → host profile
- Per-profile reload: `POST /api/helix/profiles/{id}/reload` (agent + Telegram + cron)
- Management API: `/api/helix/` for profiles, models, MCP, skills, Telegram admin

See [GATEWAY_API.md](GATEWAY_API.md) for endpoint tables and authentication.

## Environment

Set bind address and port in the **profile** `.env` (`helix profile env --edit`):

| Variable | Default | Description |
|----------|---------|-------------|
| `HELIX_GATEWAY_HOST` | `127.0.0.1` | Bind address |
| `HELIX_GATEWAY_PORT` | `8000` | Port |
| `HELIX_REQUIRE_AUTH` | `true` | API key required (except `/health`, `/v1/health`) |
| `HELIX_ENV=production` | — | Forces auth + stricter checks |

Admin routes (`/admin/*`) **always** require an admin API key.

## Quick endpoint map

| Group | Examples |
|-------|----------|
| Health | `GET /health`, `GET /v1/health`, `GET /health/detailed` |
| Chat | `POST /v1/chat/completions` |
| Hermes | `GET /v1/models`, `/v1/capabilities`, `/v1/runs`, `/api/sessions`, `/api/jobs` |
| Management | `GET/POST /api/helix/profiles`, `…/models`, `…/telegram`, `…/reload` |
| Admin | `POST /admin/api-keys`, `GET /metrics` |

Create first admin key:

```bash
# Bootstrap with auth disabled once, or use helix admin key create from CLI
export HELIX_REQUIRE_AUTH=false
helix gateway start -f
# POST /admin/api-keys with permissions including admin
# Then set HELIX_REQUIRE_AUTH=true and restart
```

Interactive API docs: `http://127.0.0.1:8000/docs` (OpenAPI).