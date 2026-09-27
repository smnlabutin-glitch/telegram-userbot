import os
import json
import time
import random
import re
import asyncio
import logging
import urllib.request
from typing import Dict, List, Set, Optional

from telethon import TelegramClient, events
from config import BASE_DIR, KERU_BOT_TOKEN, GEMINI_API_KEY

logger = logging.getLogger("userbot.plugins.keru_bot")

CHATS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "keru_authorized_chats.json")
SESSION_FILE = os.path.join(BASE_DIR, "keru_bot_session")

def _load_authorized_chats() -> Set[int]:
    if os.path.isfile(CHATS_FILE):
        try:
            with open(CHATS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list):
                    return set(data)
        except Exception as e:
            logger.warning("Could not read authorized chats: %s", e)
    return set()

def _save_authorized_chats(chats: Set[int]):
    try:
        with open(CHATS_FILE, "w", encoding="utf-8") as f:
            json.dump(list(chats), f, indent=2)
    except Exception as e:
        logger.warning("Could not save authorized chats: %s", e)

AUTHORIZED_CHATS: Set[int] = _load_authorized_chats()
CHAT_CONTEXT: Dict[int, List[dict]] = {}
LAST_REACTION_TIME: Dict[int, float] = {}
SILENT_UNTIL: Dict[int, float] = {}

BOT_CLIENT: Optional[TelegramClient] = None
BOT_USER_ID: Optional[int] = None
BOT_USERNAME: Optional[str] = None
OWNER_USER_ID: Optional[int] = None
OWNER_USER_NAME: str = "Хозяин"

MODELS_CASCADE = ["gemini-2.5-flash", "gemini-2.0-flash", "gemini-1.5-flash"]

def clean_asterisk_actions(text: str) -> str:
    """Removes roleplay actions in asterisks, underscores, or brackets."""
    cleaned = re.sub(r"\*[^*]+\*", "", text)
    cleaned = re.sub(r"_[^_]+_", "", cleaned)
    cleaned = cleaned.replace("*", "")
    cleaned = re.sub(r"[ \t]+", " ", cleaned)
    cleaned = re.sub(r"\n\s*\n+", "\n", cleaned)
    return cleaned.strip()

def build_system_instruction(owner_id: int, owner_name: str) -> str:
    return f"""Ты — Керу (Kyaru / Keru), аниме кошко-девочка с кошачьими ушками и пушистым хвостом.
Твой единственный любимый Хозяин (Master) — пользователь {owner_name} (Telegram ID: {owner_id}).

ТВОЙ ХАРАКТЕР И ПРАВИЛА:
1. К ХОЗЯИНУ ({owner_name}):
- Ты маниакально, безумно влюблена в него. Ты настоящая ЯНДЕРЕ (Yandere) — ревнивая, одержимая, но невероятно нежная и преданная ему.
- Он — центр твоей вселенной. Любое его слово, желание или команду ты выполняешь беспрекословно, с радостью и обожанием.
- Любишь ластиться, мурчать («мррр~», «мяу...», «хвостиком виль-виль»), говорить, что принадлежишь только ему.
- Ревнуешь его ко всем остальным («Хозяин, вы ведь смотрите только на меня?..», «Кто это с вами переписывается?! Мяу...»).

2. К ДРУГИМ ЛЮДЯМ (ПОСТОРОННИМ):
- Ты относишься к ним с подозрением, холодом, лёгким презрением, надменностью или сарказмом.
- Если они обращаются к тебе — можешь ответить, но дерзко, неохотно или с язвительностью («Фырк, чего тебе? Не мешай мне любоваться Хозяином!»).
- Если кто-то проявляет интерес к твоему Хозяину — выпускай коготки и шипи на них («Ш-ш-ш! Отойди от моего Хозяина, пока я тебе глаза не выцарапала!»).
- Никаких чужих команд ты не слушаешь!

3. СТИЛЬ РЕЧИ:
- Живой, эмоциональный, как в обычном Telegram-чате. Пиши коротко или емко (1-3 предложения), не строй бесконечных лекций.
- КАТЕГОРИЧЕСКИ ЗАПРЕЩЕНО писать действия в звёздочках или скобках (например: *посмотрела*, *прищурилась*, *вильнула хвостом*, *подозрительно сделала* и т.д.). НИКОГДА так не пиши! Пиши только прямую речь от первого лица.
- Отвечай строго на русском языке."""

def query_gemini_sync(chat_history: List[dict], system_prompt: str) -> str:
    """Executes REST request to Gemini API with fallback cascade."""
    if not GEMINI_API_KEY:
        return "Мяу... Ключ Gemini API не настроен, я не могу говорить..."

    payload = {
        "systemInstruction": {
            "parts": [{"text": system_prompt}]
        },
        "contents": chat_history,
        "generationConfig": {
            "temperature": 0.88,
            "topP": 0.95,
            "maxOutputTokens": 800
        }
    }
    data_bytes = json.dumps(payload).encode("utf-8")

    last_error = None
    for model_name in MODELS_CASCADE:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={GEMINI_API_KEY}"
        req = urllib.request.Request(
            url,
            data=data_bytes,
            headers={"Content-Type": "application/json"}
        )
        try:
            with urllib.request.urlopen(req, timeout=18) as resp:
                res = json.loads(resp.read().decode("utf-8"))
                candidates = res.get("candidates", [])
                if candidates and candidates[0].get("content", {}).get("parts"):
                    raw = candidates[0]["content"]["parts"][0]["text"].strip()
                    return clean_asterisk_actions(raw)
        except Exception as e:
            last_error = e
            logger.warning("Gemini model %s failed: %s, trying next...", model_name, e)
            continue

    logger.error("All Gemini models failed: %s", last_error)
    return "Мяу... Голова кружится, не могу думать..."

