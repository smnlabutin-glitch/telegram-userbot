import os
import sys
import time
import signal
import asyncio
import logging
from logging.handlers import RotatingFileHandler
from telethon import TelegramClient, errors
from config import (
    validate_config,
    BASE_DIR,
    SESSION_NAME,
    COMMAND_PREFIX,
    FLOOD_SLEEP_THRESHOLD,
    LOG_DIR,
    LOG_LEVEL,
    LOG_MAX_BYTES,
    LOG_BACKUP_COUNT,
    KERU_BOT_TOKEN,
    GEMINI_API_KEY,
)
from handlers.purge import register_purge_handlers
from handlers.system import register_system_handlers
from handlers.plugins_handler import register_plugins_handlers
from plugins.always_online import register_always_online, stop_always_online
from plugins.time_name import register_time_name, stop_autoname
from plugins.anime_quiz import register_anime_quiz
from plugins.keru_bot import start_keru_bot, stop_keru_bot


# Configure logging with RotatingFileHandler for 24/7 operation
os.makedirs(LOG_DIR, exist_ok=True)
log_file = os.path.join(LOG_DIR, "userbot.log")

log_formatter = logging.Formatter(
    fmt="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

file_handler = RotatingFileHandler(
    log_file,
    maxBytes=LOG_MAX_BYTES,
    backupCount=LOG_BACKUP_COUNT,
    encoding="utf-8",
)
file_handler.setFormatter(log_formatter)

console_handler = logging.StreamHandler(sys.stdout)
console_handler.setFormatter(log_formatter)

numeric_level = getattr(logging, LOG_LEVEL, logging.INFO)
root_logger = logging.getLogger()
root_logger.setLevel(numeric_level)
root_logger.addHandler(file_handler)
root_logger.addHandler(console_handler)

# Suppress noisy telethon debug logs
logging.getLogger("telethon").setLevel(logging.WARNING)
logger = logging.getLogger("userbot")

async def run_userbot(api_id: int, api_hash: str, stop_event: asyncio.Event):
    session_path = os.path.join(BASE_DIR, SESSION_NAME)
    
    client = TelegramClient(
        session_path,
        api_id,
        api_hash,
        flood_sleep_threshold=FLOOD_SLEEP_THRESHOLD,
        connection_retries=-1,  # Infinite retries on disconnect
        retry_delay=2,          # Base delay between reconnect attempts
        auto_reconnect=True,
    )

    # Register handlers and plugins
    register_purge_handlers(client, COMMAND_PREFIX)
    register_system_handlers(client, COMMAND_PREFIX)
    register_plugins_handlers(client, COMMAND_PREFIX)
    register_always_online(client, COMMAND_PREFIX)
    register_time_name(client, COMMAND_PREFIX)
    register_anime_quiz(client, COMMAND_PREFIX)

    retry_delay = 5
    max_retry_delay = 60

    while not stop_event.is_set():
        try:
            logger.info("Connecting to Telegram MTProto...")
            await client.start()

            me = await client.get_me()
            user_name = f"@{me.username}" if me.username else (me.first_name or "Unknown")

            logger.info("=" * 54)
            logger.info("   TELEGRAM USERBOT // 24/7 PRODUCTION ENGINE   ")
            logger.info("=" * 54)
            logger.info("Authorized as  : %s (ID: %s)", user_name, me.id)
            logger.info("Session path   : %s.session", session_path)
            logger.info("Command prefix : '%s'", COMMAND_PREFIX)
            logger.info("Flood threshold: %ss", FLOOD_SLEEP_THRESHOLD)
            logger.info("Logging to     : %s", log_file)
            logger.info("Userbot is active and listening for commands 24/7.")
            logger.info("-" * 54)

            # Reset retry backoff on successful connection
            retry_delay = 5

            # Launch Keru Bot background task if configured
            keru_task = None
            if KERU_BOT_TOKEN and GEMINI_API_KEY:
                keru_task = asyncio.create_task(
                    start_keru_bot(api_id, api_hash, me.id, me.first_name or "Хозяин", stop_event)
                )

            # Run until disconnected or stop signal received
            run_task = asyncio.create_task(client.run_until_disconnected())
            stop_task = asyncio.create_task(stop_event.wait())

            done, pending = await asyncio.wait(
                [run_task, stop_task],
                return_when=asyncio.FIRST_COMPLETED,
            )

            for task in pending:
                task.cancel()

            stop_keru_bot()
            if keru_task and not keru_task.done():
                keru_task.cancel()

            if stop_event.is_set():
                logger.info("Stop event received. Disconnecting gracefully...")
                stop_always_online()
                await stop_autoname(client)
                await client.disconnect()
                break

            logger.warning("Telethon disconnected unexpectedly.")

        except (errors.SecurityError, errors.AuthKeyDuplicatedError) as fatal:
            logger.critical("Unrecoverable authentication error: %s", fatal)
            break
        except (errors.FloodWaitError, errors.FloodError) as fe:
            wait_s = getattr(fe, "seconds", 30)
            logger.warning("Telegram Flood wait: sleeping for %s seconds...", wait_s)
            await asyncio.sleep(wait_s + 1)
        except Exception as ex:
            logger.error("Connection or runtime exception: %s", ex, exc_info=True)

        if not stop_event.is_set():
            logger.info("Auto-reconnecting in %s seconds...", retry_delay)
            await asyncio.sleep(retry_delay)
            retry_delay = min(retry_delay * 2, max_retry_delay)

    stop_always_online()
    stop_keru_bot()
    if client.is_connected():
        await stop_autoname(client)
        await client.disconnect()
    logger.info("Userbot session closed safely.")

def main():
    api_id, api_hash = validate_config()

    stop_event = asyncio.Event()

    def signal_handler():
        logger.info("Termination signal received. Initiating graceful shutdown...")
        stop_event.set()

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    # Cross-platform signal registration
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, signal_handler)
        except (NotImplementedError, AttributeError):
            # Fallback for Windows
            try:
                signal.signal(sig, lambda s, f: signal_handler())
            except Exception:
                pass

    try:
        loop.run_until_complete(run_userbot(api_id, api_hash, stop_event))
    except (KeyboardInterrupt, SystemExit):
        logger.info("Interrupted by user. Exiting cleanly.")
    finally:
        loop.close()
        logger.info("Event loop stopped. Goodbye!")

if __name__ == "__main__":
    main()
