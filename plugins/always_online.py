import asyncio
import logging
import random
from telethon import TelegramClient, events, errors
from telethon.tl.functions.account import UpdateStatusRequest
from card_engine import render_card
from plugins import get_plugin_config, update_plugin_config

logger = logging.getLogger("userbot.plugins.online")

_online_task = None

async def _online_worker(client: TelegramClient):
    """
    Background worker that continuously maintains account 'Online' status.
    Telegram drops online indicator if no packet arrives within ~30-45s.
    We use an adaptive 16-20s interval with natural jitter (mimicking official clients),
    and fast recovery on reconnects so status never flickers offline.
    """
    logger.info("Always-Online background worker started.")
    try:
        while True:
            try:
                # If temporarily reconnecting, wait briefly and retry immediately
                if not client.is_connected():
                    await asyncio.sleep(2)
                    continue

                await client(UpdateStatusRequest(offline=False))
                logger.debug("Sent UpdateStatusRequest(offline=False)")

                # Natural jitter (16-20s) ensures no robotic pattern while staying
                # well within Telegram's server-side timeout window
                delay = random.uniform(16.0, 20.0)
                await asyncio.sleep(delay)

            except errors.FloodWaitError as fwe:
                logger.warning("FloodWait in always_online: sleeping %ss", fwe.seconds)
                await asyncio.sleep(fwe.seconds + 2)
            except asyncio.CancelledError:
                raise
            except Exception as e:
                logger.error("Exception in always_online ping: %s", e)
                # On transient glitch, recover in 3s so account doesn't drop offline
                await asyncio.sleep(3)
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
                ("ИНТЕРВАЛ ПИНГА", "16–20 сек (Adaptive)"),
                ("РЕЖИМ РАБОТЫ", "Daemon 24/7"),
                ("ПЕРЕКЛЮЧЕНИЕ", f"{prefix}online [on|off]"),
            ],
            meta_left="PLUGIN // ALWAYS_ONLINE v1.1",
            meta_right="AUTO-PING: ADAPTIVE",
            category="ONLINE STATUS MANAGER",
        )

        try:
            await event.delete()
        except Exception:
            pass

        await client.send_file(event.chat_id, file=card)
