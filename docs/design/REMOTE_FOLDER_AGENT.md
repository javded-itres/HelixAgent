# Holix Link — удалённый доступ агента к папке пользователя

**Статус:** черновик на согласование (реализация не начата)  
**Ветка:** `feature/remote-folder-agent`  
**Версия документа:** 0.2  
**Дата:** 2026-06-12

---

## 1. Проблема

Сейчас Holix-агент работает **локально** на машине, где установлен CLI/gateway: файловые инструменты, терминал и workspace jail привязаны к `~/.holix/profiles/<name>/`. Удалённый оператор (другой сервер, Telegram, веб-UI) не может безопасно работать с **произвольной папкой на ПК пользователя** без:

- проброса портов и открытия gateway в интернет;
- полной установки Holix на клиентской машине с тем же уровнем доступа, что и у «основного» агента.

Нужно **простое приложение-компаньон**: пользователь выбирает одну папку, подключается к уже существующему Holix (сервер / gateway), агент на стороне сервера видит только эту папку — **за NAT**, с **шифрованием** и **простой отвязкой**.

---

## 2. Предлагаемое решение: **Holix Link**

Лёгкий клиент **Holix Link** (отдельный пакет или extra `Holix[link]`) + расширение gateway **Link Relay**.

| Роль | Где работает | Задача |
|------|--------------|--------|
| **Holix Link (клиент)** | ПК/ноутбук пользователя | Выбор папки, исходящее соединение к gateway, исполнение файловых операций только внутри jail |
| **Link Relay (сервер)** | Gateway на VPS / `holix-agent.ru` | Приём сессий Link, маршрутизация к агенту профиля `linked-<id>` |
| **Агент** | Профиль на gateway | Использует виртуальные инструменты `link_read_file`, `link_list_dir`, … вместо прямого FS |

**Ключевая идея:** клиент **сам** устанавливает исходящее соединение (WebSocket over TLS). Входящих портов на стороне пользователя не нужно — работает за NAT/CGNAT.

Синхронизация целой папки на сервер **не используется** в MVP: агент работает с **живым удалённым каталогом** через RPC (меньше диска на сервере, актуальные данные). Опциональная «офлайн-копия» — фаза 3.

---

## 3. Цели и ограничения

### Цели (MVP)

- Установка клиента за **1–2 команды** (`curl … | bash` или `pipx install Holix-Link`).
- Пользователь **явно выбирает папку** (и может сменить только после переподключения).
- **Pairing** по одноразовому коду / QR (как Telegram access request).
- Трафик **TLS 1.3** + подписанные сообщений на уровне приложения.
- Работа **за NAT** (outbound-only).
- На сервере — **отдельный профиль** или режим `link` с workspace jail = удалённая папка.
- **Отзыв** связи с любой стороны, аудит операций.
- **Паритет платформ:** клиент Holix Link с первого релиза на **Windows 10+**, **Linux** (glibc systemd/non-systemd), **macOS 12+** (Intel + Apple Silicon).

### Не входит в MVP

- Произвольный shell на клиентской машине (только файлы; терминал — фаза 2 с отдельным согласием).
- Доступ ко всей файловой системе клиента.
- P2P без relay-сервера (рассмотрено, отложено).
- Нативные GUI macOS/Windows (сначала CLI + опционально минимальный web wizard на `127.0.0.1`).

### Нефункциональные требования

- Latency: list/read &lt; 2 с на типичном канале; streaming read для больших файлов.
- Переподключение после sleep/reboot клиента без повторного pairing (пока не отозван ключ).
- Совместимость: Python 3.12+ на **Windows, Linux, macOS** (единая кодовая база, без форка).
- CI: матрица `ubuntu-latest`, `macos-latest`, `windows-latest` для клиента и jail-тестов.

---

## 4. Пользовательские сценарии

### 4.1 Подключение (pairing)

1. Админ на сервере: `holix link create --profile support` → код `LINK-7K3M-9Q2P` (TTL 10 мин).
2. Пользователь на ПК:
   - Linux/macOS: `holix-link pair LINK-7K3M-9Q2P --folder ~/Projects/acme`
   - Windows: `holix-link pair LINK-7K3M-9Q2P --folder C:\Users\me\Projects\acme`
