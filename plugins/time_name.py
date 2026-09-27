import asyncio
import logging
from datetime import datetime, timezone, timedelta
from telethon import TelegramClient, events, errors
from telethon.tl.functions.account import UpdateProfileRequest
from card_engine import render_card
from plugins import get_plugin_config, update_plugin_config

logger = logging.getLogger("userbot.plugins.autoname")

_autoname_task = None

def get_current_time_str(tz_offset: int = 3) -> str:
    tz = timezone(timedelta(hours=tz_offset))
    now = datetime.now(tz)
    return now.strftime("%H:%M")

async def _autoname_worker(client: TelegramClient):
    """Background task updating account name with time every minute."""
    logger.info("Time-in-Name worker started.")
    try:
        while True:
            cfg = get_plugin_config("time_name")
            if not cfg.get("enabled", False):
                break

            tz_offset = cfg.get("tz_offset", 3)
            orig_name = cfg.get("original_first_name", "")
            orig_last = cfg.get("original_last_name", "")

            # If original name is empty, fetch from Telegram
            if not orig_name:
                me = await client.get_me()
                orig_name = me.first_name or "User"
                orig_last = me.last_name or ""
                update_plugin_config("time_name", original_first_name=orig_name, original_last_name=orig_last)

            tz = timezone(timedelta(hours=tz_offset))
            now = datetime.now(tz)
            time_str = now.strftime("%H:%M")

            # Format name: e.g. "Name | 15:05" (max length in Telegram is 64 chars)
            base_first = orig_name.strip()
            new_first = f"{base_first} | {time_str}"[:64]

            try:
                if client.is_connected():
                    await client(UpdateProfileRequest(first_name=new_first))
                    logger.debug("Updated profile first_name to: %s", new_first)
            except errors.FloodWaitError as fwe:
                logger.warning("FloodWait in autoname: sleeping %ss", fwe.seconds)
                await asyncio.sleep(fwe.seconds + 2)
            except Exception as e:
                logger.error("Exception updating name in autoname: %s", e)

            # Sleep until the next full minute (00 seconds)
            sec = datetime.now(tz).second
            sleep_time = max(1, 60 - sec)
            await asyncio.sleep(sleep_time)

    except asyncio.CancelledError:
        logger.info("Time-in-Name worker cancelled.")

def start_autoname(client: TelegramClient):
    global _autoname_task
    if _autoname_task is None or _autoname_task.done():
        _autoname_task = asyncio.create_task(_autoname_worker(client))
        logger.info("Time-in-Name task initiated.")

async def stop_autoname(client: TelegramClient):
    global _autoname_task
    if _autoname_task and not _autoname_task.done():
        _autoname_task.cancel()
        _autoname_task = None
        logger.info("Time-in-Name task stopped.")

    # Restore original name if stored
    cfg = get_plugin_config("time_name")
    orig_name = cfg.get("original_first_name", "")
    if orig_name and client.is_connected():
        try:
            orig_last = cfg.get("original_last_name", "")
            await client(UpdateProfileRequest(first_name=orig_name, last_name=orig_last))
            logger.info("Restored original profile name: %s %s", orig_name, orig_last)
        except Exception as e:
            logger.error("Failed to restore original name: %s", e)

