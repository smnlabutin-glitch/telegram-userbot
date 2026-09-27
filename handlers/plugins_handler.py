import logging
from telethon import TelegramClient, events
from card_engine import render_card
from plugins import get_plugin_config, update_plugin_config, PLUGIN_STATE
from plugins.always_online import start_always_online, stop_always_online
from plugins.time_name import start_autoname, stop_autoname

logger = logging.getLogger("userbot.handlers.plugins")

def register_plugins_handlers(client: TelegramClient, prefix: str):
    """Registers commands for plugins menu and management."""

    # .plugins or .menu
    @client.on(events.NewMessage(outgoing=True, pattern=rf"^{prefix}(?:plugins|menu)$"))
    async def plugins_menu_handler(event: events.NewMessage.Event):
        # Gather plugins list with current statuses
        items_list = []
        enabled_count = 0
        total_count = len(PLUGIN_STATE)

        for p_id, p_info in PLUGIN_STATE.items():
            is_enabled = p_info.get("enabled", False)
            if is_enabled:
                enabled_count += 1
            status_tag = " [ВКЛ]" if is_enabled else " [ВЫКЛ]"
            title = p_info.get("title", p_id) + status_tag
            cmd = p_info.get("command", f"{prefix}{p_id}")
            desc = p_info.get("description", "")
            items_list.append((cmd, f"{title} — {desc}"))

        card = render_card(
            title="Центр управления плагинами",
            subtitle="Каталог расширений и фоновых демонов Telegram юзербота",
            badge_text=f"{enabled_count}/{total_count} АКТИВНО",
            badge_type="running" if enabled_count > 0 else "info",
            items=items_list,
            meta_left=f"USERBOT EXTENSION ENGINE // {enabled_count} ACTIVE",
            meta_right=f"PREFIX: '{prefix}'",
            category="PLUGIN REGISTRY & DASHBOARD",
        )

        try:
            await event.delete()
        except Exception:
            pass

        await client.send_file(event.chat_id, file=card)

    # .plugin <name> <on|off>
    @client.on(events.NewMessage(outgoing=True, pattern=rf"^{prefix}plugin\s+(\w+)\s+(on|off)$"))
    async def toggle_plugin_handler(event: events.NewMessage.Event):
        p_name = event.pattern_match.group(1).lower()
        action = event.pattern_match.group(2).lower()
        target_enable = (action == "on")

        if p_name in ("online", "always_online"):
            update_plugin_config("always_online", enabled=target_enable)
            if target_enable:
                start_always_online(client)
            else:
                stop_always_online()
            p_title = "Вечный онлайн"
        elif p_name in ("autoname", "time_name"):
            update_plugin_config("time_name", enabled=target_enable)
            if target_enable:
                start_autoname(client)
            else:
                await stop_autoname(client)
            p_title = "Время в никнейме"
        else:
            await event.reply(f"⚠️ Неизвестный плагин: `{p_name}`. Используйте `{prefix}plugins` для просмотра каталога.")
            return

        card = render_card(
            title=f"Плагин {p_title}",
            subtitle=f"Плагин успешно {'активирован' if target_enable else 'деактивирован'}",
            badge_text="АКТИВЕН" if target_enable else "ВЫКЛЮЧЕН",
            badge_type="success" if target_enable else "warn",
            stats=[
                ("МОДУЛЬ", p_name),
                ("СТАТУС", "ВКЛЮЧЕН" if target_enable else "ОТКЛЮЧЕН"),
                ("РЕЖИМ", "24/7 Background"),
                ("МЕНЮ", f"{prefix}plugins"),
            ],
            meta_left="PLUGIN MANAGER // STATE UPDATED",
            meta_right=f"STATE: {'ON' if target_enable else 'OFF'}",
            category="PLUGIN STATE SWITCH",
        )

        try:
            await event.delete()
        except Exception:
            pass

        await client.send_file(event.chat_id, file=card)