3. Клиент показывает fingerprint сервера; пользователь подтверждает.
4. Сервер создаёт запись `link_id`, профиль `linked-acme` с `workspace_root` = виртуальный корень.
5. Агент в Telegram/веб: «Папка Acme подключена».

### 4.2 Работа агента

- Оператор пишет в Telegram профиля `support`: «Прочитай README в корне».
- Агент вызывает `link_read_file("README.md")` → RPC → клиент читает `~/Projects/acme/README.md` → ответ.

### 4.3 Отзыв

- `holix link revoke <link_id>` на сервере **или** `holix-link disconnect` на клиенте.
- Все сессии и refresh-токены инвалидируются.

---

## 5. Архитектура

```mermaid
flowchart TB
  subgraph user_pc [ПК пользователя за NAT]
    LinkApp[Holix Link daemon]
    Folder[(Выбранная папка)]
    LinkApp -->|chroot/jail| Folder
  end

  subgraph server [Сервер Holix / VPS]
    GW[API Gateway]
    Relay[Link Relay WS hub]
    Agent[Agent profile linked-*]
    GW --> Relay
    Agent -->|link_* tools| Relay
  end

  subgraph operator [Оператор]
    TG[Telegram / TUI / API]
  end

  LinkApp -->|WSS outbound TLS| Relay
  TG --> GW --> Agent
```

### Поток данных

1. **Control plane:** pairing, revoke, status — HTTP на gateway (`/v1/link/*`).
2. **Data plane:** постоянный **WebSocket** клиент → relay; запросы файловых операций с `request_id`, таймаут, размерные лимиты.
3. **Агент** не ходит на клиент напрямую — только через `LinkBridge` в процессе gateway.

---

## 6. Безопасность

### 6.1 Модель угроз

| Угроза | Митигация |
|--------|-----------|
| Перехват трафика | TLS 1.3 (WSS), certificate pinning опционально |
| Подмена сервера | Отображение fingerprint при pairing; TOFU + опциональный `HOLIX_LINK_TRUSTED_FP` |
| Компрометация pairing-кода | TTL 10 мин, одноразовость, rate limit |
| Расширение scope | Жёсткий `workspace_root` на клиенте; все пути нормализуются и проверяются (`..` запрещён) |
| Утечка через агента | Отдельный профиль link; без терминала в MVP; whitelist расширений файлов опционально |
| Украденный device token | Refresh rotation, revoke, короткий TTL access token |

### 6.2 Шифрование (слои)

| Слой | Механизм |
|------|----------|
| Транспорт | TLS 1.3 (обязательно) |
| Аутентификация сессии | Ed25519 keypair на клиенте при первом pair; сервер хранит public key |
| Сообщения RPC | JSON + HMAC-SHA256 или подпись Ed25519 (`link_session_key`) |
| Секреты at rest | `~/.holix/link/credentials.json` chmod 600; OS keychain — фаза 2 |

Полное E2E без расшифровки на relay **не требуется в MVP**, если relay на том же доверенном gateway. Для multi-tenant SaaS — фаза 2: envelope encryption per link.

### 6.3 Права на клиенте

- Переиспользовать **`workspace_jail`** из `core/tools/` — тот же код нормализации путей.
- Запрет symlink-escape (resolve realpath внутри jail).
- Лимиты: max file size read (например 10 MB MVP), max list entries, rate limit RPC/мин.

---

## 7. Обход NAT

**Выбранный подход:** persistent **outbound WebSocket** от клиента к `wss://<gateway>/v1/link/ws`.

| Альтернатива | Почему не MVP |
|--------------|---------------|
| Reverse SSH tunnel | Сложная установка для пользователя |
| WireGuard | Нужны права админа, конфиг сети |
| STUN/TURN P2P | Сложность, нестабильность CGNAT |
| Tailscale/ZeroTier | Внешняя зависимость, не «одно приложение Holix» |

