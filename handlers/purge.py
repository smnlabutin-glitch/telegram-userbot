import time
import asyncio
import logging
from telethon import TelegramClient, events, errors
from telethon.tl.types import User, Channel, Chat
from card_engine import render_card

logger = logging.getLogger("userbot.purge")

# Track ongoing purge operations to prevent concurrent conflicting runs
ACTIVE_PURGES = set()

def register_purge_handlers(client: TelegramClient, prefix: str):
    """Registers commands for purging user messages with 24/7 server resilience."""

    pattern = rf"^{prefix}(?:delall|purge_me|delme)(?:\s+(.+))?$"

    @client.on(events.NewMessage(outgoing=True, pattern=pattern))
    async def purge_handler(event: events.NewMessage.Event):
        target_arg = event.pattern_match.group(1)
        origin_chat = event.chat_id

        # 1. Resolve target entity
        target_entity = None
        target_name = ""

        try:
            if target_arg:
                target_str = target_arg.strip()
                # Support integer chat IDs (e.g. -100...)
                if (target_str.startswith("-") and target_str[1:].isdigit()) or target_str.isdigit():
                    target_entity = await client.get_entity(int(target_str))
                else:
                    target_entity = await client.get_entity(target_str)
            else:
                target_entity = await event.get_chat()
        except Exception as e:
            logger.error("Failed to resolve target entity '%s': %s", target_arg, e)
            err_card = render_card(
                title="Ошибка разрешения чата",
                subtitle=f"Не удалось найти указанный диалог: {target_arg}",
                badge_text="ОШИБКА",
                badge_type="error",
                stats=[
                    ("АРГУМЕНТ", str(target_arg or "Текущий чат")),
                    ("ТИП ОШИБКИ", type(e).__name__),
                ],
                meta_left="PURGE ROUTER // ERROR",
                category="ENTITY RESOLUTION FAILED",
            )
            await event.reply(file=err_card)
            return

        # Determine readable name of target entity
        if isinstance(target_entity, User):
            target_name = f"@{target_entity.username}" if target_entity.username else (target_entity.first_name or "User")
        elif isinstance(target_entity, (Channel, Chat)):
            target_name = f"@{target_entity.username}" if getattr(target_entity, "username", None) else (target_entity.title or f"Chat {target_entity.id}")
        else:
            target_name = str(getattr(target_entity, "title", getattr(target_entity, "id", "Unknown")))

        target_id = getattr(target_entity, "id", None)
        if target_id in ACTIVE_PURGES:
            await event.reply("⚠️ Очистка в этом диалоге уже выполняется в фоновом режиме.")
            return

        ACTIVE_PURGES.add(target_id)

        # Get own user info
        me = await client.get_me()
        my_id = me.id

        start_time = time.monotonic()
        messages_to_delete = []
        batch_size = 100
        total_deleted = 0
        chunks_count = 0

        # Inform user that deletion is starting
        status_msg = None
        try:
            status_msg = await event.edit("`[PURGE] Инициализация сканирования истории...`")
        except Exception:
            pass

        async def flush_batch(msgs: list) -> int:
            nonlocal chunks_count
            if not msgs:
                return 0
            chunks_count += 1
            for attempt in range(3):
                try:
                    await client.delete_messages(target_entity, msgs, revoke=True)
                    return len(msgs)
                except errors.FloodWaitError as fwe:
                    logger.warning("FloodWait encountered during purge: %ss", fwe.seconds)
                    await asyncio.sleep(fwe.seconds + 1)
                except Exception as ex:
                    logger.warning("Failed to delete chunk (attempt %s): %s", attempt + 1, ex)
                    await asyncio.sleep(0.5)
            return 0

        try:
            # 2. Iterate and collect message IDs
            can_use_server_filter = True
            scan_count = 0
            try:
                async for msg in client.iter_messages(target_entity, from_user="me"):
                    scan_count += 1
                    if status_msg and msg.id == status_msg.id:
                        continue
                    messages_to_delete.append(msg.id)

                    if len(messages_to_delete) >= batch_size:
                        deleted = await flush_batch(messages_to_delete)
                        total_deleted += deleted
                        messages_to_delete = []
                        await asyncio.sleep(0.15)
                    elif scan_count % 50 == 0:
                        # Yield to event loop to allow other tasks to process
                        await asyncio.sleep(0.02)
            except errors.FloodWaitError as fwe:
                logger.warning("FloodWait encountered during message scanning: %ss", fwe.seconds)
                await asyncio.sleep(fwe.seconds + 1)
            except Exception:
                can_use_server_filter = False

            # Fallback if from_user is not supported for this entity type
            if not can_use_server_filter:
                scan_count = 0
                async for msg in client.iter_messages(target_entity):
                    scan_count += 1
                    if msg.out or (msg.sender_id and msg.sender_id == my_id):
                        if status_msg and msg.id == status_msg.id:
                            continue
                        messages_to_delete.append(msg.id)

                        if len(messages_to_delete) >= batch_size:
                            deleted = await flush_batch(messages_to_delete)
                            total_deleted += deleted
                            messages_to_delete = []
                            await asyncio.sleep(0.15)
                        elif scan_count % 50 == 0:
                            await asyncio.sleep(0.02)

            # Delete any remaining messages
            if messages_to_delete:
                deleted = await flush_batch(messages_to_delete)
                total_deleted += deleted

            elapsed = max(0.01, time.monotonic() - start_time)
            speed = total_deleted / elapsed if elapsed > 0 else 0

            # Remove status message if present
            if status_msg:
                try:
                    await status_msg.delete()
                except Exception:
                    pass

            # 3. Render and send result card
            if total_deleted > 0:
                card = render_card(
                    title="Все сообщения удалены",
                    subtitle=f"История сообщений очищена в диалоге {target_name}",
                    badge_text="ОЧИЩЕНО",
                    badge_type="success",
                    stats=[
                        ("УДАЛЕНО СООБЩЕНИЙ", f"{total_deleted:,}"),
                        ("ЦЕЛЕВОЙ ДИАЛОГ", target_name[:18]),
                        ("ВРЕМЯ РАБОТЫ", f"{elapsed:.2f}s"),
                        ("СКОРОСТЬ", f"{speed:.1f} msg/s"),
                    ],
                    meta_left=f"TARGET ID: {getattr(target_entity, 'id', 'N/A')} // USERBOT PURGE",
                    meta_right=f"CHUNKS: {chunks_count} • LATENCY: ~{int(elapsed * 10)}ms",
                    category="DATABASE PURGE OPERATION",
                )
            else:
                card = render_card(
                    title="Сообщения не найдены",
                    subtitle=f"В целевом диалоге {target_name} отсутствуют ваши сообщения",
                    badge_text="ПУСТО",
                    badge_type="info",
                    stats=[
                        ("УДАЛЕНО", "0"),
                        ("ЦЕЛЕВОЙ ДИАЛОГ", target_name[:18]),
                        ("ВРЕМЯ СКАНИРОВАНИЯ", f"{elapsed:.2f}s"),
                        ("СТАТУС", "Очистка не требуется"),
                    ],
                    meta_left="SCAN FINISHED // ZERO MATCHES",
                    meta_right="CHUNKS: 0",
                    category="SCAN REPORT",
                )

            # Send card to the origin chat where command was triggered
            try:
                await client.send_file(origin_chat, file=card)
            except errors.ChatSendMediaForbiddenError:
                await client.send_file("me", file=card, caption=f"Отчёт по очистке в {target_name}")
            except Exception as e:
                logger.error("Failed to send purge card: %s", e)
                await client.send_message(
                    origin_chat,
                    f"**[PURGE COMPLETED]**\nУдалено сообщений: `{total_deleted}`\nДиалог: `{target_name}`\nВремя: `{elapsed:.2f}s`"
                )

        finally:
            ACTIVE_PURGES.discard(target_id)