def register_time_name(client: TelegramClient, prefix: str):
    """Registers autoname commands and launches worker if enabled in state."""
    cfg = get_plugin_config("time_name")
    if cfg.get("enabled", False):
        start_autoname(client)

    pattern = rf"^{prefix}(?:autoname|time_name)(?:\s+(on|off|status|tz(?:\s+([+-]?\d+))?))?$"

    @client.on(events.NewMessage(outgoing=True, pattern=pattern))
    async def autoname_cmd(event: events.NewMessage.Event):
        match = event.pattern_match
        subcmd = match.group(1) or ""
        subcmd = subcmd.strip().lower()

        cfg = get_plugin_config("time_name")
        current_status = cfg.get("enabled", False)
        tz_offset = cfg.get("tz_offset", 3)

        if subcmd.startswith("tz"):
            tz_val = match.group(2)
            if tz_val is not None:
                try:
                    tz_offset = int(tz_val)
                    update_plugin_config("time_name", tz_offset=tz_offset)
                except ValueError:
                    pass
            card = render_card(
                title="Часовой пояс обновлен",
                subtitle=f"Время в никнейме теперь использует UTC{'+' if tz_offset >= 0 else ''}{tz_offset}",
                badge_text=f"UTC{'+' if tz_offset >= 0 else ''}{tz_offset}",
                badge_type="info",
                stats=[
                    ("ЧАСОВОЙ ПОЯС", f"UTC{'+' if tz_offset >= 0 else ''}{tz_offset}"),
                    ("ТЕКУЩЕЕ ВРЕМЯ", get_current_time_str(tz_offset)),
                    ("СТАТУС ПЛАГИНА", "АКТИВЕН" if current_status else "ОТКЛЮЧЕН"),
                    ("ОБНОВЛЕНИЕ", "Каждую минуту"),
                ],
                meta_left="PLUGIN // TIME_NAME v1.0",
                meta_right=f"TZ: UTC{'+' if tz_offset >= 0 else ''}{tz_offset}",
                category="TIMEZONE CONFIGURATION",
            )
            try:
                await event.delete()
            except Exception:
                pass
            await client.send_file(event.chat_id, file=card)
            return

        if subcmd == "on":
            me = await client.get_me()
            orig_name = me.first_name or "User"
            orig_last = me.last_name or ""
            # Strip previous timestamp if already in name
            if " | " in orig_name:
                orig_name = orig_name.split(" | ")[0].strip()

            update_plugin_config(
                "time_name",
                enabled=True,
                original_first_name=orig_name,
                original_last_name=orig_last,
            )
            start_autoname(client)
            badge_text = "АКТИВЕН"
            badge_type = "success"
            title = "Время в никнейме включено"
            subtitle = f"Имя обновляется каждую минуту. Текущее: {orig_name} | {get_current_time_str(tz_offset)}"
            stat_status = "ВКЛЮЧЕН"
        elif subcmd == "off":
            update_plugin_config("time_name", enabled=False)
            await stop_autoname(client)
            badge_text = "ВЫКЛЮЧЕН"
            badge_type = "warn"
            title = "Время в никнейме отключено"
            subtitle = f"Исходное имя пользователя ({cfg.get('original_first_name', 'User')}) успешно восстановлено"
            stat_status = "ВЫКЛЮЧЕН"
        else:
            # Status check
            stat_status = "АКТИВЕН" if current_status else "ОТКЛЮЧЕН"
            badge_text = "ВКЛЮЧЕН" if current_status else "ВЫКЛЮЧЕН"
            badge_type = "success" if current_status else "info"
            title = "Плагин: Время в никнейме"
            subtitle = f"Формат: [Имя | {get_current_time_str(tz_offset)}]"

        card = render_card(
            title=title,
            subtitle=subtitle,
            badge_text=badge_text,
            badge_type=badge_type,
            stats=[
                ("СТАТУС", stat_status),
                ("ТЕКУЩЕЕ ВРЕМЯ", get_current_time_str(tz_offset)),
                ("ЧАСОВОЙ ПОЯС", f"UTC{'+' if tz_offset >= 0 else ''}{tz_offset}"),
                ("ПЕРЕКЛЮЧЕНИЕ", f"{prefix}autoname [on|off]"),
            ],
            meta_left="PLUGIN // TIME_NAME v1.0",
            meta_right=f"TZ: UTC+{tz_offset} • SYNC: 60s",
            category="DYNAMIC NICKNAME CLOCK",
        )

        try:
            await event.delete()
        except Exception:
            pass

        await client.send_file(event.chat_id, file=card)