**Reconnect:** exponential backoff; при долгом offline агент видит статус `link_offline`; очередь запросов не буферизуется (fail fast).

**Self-hosted:** relay встроен в существующий `holix gateway` — отдельный порт не нужен, тот же TLS termination на nginx.

---

## 8. Установка (UX)

### Клиент — все платформы

| Платформа | Установка | Требования |
|-----------|-----------|------------|
| **Linux** | `pipx install Holix-Link` или `curl … \| bash` | Python 3.12+ |
| **macOS** | `pipx install Holix-Link` или `curl … \| bash` | Python 3.12+ (Homebrew/pyenv) |
| **Windows** | `pipx install Holix-Link` или `install-link.ps1` | Python 3.12+ с python.org или `winget install Python.Python.3.12` |

Общие команды (имя CLI одинаковое):

```bash
holix-link wizard      # pairing + выбор папки + фоновый daemon
holix-link status
holix-link disconnect
holix-link install-service   # автозапуск (см. §9)
```

На Windows те же команды в **PowerShell** / **cmd** (после `pipx ensurepath`).

### Сервер (уже есть Holix)

```bash
holix link create --profile support --ttl 10m
holix link list
holix link revoke <id>
```

Серверная часть (gateway relay) — только Linux/macOS/Windows **как хост gateway**; клиент Link — обязательно все три ОС у пользователя.

---

## 9. Кроссплатформенная поддержка (Windows / Linux / macOS)

Клиент Holix Link — **не серверный** компонент: он ставится на машину пользователя с любой из трёх ОС. Архитектура протокола и relay **одинаковая**; отличаются только пути, фоновый сервис и edge-cases ФС.

### 9.1 Каталоги данных

Переиспользовать `core/platform_compat.resolve_holix_home()`:

| ОС | Путь по умолчанию |
|----|-------------------|
| Linux / macOS | `~/.holix/link/` |
| Windows | `%LOCALAPPDATA%\Holix\link\` |

Содержимое: `credentials.json`, `config.json` (folder, link_id, server URL), `link.log`, `daemon.pid`.

Права: Unix `chmod 600` на секреты; Windows — ACL только для текущего пользователя (фаза 1), DPAPI — фаза 2.

### 9.2 Выбор папки (workspace jail)

| ОС | MVP | Фаза 2 |
|----|-----|--------|
| Все | Аргумент `--folder <path>` в CLI | `holix-link wizard` с нативным диалогом |
| Linux/macOS | `~/…`, `/home/…` | `zenity` / AppleScript `choose folder` |
| Windows | `C:\Users\…`, UNC `\\server\share` (read-only share — осторожно) | PowerShell `FolderBrowserDialog` |

**Нормализация путей** (`integrations/link/paths.py`):

- Внутреннее представление: POSIX-style относительно jail root (`src/main.py`).
- Windows: `Path.resolve()`, поддержка длинных путей (`\\?\` при &gt;260 символов).
- Запрет: `..`, absolute escape, **junction/symlink** за пределы jail (`os.path.realpath` / `Path.resolve(strict=False)` с проверкой `is_relative_to`).

Отдельный набор тестов: `tests/test_link_paths_windows.py` (моки `sys.platform`), `test_link_jail_unix.py`.

### 9.3 Фоновый daemon (автозапуск)

Единая команда: `holix-link install-service` / `holix-link uninstall-service`.

| ОС | Механизм | Заметки |
|----|----------|---------|
| **Linux** | systemd **user** unit `holix-link.service` | `WantedBy=default.target`, перезапуск при обрыве WS |
| **macOS** | LaunchAgent `~/Library/LaunchAgents/ru.holix.link.plist` | `RunAtLoad`, `KeepAlive` |
| **Windows** | Планировщик задач **или** `nssm`/pywin32 Service | MVP: Task Scheduler «при входе» + `--foreground` fallback; полноценная Service — фаза 2 |

Без прав администратора: только user-level сервисы (не `/Library/LaunchDaemons`, не system systemd).

Остановка: `holix-link stop` → корректный SIGTERM (POSIX) / `GenerateConsoleCtrlEvent` (Windows) через `core/platform_compat.terminate_process`.

### 9.4 Сеть и NAT

На всех ОС — **только исходящие** TCP 443 (WSS). Входящие порты и правила firewall на клиенте не нужны.

| ОС | Типичные ограничения |
|----|---------------------|
| Windows | Корпоративный прокси — фаза 2: `HTTPS_PROXY` для WebSocket |
| macOS | Little Snitch / firewall — пользователь разрешает исходящее к gateway |
| Linux | `iptables` OUTPUT обычно разрешён |

Sleep/hibernate: при пробуждении — автоматический reconnect (все платформы).

### 9.5 Установщики

| Скрипт | Платформа |
|--------|-----------|
| `scripts/install-link.sh` | Linux + macOS (проверка `python3.12`, `pipx`, PATH) |
| `scripts/install-link.ps1` | Windows (проверка Python, `pipx`, добавление в PATH) |

Документация: `docs/en/LINK.md`, `docs/ru/LINK.md` — отдельные подразделы per OS.

### 9.6 CI и ручная матрица

```yaml
# .github/workflows/link-client.yml (план)
strategy:
  matrix:
    os: [ubuntu-latest, macos-latest, windows-latest]
    python: ["3.12", "3.13"]
