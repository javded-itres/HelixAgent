"""Interactive pickers and callback handling for MAX."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from cli.shared.slash_input import is_mode_slash, is_models_slash, normalize_slash_input
from core.i18n import host_locale, t
from integrations.max.keyboards import (
    MODE_LABELS,
    mode_picker_keyboard,
    mode_picker_text,
    models_provider_keyboard,
    models_root_keyboard,
    parse_callback,
    profile_picker_keyboard,
    sessions_picker_keyboard,
    status_menu_keyboard,
    stream_picker_keyboard,
    tools_picker_keyboard,
)
from integrations.telegram.interactive import profile_model_summary
from integrations.telegram.model_switch import (
    MODELS_PAGE_SIZE,
    PROVIDERS_PAGE_SIZE,
    apply_preset_index,
    apply_provider_model_index,
    build_models_menu,
    current_model_label,
)

if TYPE_CHECKING:
    from integrations.max.host import MaxHost


class MaxInteractive:
    def __init__(self, host: MaxHost) -> None:
        self._host = host

    @property
    def _session(self) -> Any:
        return self._host._session

    async def handle_slash(self, command: str) -> bool:
        cmd = normalize_slash_input(command.strip())
        lower = cmd.lower()
        parts = lower.split()

        if is_models_slash(cmd):
            await self.show_models()
            return True

        if is_mode_slash(cmd):
            if len(parts) > 1 and parts[1] in self._host._execution_modes:
                self._host._execution_mode_index = self._host._execution_modes.index(parts[1])
                await self._host._send_text(t("mode_set", host_locale(self._host), mode=parts[1]))
            else:
                await self.show_mode_picker()
            return True

        if lower.startswith("/stream"):
            if len(parts) > 1:
                self._host.streaming_enabled = parts[1] in ("on", "true", "1")
                state = "on" if self._host.streaming_enabled else "off"
                await self._host._send_text(t("streaming", host_locale(self._host), state=state))
            else:
                await self.show_stream_picker()
            return True

        if lower.startswith("/profile"):
            if len(parts) >= 2:
                return False
            await self.show_profile_picker()
            return True

        if lower in ("/sessions",):
            await self.show_sessions_picker()
            return True

        if lower.startswith("/switch"):
            if len(parts) >= 2 and parts[1].isdigit():
                return False
            await self.show_sessions_picker()
            return True

        if lower == "/tools":
            await self.show_tools_picker()
            return True

        if lower == "/skills" or lower.startswith("/skills "):
            from cli.shared.commands.skills_commands import run_skills_command

            await run_skills_command(self._host, cmd)
            return True

        if lower.startswith("/subagent") or lower == "/subagents":
            from cli.shared.commands.subagent_commands import run_subagents_command

            await run_subagents_command(self._host, cmd)
            return True

        if lower in ("/status", "/menu"):
            await self.show_status()
            return True

        if lower.startswith("/mcp"):
            await self.show_mcp_menu(cmd)
            return True

        return False

    async def apply_callback(self, action: str, value: str) -> str:
        if action == "m" and value in self._host._execution_modes:
            self._host._execution_mode_index = self._host._execution_modes.index(value)
            await self.show_mode_picker()
            return t("tg.mode", host_locale(self._host), mode=value)

        if action == "st":
            self._host.streaming_enabled = value == "1"
            await self.show_stream_picker()
            state = "on" if self._host.streaming_enabled else "off"
            return t("tg.streaming", host_locale(self._host), state=state)

        if action == "pi":
            profiles = self._session.ui_profiles
            idx = int(value)
            if 0 <= idx < len(profiles):
                name = profiles[idx]
                if name != self._host.profile:
                    await self._host._switch_profile(name)
                    return t("tg.profile", host_locale(self._host), name=name)
                return t("tg.profile_same", host_locale(self._host), name=name)
            return t("tg.profile_invalid", host_locale(self._host))

        if action == "s":
            sessions = self._session.ui_sessions
            idx = int(value)
            if 0 <= idx < len(sessions):
                cid = sessions[idx].get("conversation_id", "")
                self._host._session.conversation_id = cid
                from core.session_models import restore_session_model

                restored = restore_session_model(self._host)
                title = sessions[idx].get("title") or cid
                model_line = f"\n{t('tg.model', host_locale(self._host), label=restored)}" if restored else ""
                await self._host._send_text(f"**Сессия:** `{title}`{model_line}")
                return t("tg.session_switched", host_locale(self._host))
            return t("tg.session_invalid", host_locale(self._host))

        if action == "sp":
            await self.show_sessions_picker(page=int(value))
            return ""

        if action == "sn":
            await self._host._create_new_session()
            await self.show_sessions_picker()
            return t("tg.new_session", host_locale(self._host))

        if action == "t":
            self._host._show_full_tool_result(int(value))
            return t("tg.tool_result", host_locale(self._host))

        if action == "mp":
            label = await apply_preset_index(self._host, int(value))
            idx = self._session.ui_models_provider_idx
            if idx is not None:
                await self.show_provider_models(idx, page=self._session.ui_models_page)
            else:
                await self.show_models(page=self._session.ui_providers_page)
            return t("tg.model", host_locale(self._host), label=label)

        if action == "mg":
            await self.show_provider_models(int(value), page=0)
            return ""

        if action == "mgp":
            await self.show_models(provider_page=int(value))
            return ""

        if action == "mv":
            parts = value.split(":", 1)
            if len(parts) == 2:
                await self.show_provider_models(int(parts[0]), page=int(parts[1]))
            return ""

        if action == "mm":
            parts = value.split(":", 1)
            if len(parts) != 2:
                return t("tg.error", host_locale(self._host))
            pi, mi = int(parts[0]), int(parts[1])
            label = await apply_provider_model_index(self._host, pi, mi)
            await self.show_provider_models(pi, page=self._session.ui_models_page)
            return t("tg.model", host_locale(self._host), label=label)

        if action == "mb":
            await self.show_models()
            return ""

        if action == "r":
            await self._refresh(value)
            return ""

        return t("tg.unknown_action", host_locale(self._host))

    async def _refresh(self, kind: str) -> None:
        if kind == "compress":
            from cli.shared.commands.context_compress import run_context_compress

            await run_context_compress(self._host)
            return

        dispatch = {
            "mode": self.show_mode_picker,
            "profile": self.show_profile_picker,
            "sessions": self.show_sessions_picker,
            "stream": self.show_stream_picker,
            "models": self.show_models,
            "tools": self.show_tools_picker,
            "status": self.show_status,
        }
        fn = dispatch.get(kind)
        if fn:
            await fn()

    async def show_mode_picker(self) -> None:
        current = self._session.execution_mode
        await self._host._send_text_with_keyboard(
            mode_picker_text(current),
            mode_picker_keyboard(self._host._execution_modes, current),
        )

    async def show_stream_picker(self) -> None:
        on = self._host.streaming_enabled
        text = (
            "**Стриминг ответа**\n"
            f"Сейчас: `{'on' if on else 'off'}`\n\n"
            "_При включении ответ обновляется в одном сообщении по мере генерации._"
        )
        await self._host._send_text_with_keyboard(text, stream_picker_keyboard(on))

    async def show_profile_picker(self) -> None:
        profiles = self._host._get_available_profiles()
        self._session.ui_profiles = profiles
        lines = [
            "**Профиль Helix**",
            f"Сейчас: `{self._host.profile}`",
            "",
            "_Профиль задаёт модели, память и skills. Смена создаёт новую сессию._",
        ]
        await self._host._send_text_with_keyboard(
            "\n".join(lines),
            profile_picker_keyboard(profiles, self._host.profile),
        )

    async def show_sessions_picker(self, *, page: int = 0) -> None:
        if self._host.agent:
            try:
                self._session.ui_sessions = await self._host.agent.list_conversations(limit=24)
            except Exception:
                self._session.ui_sessions = []
        sessions = self._session.ui_sessions
        if not sessions:
            await self._host._send_text_with_keyboard(
                "**Сессии**\nНет сохранённых сессий.\n\n_Отправьте сообщение или создайте новую_",
                sessions_picker_keyboard([], self._host.conversation_id),
            )
            return

        self._session.ui_sessions_page = page
        lines = [
            "**Сессии**",
            f"Текущая: `{self._host.conversation_id}`",
            "",
            "_Выберите сессию или создайте новую_",
        ]
        await self._host._send_text_with_keyboard(
            "\n".join(lines),
            sessions_picker_keyboard(sessions, self._host.conversation_id, page=page),
        )

    async def show_tools_picker(self) -> None:
        tools = self._host._recent_tool_results
        if not tools:
            await self._host._send_text(t("tg.no_tools", host_locale(self._host)))
            return
        lines = ["**Последние tools**", "_Нажмите, чтобы получить полный вывод_"]
        await self._host._send_text_with_keyboard(
            "\n".join(lines),
            tools_picker_keyboard(tools),
        )

    def _load_models_menu(self) -> None:
        state = build_models_menu(self._host.profile)
        self._session.ui_model_presets = list(state.presets)
        self._session.ui_providers = list(state.providers)

    async def show_models(self, *, provider_page: int = 0) -> None:
        self._load_models_menu()
        self._session.ui_models_provider_idx = None
        self._session.ui_providers_page = provider_page

        presets = self._session.ui_model_presets
        providers = self._session.ui_providers
        active = self._host.agent.model if self._host.agent else current_model_label(self._session)

        lines = [
            "**Модель для чата**",
            f"Профиль: `{self._host.profile}`",
            f"Сейчас: `{active}`",
            "",
            "**Пресеты** — main, agent_models",
            "**Провайдеры** — список моделей без префикса",
        ]
        if not presets and not providers:
            lines.append("\n**Нет моделей** — `helix models setup`")
            await self._host._send_text("\n".join(lines))
            return

        await self._host._send_text_with_keyboard(
            "\n".join(lines),
            models_root_keyboard(
                presets,
                providers,
                self._session.active_model_slot,
                provider_page=provider_page,
                page_size=PROVIDERS_PAGE_SIZE,
            ),
        )

    async def show_provider_models(self, provider_idx: int, *, page: int = 0) -> None:
        if not self._session.ui_providers:
            self._load_models_menu()
        providers = self._session.ui_providers
        if provider_idx < 0 or provider_idx >= len(providers):
            await self.show_models()
            return

        prov = providers[provider_idx]
        self._session.ui_models_provider_idx = provider_idx
        self._session.ui_models_page = page

        active = self._host.agent.model if self._host.agent else "—"
        total = len(prov.models)
        pages = max(1, (total + MODELS_PAGE_SIZE - 1) // MODELS_PAGE_SIZE)

        lines = [
            f"**Провайдер** `{prov.name}`",
            f"Сейчас в чате: `{active}`",
            f"Моделей: {total}",
        ]
        if pages > 1:
            lines.append(f"Страница {page + 1} / {pages}")
        lines.append("")
        lines.append("_Выберите модель (имя без префикса провайдера)_")

        await self._host._send_text_with_keyboard(
            "\n".join(lines),
            models_provider_keyboard(
                prov.name,
                list(prov.models),
                self._session.active_model_slot,
                provider_idx,
                page=page,
                page_size=MODELS_PAGE_SIZE,
            ),
        )

    async def show_mcp_menu(self, command: str = "/mcp") -> None:
        cmd = command.lower()
        parts = cmd.split()
        if len(parts) > 1:
            sub = parts[1]
            if sub == "list":
                await self._host._mcp_list()
                return
            if sub in ("install", "add"):
                arg = " ".join(parts[2:]) if len(parts) > 2 else ""
                self._host.run_worker(self._host._mcp_install(arg))
                return

        await self._host._mcp_list()

    async def show_status(self) -> None:
        mode = self._session.execution_mode
        stream = "on" if self._host.streaming_enabled else "off"
        mode_title = MODE_LABELS.get(mode, (mode, ""))[0]
        model_line = current_model_label(self._session)
        if self._host.agent:
            model_line = self._host.agent.model
        subagents = "—"
        if self._host.agent:
            cfg = getattr(self._host.agent, "config", None)
            if cfg and getattr(cfg, "enable_subagents", False):
                subagents = "вкл"
            else:
                subagents = "выкл"

        headline, rows = profile_model_summary(self._host.profile)
        lines = [
            "**Helix — статус**",
            f"Профиль: `{self._host.profile}`",
            f"Модель: `{model_line}`",
            f"Режим: `{mode}` ({mode_title})",
            f"Стриминг: `{stream}`",
            f"Субагенты: `{subagents}`",
            f"Сессия: `{self._host.conversation_id}`",
        ]
        if rows:
            lines.append("")
            lines.append("**Агенты:**")
            for name, provider, mdl in rows:
                lines.append(f"• `{name}` — {provider} / {mdl}")
        await self._host._send_text_with_keyboard(
            "\n".join(lines),
            status_menu_keyboard(host_locale(self._host)),
        )


async def dispatch_callback(host: MaxHost, payload: str) -> str:
    if payload.startswith("cfm:"):
        return ""
    if payload.startswith("plan:"):
        return ""
    parsed = parse_callback(payload)
    if parsed is None:
        return ""
    action, value = parsed
    return await MaxInteractive(host).apply_callback(action, value)