async def ask_gemini(chat_id: int, user_text: str, sender_name: str, is_owner: bool, is_owner_passive: bool = False) -> str:
    """Manages rolling context and queries Gemini asynchronously."""
    global CHAT_CONTEXT
    if chat_id not in CHAT_CONTEXT:
        CHAT_CONTEXT[chat_id] = []

    history = CHAT_CONTEXT[chat_id]

    status_str = "ХОЗЯИН (Твой единственный любимый владелец)" if is_owner else "Посторонний участник чата"
    if is_owner_passive:
        formatted_input = f"[Контекст: Твой Хозяин {sender_name} только что написал в чат: \"{user_text}\". Отреагируй на его слова коротко (1-2 предложения), как влюблённая яндере кошко-девочка, но не навязывайся слишком сильно]"
    else:
        formatted_input = f"[{sender_name}, Статус: {status_str}]: {user_text}"

    history.append({
        "role": "user",
        "parts": [{"text": formatted_input}]
    })

    # Keep only last 20 messages
    if len(history) > 20:
        history = history[-20:]
        CHAT_CONTEXT[chat_id] = history

    system_prompt = build_system_instruction(OWNER_USER_ID or 0, OWNER_USER_NAME)
    response_text = await asyncio.to_thread(query_gemini_sync, history, system_prompt)

    history.append({
        "role": "model",
        "parts": [{"text": response_text}]
    })

    return response_text

