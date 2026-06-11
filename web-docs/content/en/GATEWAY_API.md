# Gateway API Reference

Helix gateway exposes two HTTP API layers on a **single multi-profile process**:

1. **Hermes-compatible API** — drop-in for Open WebUI, LobeChat, and other Hermes clients
2. **Helix Management API** — control plane for SaaS: profiles, models, MCP, skills, Telegram admin

Operational guide (start/stop, ports, logs): [GATEWAY.md](GATEWAY.md).

---

## Base URL and version

```text
http://127.0.0.1:8000
```

Gateway version is reported by `GET /` (`version`, `host_profile`, `loaded_profiles`).

---

## Authentication

### API key (layer 1)

All routes **except** `GET /health` and `GET /v1/health` require a valid API key when `HELIX_REQUIRE_AUTH=true` (default).

| Header | Example |
|--------|---------|
| `Authorization` | `Bearer hx_…` |
| `X-API-Key` | `hx_…` |

Permissions: `read`, `write`, `execute`, `admin` (see [SECURITY.md](SECURITY.md)).

Create keys via `POST /admin/api-keys` (admin permission required).

### Profile access key (layer 2)

`/api/helix/*` management routes also require profile authorization:

| Who | Headers | Scope |
|-----|---------|-------|
| Profile owner | `X-Helix-Profile-Key: hp_…` | Own profile only |
| Gateway admin | API key with `admin` **or** master key of admin profile | All profiles |

Admin profile name defaults to `admin` (`HELIX_TELEGRAM_ADMIN_PROFILE`).

### Public endpoints

| Method | Path |
|--------|------|
| GET | `/health` |
| GET | `/v1/health` |

---

## Profile routing (chat / Hermes surface)

Priority (first non-empty wins):

1. `X-Helix-Profile` or `X-Hermes-Profile`
2. `model` field in `/v1/chat/completions` or `/v1/responses` (profile name)
3. Gateway host profile (`HELIX_PROFILE` at process start)

### Session continuity (header aliases)

| Purpose | Helix | Hermes (alias) |
|---------|-------|----------------|
| Conversation / transcript id | `X-Helix-Session-Id` | `X-Hermes-Session-Id` |
| Stable memory scope | `X-Helix-Session-Key` | `X-Hermes-Session-Key` |

Session key max 256 chars; control characters rejected.

---

## SaaS workflow (curl)

```bash
export HELIX_URL=http://127.0.0.1:8000
export ADMIN_KEY=hx_admin_…
export ADMIN_PROFILE_KEY=hp_…   # master key of admin profile

# 1. Create tenant profile (admin)
curl -sS -X POST "$HELIX_URL/api/helix/profiles" \
  -H "Authorization: Bearer $ADMIN_KEY" \
  -H "Content-Type: application/json" \
  -d '{"name":"tenant-42","with_access_key":true}'

# 2. Add LLM provider
curl -sS -X POST "$HELIX_URL/api/helix/profiles/tenant-42/models/providers" \
  -H "Authorization: Bearer $ADMIN_KEY" \
  -H "X-Helix-Profile-Key: $ADMIN_PROFILE_KEY" \
  -H "Content-Type: application/json" \
  -d '{"preset_id":"openrouter","skip_test":true}'

# 3. Reload tenant agent + companions
curl -sS -X POST "$HELIX_URL/api/helix/profiles/tenant-42/reload" \
  -H "Authorization: Bearer $ADMIN_KEY" \
  -H "X-Helix-Profile-Key: $ADMIN_PROFILE_KEY"

# 4. Chat as tenant (OpenAI client: model = profile name)
curl -sS "$HELIX_URL/v1/chat/completions" \
  -H "Authorization: Bearer $TENANT_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"model":"tenant-42","messages":[{"role":"user","content":"hi"}]}'

# 5. Telegram setup for tenant bot profile
curl -sS -X POST "$HELIX_URL/api/helix/profiles/tenant-42/telegram/setup" \
  -H "Authorization: Bearer $ADMIN_KEY" \
  -H "X-Helix-Profile-Key: $TENANT_PROFILE_KEY" \
  -H "Content-Type: application/json" \
  -d '{"bot_token":"123456789:AAH…"}'

# 6. Approve Telegram user (admin only)
curl -sS -X POST "$HELIX_URL/api/helix/profiles/tenant-42/telegram/requests/12345/approve" \
  -H "Authorization: Bearer $ADMIN_KEY" \
  -H "X-Helix-Profile-Key: $ADMIN_PROFILE_KEY" \
  -H "Content-Type: application/json" \
  -d '{"profile":"tenant-42"}'
```