```

Проверки: pairing mock, jail escape, path normalize, daemon start/stop (smoke), `holix doctor --link` (план).

### 9.7 Зависимости клиента

Минимальный набор (без Chromium/Playwright):

- `httpx`, `websockets` (или `aiohttp`), `cryptography` (Ed25519)
- Опционально `pywin32` / `psutil` — extra `Holix-Link[windows]` (как `Holix[windows]` сегодня)
- **Без** компиляции: wheels на PyPI для win_amd64, macosx arm64/x86_64, manylinux

---

## 10. Компоненты кодовой базы

| Компонент | Путь (план) | Описание |
|-----------|-------------|----------|
| `integrations/link/` | новый | Протокол, клиент daemon, jail executor |
| `api/routers/link.py` | новый | REST + WebSocket relay |
| `core/tools/link_fs.py` | новый | `link_read_file`, `link_write_file`, `link_list_directory` |
| `cli/commands/link.py` | новый | `holix link *` |
| `cli/link_worker.py` | новый | фоновый процесс (аналог `gateway_worker`) |
| `integrations/link/service_install.py` | новый | systemd / LaunchAgent / Task Scheduler |
| `integrations/link/paths.py` | новый | нормализация путей Win/Unix |
| `scripts/install-link.sh` / `.ps1` | новый | установщики |
| `docs/en|ru/LINK.md` | новый | пользовательская документация (Windows/Linux/macOS) |

Переиспользование:

- `core/platform_compat` — `resolve_holix_home`, `terminate_process`, `popen_background`
- `workspace_jail` / path guards из `core/tools/`
- `ProfileManager`, pairing UX как в `integrations/telegram/access_approval`
- `gateway_daemon` / supervisor pattern для фонового link worker на сервере не нужен — WS внутри uvicorn

---

## 11. Протокол (черновик)

### WebSocket: клиент → сервер (после pair)

```json
{"type": "rpc_result", "id": "uuid", "ok": true, "payload": {"entries": ["a.txt", "src/"]}}
```

### WebSocket: сервер → клиент

```json
{"type": "rpc_call", "id": "uuid", "op": "list_dir", "path": "src", "limit": 200}
```

Операции MVP: `list_dir`, `read_file`, `write_file`, `stat`, `mkdir` (опционально выкл.), `delete` (выкл. по умолчанию).

---

## 12. План реализации по фазам

> **Важно:** код пишется только после согласования этого документа.

### Фаза 0 — Согласование (текущий этап)

- [ ] Утвердить название (Holix Link / другое)
- [ ] Утвердить: только файлы в MVP или нужен read-only
- [ ] Утвердить: отдельный PyPI-пакет `Holix-Link` vs extra `Holix[link]`
- [ ] Утвердить модель хостинга relay (только self-hosted gateway / managed cloud)
- [x] Поддержка клиента: **Windows + Linux + macOS** (обязательно в MVP)

### Фаза 1 — MVP (оценка 4–5 недель с кроссплатформой)

| PR | Содержание | Зависимости |
|----|------------|-------------|
| **PR-1** | Спецификация протокола + типы (`integrations/link/protocol.py`) | — |
| **PR-2** | `integrations/link/paths.py` + jail (Unix + Windows path tests) | PR-1 |
| **PR-3** | Gateway: `POST /v1/link/pair`, `WS /v1/link/connect`, `links.db` | PR-1 |
| **PR-4** | Клиент: `holix-link pair`, daemon, jail executor (все ОС) | PR-2, PR-3 |
| **PR-5** | `holix-link install-service` — systemd / LaunchAgent / Task Scheduler | PR-4 |
| **PR-6** | Agent tools `link_*` + профиль `linked-*` auto setup | PR-3 |
| **PR-7** | CLI `holix link create|list|revoke`, doctor checks | PR-3 |
| **PR-8** | CI `link-client.yml` matrix (ubuntu, macos, windows) | PR-4, PR-5 |
| **PR-9** | Установщики `install-link.sh` + `install-link.ps1` | PR-4 |
| **PR-10** | Документация EN/RU (§ per OS) + `holix docs build` | PR-7, PR-9 |

**Критерий готовности MVP:** пользователь за NAT на **Windows, Linux или macOS** подключает папку; оператор через Telegram-профиль на сервере читает файл из этой папки; после перезагрузки клиента связь восстанавливается (`install-service`).

### Фаза 2 — Усиление (2 недели)

- Read-only режим по умолчанию + toggle `holix link grant write`
- OS keychain: **Keychain** (macOS), **Credential Manager** (Windows), **secretstorage** (Linux)
- Нативный диалог выбора папки в `wizard`
- Windows: полноценная Service + корпоративный `HTTPS_PROXY`
- Ограничение MIME/расширений
- Статус в `holix gateway status` / Prometheus метрики
- Уведомление клиенту при каждой записи файла

### Фаза 3 — Опционально

- Терминал в sandbox (ограниченный whitelist на клиенте) — отдельное согласие
- Selective sync кэша для офлайн-read
- Desktop tray app (Tauri/Electron)
- Managed relay для пользователей без своего VPS

---

## 13. Альтернативы (кратко)

| Подход | Плюсы | Минусы |
|--------|-------|--------|
| **Sync папки на сервер** | Проще для агента (локальный FS) | Диск, задержка, конфликты, не «живые» данные |
| **Только SSH reverse tunnel** | Зрелый протокол | Сложная установка, ключи SSH для пользователей |
| **Расширить `holix tui --web`** | Уже есть web UI | Нужен входящий порт / VPN; не NAT-friendly |
| **Telegram-only file upload** | Уже работает | Не папка, не непрерывный доступ |

**Рекомендация:** outbound Link Relay — лучший баланс простоты установки и безопасности для Holix.

---

## 14. Открытые вопросы для согласования

1. **Имя продукта:** Holix Link / Holix Remote / Holix Folder Bridge?
2. **MVP write:** разрешать запись файлов сразу или только read-only?
3. **Пакет:** отдельный `Holix-Link` на PyPI (меньше размер) или `pip install Holix[link]`?
4. **Кто может создавать pair-код:** только admin gateway или любой владелец профиля?
5. **Лимит одновременных link на профиль:** 1 папка = 1 link или несколько?
6. **Интеграция с Telegram:** отдельный бот для «клиентских» машин или тот же бот с ролью link?

---

## 15. Следующий шаг после согласования

1. Зафиксировать ответы на §14 в этом файле (версия 1.0).
2. Создать issue/PR stack по таблице Фазы 1.
3. Начать с **PR-1** (протокол + тесты контракта без сети).

---

*Документ подготовлен для ветки `feature/remote-folder-agent`. Изменения в коде до approval не вносятся.*