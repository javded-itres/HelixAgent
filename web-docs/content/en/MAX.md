# MAX Messenger

Helix integrates with [MAX](https://max.ru) — the Russian messenger platform — so you can run the same self-improving agent in personal and group chats without leaving a domestic ecosystem.

> **Status:** available on `feature/max-messenger` — Long Polling (`helix max`), production webhook (`helix gateway start`), files, inline approvals.

```bash
uv sync --extra max
export MAX_ACCESS_TOKEN=...
export HELIX_MAX_ALLOWED_USERS=123456789
helix max setup
helix max
# or with gateway (production webhook):
helix gateway start
```

In production (`HELIX_ENV=production`), `HELIX_MAX_ALLOWED_USERS` is required.

## Why MAX

| Benefit | Description |
|---------|-------------|
| **Domestic messenger** | Reach users on a Russian platform without Telegram dependency |
| **Same agent brain** | Memory, skills, MCP, slash commands, and tool approvals — identical to TUI/Telegram |
| **Webhook-ready** | Production mode via `helix gateway start` and HTTPS webhook |
| **Inline approvals** | Callback buttons for risky tool actions (Allow / Deny / Allow always) |

Official API reference: [dev.max.ru/docs-api](https://dev.max.ru/docs-api)

## Quick setup

### 1. Create a bot

1. Open [business.max.ru](https://business.max.ru/self) → **Chat bots** → **Integration**
2. Copy the bot **access token**
3. Note your bot username from `GET /me`

### 2. Configure Helix

```bash
helix max setup
```

Or set environment variables manually:

```bash
MAX_ACCESS_TOKEN=your_token_here
HELIX_MAX_ALLOWED_USERS=123456789,987654321
HELIX_MAX_PROFILE=default
HELIX_MAX_MODE=polling          # dev/test only
# HELIX_MAX_MODE=webhook        # production (default with gateway)
# HELIX_MAX_WEBHOOK_URL=https://your-host.example/max/webhook
# HELIX_MAX_WEBHOOK_SECRET=random_secret
```

### 3. Run

**Development (Long Polling):**

```bash
helix max
```

**Production (Webhook via gateway):**

```bash
helix gateway start
```

Gateway registers the webhook with MAX (`POST /subscriptions`) and serves `POST /max/webhook`.

## Environment variables

| Variable | Required | Description |
|----------|----------|-------------|
| `MAX_ACCESS_TOKEN` | Yes | Bot token from business.max.ru |
| `HELIX_MAX_ALLOWED_USERS` | Prod | Comma-separated MAX `user_id` allowlist |
| `HELIX_MAX_MODE` | No | `webhook` (default in prod) or `polling` (dev/test) |
| `HELIX_MAX_WEBHOOK_URL` | Webhook | Public HTTPS URL for MAX events |
| `HELIX_MAX_WEBHOOK_SECRET` | Webhook | Value for `X-Max-Bot-Api-Secret` header validation |
| `HELIX_MAX_PROFILE` | No | Helix profile (default: active profile) |

Token is sent in the `Authorization` header — query-string tokens are **not** supported by MAX API.

## CLI commands

| Command | Description |
|---------|-------------|
| `helix max setup` | Wizard: token, allowlist, mode, save to `~/.helix/max.env` |
| `helix max` | Start bot (Long Polling — dev/test only) |
| `helix max status` | `GET /me`, webhook subscriptions |
| `helix gateway start` | Start gateway + MAX webhook companion |

See [CLI.md](CLI.md#helix-max).

## Event modes

MAX supports **one** delivery mode at a time:

| Mode | When to use | Helix command |
|------|-------------|---------------|
| **Webhook** | Production | `helix gateway start` |
| **Long Polling** | Local dev / testing | `helix max` |

Long Polling (`GET /updates`) is rate-limited and not suitable for production. MAX recommends HTTPS webhook on port 443 with a trusted TLS certificate.

## Features

### Agent conversations

- One live message per task (edited with `PUT /messages` during streaming when enabled)
- Session id: `max_{profile}_{user_id}`
- Shared slash commands with TUI: `/help`, `/profile`, `/models`, `/new`, `/stop` — see [SLASH_COMMANDS.md](SLASH_COMMANDS.md)

### Inline approvals

When the agent requests confirmation for a risky tool, Helix sends inline keyboard buttons. User taps a button → `message_callback` event → Helix replies via `POST /answers`.

### Files

Helix can send and receive file attachments via `POST /uploads` and message attachments. Text extraction reuses the same pipeline as Telegram file handling.

### Markdown replies

Agent output is formatted with MAX markdown (`**bold**`, `*italic*`, `` `code` ``, links). Long answers are split into chunks.

## Architecture

```
integrations/max/
├── client.py      # REST client (platform-api.max.ru)
├── bot.py         # event dispatcher
├── session.py     # chat → conversation_id
├── webhook.py     # FastAPI route POST /max/webhook
├── polling.py     # GET /updates loop (dev)
├── approvals.py   # callback buttons
└── main.py        # helix max entry point
```

Pattern mirrors `integrations/telegram/` but uses a lightweight HTTP client (`aiohttp`) instead of aiogram.

## Production checklist

1. Public **HTTPS** endpoint on port 443 (reverse proxy → gateway)
2. `HELIX_MAX_MODE=webhook` and valid `HELIX_MAX_WEBHOOK_URL`
3. `HELIX_MAX_ALLOWED_USERS` set
4. `HELIX_ENV=production`
5. Rate limit: MAX allows **30 rps** on `platform-api.max.ru`

See [DEPLOYMENT.md](DEPLOYMENT.md) and [SECURITY.md](SECURITY.md).

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| `401` from MAX API | Check `MAX_ACCESS_TOKEN`; re-run `helix max setup` |
| No webhook events | Verify HTTPS URL, `POST /subscriptions`, gateway logs |
| Polling stops after webhook | Only one mode active — remove webhook subscription first |
| User ignored | Add their `user_id` to `HELIX_MAX_ALLOWED_USERS` |
| `429` errors | Reduce send rate; Helix client enforces ≤30 rps |

Run `helix doctor` to validate token, webhook, and allowlist.

## Related

- [TELEGRAM.md](TELEGRAM.md) — parallel messenger integration
- [GATEWAY.md](GATEWAY.md) — HTTP gateway and companions
- [SLASH_COMMANDS.md](SLASH_COMMANDS.md) — `/` commands in MAX chats