Management mutations return `"reload_required": true` when the running agent must be refreshed. Call `POST /api/helix/profiles/{id}/reload` to apply config changes without restarting uvicorn.

---

## Hermes-compatible API

Mapping to [Hermes API Server](https://github.com/NousResearch/hermes-agent/blob/main/website/docs/user-guide/features/api-server.md) endpoints.

| Hermes | Helix | Notes |
|--------|-------|-------|
| `GET /v1/models` | ✅ | Lists profile names as model ids |
| `GET /v1/capabilities` | ✅ | Agent capabilities |
| `GET /v1/health` | ✅ | Public |
| `GET /health/detailed` | ✅ | Extended health (auth optional) |
| `GET /v1/toolsets` | ✅ | From agent tools |
| `GET /v1/skills` | ✅ | `[{name, description, category}]` |
| `POST /v1/responses` | ✅ | SQLite store, LRU 100 |
| `GET /v1/responses/{id}` | ✅ | |
| `DELETE /v1/responses/{id}` | ✅ | |
| `POST /v1/runs` | ✅ | In-memory + SSE |
| `GET /v1/runs/{id}` | ✅ | |
| `GET /v1/runs/{id}/events` | ✅ | SSE stream |
| `POST /v1/runs/{id}/stop` | ✅ | |
| `POST /v1/runs/{id}/approval` | ✅ | Human-in-the-loop |
| `GET/POST/PATCH/DELETE /api/jobs` | ✅ | Cron jobs per profile |
| `POST /api/jobs/{id}/pause\|resume\|run` | ✅ | |
| `GET/POST /api/sessions` | ✅ | |
| `GET/PATCH/DELETE /api/sessions/{id}` | ✅ | |
| `GET /api/sessions/{id}/messages` | ✅ | |
| `POST /api/sessions/{id}/fork` | ✅ | |
| `POST /api/sessions/{id}/chat` | ✅ | |
| `POST /api/sessions/{id}/chat/stream` | ✅ | SSE |

### Helix legacy extensions (`/v1`)

| Method | Path | Description |
|--------|------|-------------|
| POST | `/v1/chat/completions` | OpenAI-compatible chat |
| GET | `/v1/conversations/{id}` | Conversation history |
| GET | `/v1/tools` | Tool list |
| POST | `/v1/search` | Memory search |
| POST/GET/DELETE | `/v1/permissions/*` | Tool permissions |
| POST | `/v1/confirmations/resolve` | Approve risky actions |
| POST/GET | `/v1/plan/*` | Plan review |

---

## Helix Management API (`/api/helix/`)

Prefix for control-plane operations. All routes require API key + profile access (see above).

### Profiles — `/api/helix/profiles`

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/helix/profiles` | List profiles (admin) |
| POST | `/api/helix/profiles` | Create profile (admin) |
| GET | `/api/helix/profiles/{id}` | Profile details |
| GET | `/api/helix/profiles/{id}/status` | Agent + companions status |
| DELETE | `/api/helix/profiles/{id}` | Delete profile (admin) |
| POST | `/api/helix/profiles/{id}/reload` | Reload agent + Telegram + cron |
| GET | `/api/helix/profiles/{id}/key/status` | Access key status |
| POST | `/api/helix/profiles/{id}/key/init` | Enable profile key + jail |
| POST | `/api/helix/profiles/{id}/key/rotate` | Rotate key (body: `current_key`) |
| POST | `/api/helix/profiles/{id}/key/disable` | Remove key (admin) |
| GET | `/api/helix/profiles/{id}/jail` | Workspace jail status |
| POST | `/api/helix/profiles/{id}/jail/enable` | Enable jail (optional `path`) |
| POST | `/api/helix/profiles/{id}/jail/disable` | Disable jail |

### Models — `/api/helix/profiles/{id}/models`

| Method | Path | Description |
|--------|------|-------------|
| GET | `…/presets` | Provider catalog |
| GET | `…/providers` | Configured providers (keys masked) |
| POST | `…/providers` | Add preset provider |
| DELETE | `…/providers/{name}` | Remove provider |
| POST | `…/providers/{name}/test` | Probe + discover models |
| GET/PATCH | `…/agent-models` | Agent model routing |
| GET/PATCH | `…/fallbacks` | Fallback provider chain |

### Skills — `/api/helix/profiles/{id}/skills`

| Method | Path | Description |
|--------|------|-------------|
| GET | `…/skills` | List skills (`?agent=`, `?limit=`) |
| GET | `…/skills/search?q=` | Semantic search |
| GET | `…/skills/{name}` | Skill detail |
| GET/PATCH | `…/skills/assignments` | Per-agent skill allowlists |
| POST | `…/skills/seed-bundled` | Install bundled skills |

### MCP — `/api/helix/profiles/{id}/mcp`

| Method | Path | Description |
|--------|------|-------------|
| GET | `…/servers` | List servers + assignments |
| POST | `…/servers` | Create server |
| GET | `…/servers/{name}` | Server config |
| DELETE | `…/servers/{name}` | Remove server |
| POST | `…/servers/{name}/test` | Connect + list tools |
| GET/PATCH | `…/assignments` | Agent ↔ server mapping |
| GET | `…/popular` | Curated install list |
| POST | `…/install` | Install popular or git MCP |

### Config — `/api/helix/profiles/{id}`

| Method | Path | Description |
|--------|------|-------------|
| GET/PATCH | `…/config` | Profile YAML (secrets masked) |
| GET/PATCH | `…/env` | Profile `.env` (secrets masked) |

### Global — `/api/helix/global` (admin only)

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/helix/global/init` | Create global config + env |
| GET/PATCH | `/api/helix/global/config` | `~/.helix/global/config.yaml` |
| GET/PATCH | `/api/helix/global/env` | `~/.helix/global/.env` |

### Telegram — `/api/helix/profiles/{id}/telegram`

CLI equivalents in [TELEGRAM.md](TELEGRAM.md).

| Method | Path | CLI | Auth |
|--------|------|-----|------|
| GET | `…/status` | `telegram status` | owner/admin |
| POST | `…/setup` | `telegram setup` | owner/admin |
| GET | `…/requests` | `telegram requests list` | owner/admin |
| POST | `…/requests/{user_id}/approve` | `telegram requests approve` | **admin** |
| POST | `…/requests/{user_id}/reject` | `telegram requests reject` | **admin** |
| GET | `…/admin` | `telegram admin show` | owner/admin |
| DELETE | `…/admin` | `telegram admin clear` | **admin** |
| GET | `…/map` | `telegram map list` | owner/admin |
| POST | `…/map` | `telegram map set` | owner/admin |
| DELETE | `…/map/{user_id}` | `telegram map remove` | owner/admin |
| POST | `…/sync-menu` | `telegram sync-menu` | owner/admin |

`POST …/setup` body: `{"bot_token":"…","also_project_env":false}`. Verifies token via Telegram `getMe`, saves `telegram.env`, reloads Telegram companion when gateway companions are active.

`POST …/approve` body: `{"profile":"alice"}` or `{"create_profile":"bob"}` or `{"set_admin":true}`.

---

## Admin routes (`/admin`)

| Method | Path | Description |
|--------|------|-------------|
| POST | `/admin/api-keys` | Create API key |
| GET | `/admin/api-keys` | List keys |
| DELETE | `/admin/api-keys/{id}` | Revoke key |
| GET | `/metrics` | Prometheus (admin; disabled unless enabled) |

---

## Multi-profile architecture

One uvicorn process serves **N profiles** via in-memory `ProfileAgentRegistry`:

- Agents are lazy-loaded per profile
- `CompanionManager` runs Telegram polling + cron per profile
- `POST …/reload` stops and restarts companions for one profile without gateway restart

Host profile is set at startup (`HELIX_PROFILE`). Other profiles load on first request or via management API.

---

## Security notes

- Secrets in management responses are **masked** (tokens, API keys, env vars)
- Access keys are returned **once** on create/init/rotate — store securely
- `GET /metrics` requires admin API key
- Security headers on all responses: `X-Content-Type-Options: nosniff`, `Referrer-Policy: no-referrer`
- Production: set `HELIX_API_KEY_PEPPER`, bind to `127.0.0.1`, terminate TLS at reverse proxy

See also: [SECURITY.md](SECURITY.md), [DEPLOYMENT.md](DEPLOYMENT.md), [PROFILES.md](PROFILES.md).