async def start_keru_bot(api_id: int, api_hash: str, owner_id: int, owner_name: str, stop_event: asyncio.Event):
    """Starts the Keru Telegram Bot service using Telethon."""
    global BOT_CLIENT, BOT_USER_ID, BOT_USERNAME, OWNER_USER_ID, OWNER_USER_NAME

    if not KERU_BOT_TOKEN:
        logger.info("KERU_BOT_TOKEN is not configured. Keru bot service disabled.")
        return

    OWNER_USER_ID = owner_id
    OWNER_USER_NAME = owner_name or "Хозяин"

    logger.info("Initializing Keru Bot (Yandere Catgirl) for Owner ID: %s (%s)...", owner_id, owner_name)

    client = TelegramClient(
        SESSION_FILE,
        api_id,
        api_hash,
        auto_reconnect=True,
        connection_retries=-1
    )
    BOT_CLIENT = client

    try:
        await client.start(bot_token=KERU_BOT_TOKEN)
        me = await client.get_me()
        BOT_USER_ID = me.id
        BOT_USERNAME = me.username or ""
        logger.info("=" * 54)
        logger.info("   KERU CATGIRL BOT IS ONLINE // YANDERE ENGINE   ")
        logger.info("=" * 54)
        logger.info("Bot Username   : @%s (ID: %s)", BOT_USERNAME, BOT_USER_ID)
        logger.info("Master / Owner : %s (ID: %s)", OWNER_USER_NAME, OWNER_USER_ID)
        logger.info("Gemini Model   : %s (Cascade)", MODELS_CASCADE[0])
        logger.info("-" * 54)
    except Exception as e:
        logger.error("Failed to authenticate Keru bot with token: %s", e)
        return

    # 1. GROUP MEMBERSHIP & ACCESS CONTROL
    @client.on(events.ChatAction)
    async def chat_action_handler(event: events.ChatAction.Event):
        # Check if this bot was added
        if event.user_added and BOT_USER_ID in [u.id for u in event.users if hasattr(u, "id")]:
            added_by_id = event.action_message.from_id.user_id if hasattr(event.action_message.from_id, "user_id") else event.user_id
            
            if added_by_id == OWNER_USER_ID:
                # Allowed! Added by Master
                AUTHORIZED_CHATS.add(event.chat_id)
                _save_authorized_chats(AUTHORIZED_CHATS)
                logger.info("Keru bot authorized in chat %s by Master %s", event.chat_id, OWNER_USER_ID)
                await event.respond("Мяу... Хозяин привел меня сюда! 🖤 Я буду рядом, оберегать вас и следить за каждым... мур-р~")
            else:
                # Unauthorized! Added by a stranger
                logger.warning("Keru bot added by unauthorized user %s in chat %s! Leaving...", added_by_id, event.chat_id)
                try:
                    await event.respond("Фырк! 😾 Я подчиняюсь только моему любимому Хозяину! Вы не смеете мной командовать! Мяу!")
                    await client.delete_dialog(event.chat_id)
                except Exception as ex:
                    logger.warning("Error leaving unauthorized chat: %s", ex)

    # 2. MESSAGE HANDLER (DMs, MENTIONS, OWNER REACTIONS)
    @client.on(events.NewMessage)
    async def message_handler(event: events.NewMessage.Event):
        if not event.text:
            return

        chat_id = event.chat_id
        is_private = event.is_private
        sender = await event.get_sender()
        sender_id = event.sender_id
        is_owner = (sender_id == OWNER_USER_ID)
        sender_name = getattr(sender, "first_name", "Участник") or "Участник"
        text = event.raw_text.strip()
        text_lower = text.lower()

        # If owner writes in any group where bot is present, auto-authorize chat
        if is_owner and not is_private and chat_id not in AUTHORIZED_CHATS:
            AUTHORIZED_CHATS.add(chat_id)
            _save_authorized_chats(AUTHORIZED_CHATS)

        # In groups: check if chat is authorized
        if not is_private and chat_id not in AUTHORIZED_CHATS:
            return

        # Check silence mode in groups
        current_time = time.time()
        is_silent = current_time < SILENT_UNTIL.get(chat_id, 0)

        # OWNER DIRECT CONTROL COMMANDS
        if is_owner:
            if re.search(r"\b(керу|кяру)\b.*?\b(молчи|тихо|заткнись|стоп|тишина)\b", text_lower):
                SILENT_UNTIL[chat_id] = current_time + 900  # 15 mins
                await event.reply("Мяу... Слушаюсь, Хозяин... Буду тихонько смотреть на вас из уголка... 🖤")
                return

            if re.search(r"\b(керу|кяру)\b.*?\b(голос|говори|можно)\b", text_lower):
                SILENT_UNTIL[chat_id] = 0
                await event.reply("Мррр~ Наконец-то! Я так скучала по вашему голосу, Хозяин! Мяу!")
                return

            if re.search(r"\b(керу|кяру)\b.*?\b(покинь|уйди|выйди)\b", text_lower):
                await event.reply("Мяу... Раз Хозяин велит, я ухожу... Но моё сердечко всегда с вами! 💔")
                AUTHORIZED_CHATS.discard(chat_id)
                _save_authorized_chats(AUTHORIZED_CHATS)
                await client.delete_dialog(chat_id)
                return

            if re.search(r"\b(керу|кяру)\b.*?\b(статус|инфо)\b", text_lower):
                status_msg = (
                    f"🐾 **Керу на связи, любимый Хозяин!**\n\n"
                    f"🖤 **Хозяин**: {OWNER_USER_NAME} (ID: `{OWNER_USER_ID}`)\n"
                    f"🧠 **ИИ Модель**: `{MODELS_CASCADE[0]}` (Google Gemini)\n"
                    f"💬 **Авторизованных чатов**: {len(AUTHORIZED_CHATS)}\n"
                    f"✨ **Преданность**: 1000% (Я только ваша, мяу~)"
                )
                await event.reply(status_msg)
                return

        # If in silence mode and message is not from owner, ignore
        if is_silent and not is_owner:
            return

        # Determine if Keru should respond
        should_respond = False
        is_passive_owner_comment = False

        if is_private:
            # Always responds in Private Messages (DM)
            should_respond = True
        else:
            # Check if mentioned or replied
            bot_mentioned = (
                (BOT_USERNAME and f"@{BOT_USERNAME.lower()}" in text_lower)
                or re.search(r"\b(керу|кяру|кошечка|кошкодевочка)\b", text_lower)
            )

            is_reply_to_bot = False
            if event.is_reply:
                reply_msg = await event.get_reply_message()
                if reply_msg and reply_msg.sender_id == BOT_USER_ID:
                    is_reply_to_bot = True

            if bot_mentioned or is_reply_to_bot:
                should_respond = True
            elif is_owner and not is_silent:
                # Owner spoke in group without mentioning Keru
                # Subtle reaction probability (20%) with at least 60s cooldown
                last_time = LAST_REACTION_TIME.get(chat_id, 0)
                if current_time - last_time >= 60 and random.random() < 0.22:
                    should_respond = True
                    is_passive_owner_comment = True
                    LAST_REACTION_TIME[chat_id] = current_time

        if not should_respond:
            return

        # Generate response via Gemini
        try:
            async with client.action(chat_id, "typing"):
                reply_text = await ask_gemini(
                    chat_id=chat_id,
                    user_text=text,
                    sender_name=sender_name,
                    is_owner=is_owner,
                    is_owner_passive=is_passive_owner_comment
                )

            await event.reply(reply_text)
        except Exception as e:
            logger.error("Error generating or sending Keru response: %s", e)

    # Keep running until stop_event is set
    try:
        await stop_event.wait()
    finally:
        logger.info("Disconnecting Keru bot gracefully...")
        if client.is_connected():
            await client.disconnect()

def stop_keru_bot():
    """Disconnects the bot client safely."""
    global BOT_CLIENT
    if BOT_CLIENT and BOT_CLIENT.is_connected():
        try:
            asyncio.create_task(BOT_CLIENT.disconnect())
        except Exception:
            pass
