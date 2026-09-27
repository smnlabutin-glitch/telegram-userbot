import asyncio
import logging
from telethon import TelegramClient, events, errors
from telethon.tl.functions.account import UpdateStatusRequest
from card_engine import render_card
from plugins import get_plugin_config, update_plugin_config

logger = logging.getLogger("userbot.plugins.online")

_online_task = None

async def _online_worker(client: TelegramClient):
    """Background task to continuously keep account status online."""
    logger.info("Always-Online background worker started.")
    try:
        while True:
            try:
                if client.is_connected():
                    await client(UpdateStatusRequest(offline=False))
                    logger.debug("Sent UpdateStatusRequest(offline=False)")
            except errors.FloodWaitError as fwe:
                logger.warning("FloodWait in always_online: sleeping %ss", fwe.seconds)
                await asyncio.sleep(fwe.seconds + 2)
            except Exception as e:
                logger.error("Exception in always_online ping: %s", e)
            await asyncio.sleep(25)
    except asyncio.CancelledError:
        logger.info("Always-Online worker cancelled.")

def start_always_online(client: TelegramClient):
    global _online_task
    if _online_task is None or _online_task.done():
        _online_task = asyncio.create_task(_online_worker(client))
        logger.info("Always-Online task initiated.")

def stop_always_online():
    global _online_task
    if _online_task and not _online_task.done():
        _online_task.cancel()
        _online_task = None
        logger.info("Always-Online task stopped.")

def register_always_online(client: TelegramClient, prefix: str):
    """Registers always_online commands and launches worker if enabled in state."""
    cfg = get_plugin_config("always_online")
    if cfg.get("enabled", False):
        start_always_online(client)

    pattern = rf"^{prefix}(?:online|always_online)(?:\s+(on|off|status))?$"

    @client.on(events.NewMessage(outgoing=True, pattern=pattern))
    async def online_cmd(event: events.NewMessage.Event):
        subcmd = event.pattern_match.group(1)
        if subcmd:
            subcmd = subcmd.lower()

        cfg = get_plugin_config("always_online")
        current_status = cfg.get("enabled", False)

        if subcmd == "on":
            if not current_status:
                update_plugin_config("always_online", enabled=True)
                start_always_online(client)
            badge_text = "АКТИВЕН"
            badge_type = "success"
            title = "Вечный онлайн включен"
            subtitle = "Статус учетной записи постоянно удерживается в сети 24/7"
            stat_status = "ВКЛЮЧЕН"
        elif subcmd == "off":
            if current_status:
                update_plugin_config("always_online", enabled=False)
                stop_always_online()
            badge_text = "ВЫКЛЮЧЕН"
            badge_type = "warn"
            title = "Вечный онлайн отключен"
            subtitle = "Автоматическая отправка статуса 'В сети' остановлена"
            stat_status = "ВЫКЛЮЧЕН"
        else:
            # Status check
            stat_status = "АКТИВЕН" if current_status else "ОТКЛЮЧЕН"
            badge_text = "ОНЛАЙН" if current_status else "ПАУЗА"
            badge_type = "success" if current_status else "info"
            title = "Плагин вечного онлайна"
            subtitle = "Фоновый демон поддержания онлайн-статуса аккаунта"

        card = render_card(
            title=title,
            subtitle=subtitle,
            badge_text=badge_text,
            badge_type=badge_type,
            stats=[
                ("СТАТУС ПЛАГИНА", stat_status),
                ("ИНТЕРВАЛ ПИНГА", "25 сек"),
                ("РЕЖИМ РАБОТЫ", "Daemon 24/7"),
                ("ПЕРЕКЛЮЧЕНИЕ", f"{prefix}online [on|off]"),
            ],
            meta_left="PLUGIN // ALWAYS_ONLINE v1.0",
            meta_right="AUTO-PING: ENABLED",
            category="ONLINE STATUS MANAGER",
        )

        try:
            await event.delete()
        except Exception:
            pass

        await client.send_file(event.chat_id, file=card)
