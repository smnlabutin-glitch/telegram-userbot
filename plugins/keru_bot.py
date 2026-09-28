import os
import json
import time
import random
import re
import asyncio
import logging
import base64
import io
import urllib.request
import urllib.error
from typing import Dict, List, Set, Optional

from telethon import TelegramClient, events
from config import BASE_DIR, KERU_BOT_TOKEN, PROXYAPI_KEY

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

# --- MASTER MEMORY & DYNAMIC DIRECTIVES ---
MEMORY_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "keru_memory.json")

def _load_memory() -> dict:
    default_mem = {
        "ignored_users": [],
        "ignored_chats": [],
        "chat_only_owner": [],
        "custom_rules": [],
        "attitude_overrides": {}
    }
    if os.path.isfile(MEMORY_FILE):
        try:
            with open(MEMORY_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    default_mem.update(data)
                    return default_mem
        except Exception as e:
            logger.warning("Could not read keru memory: %s", e)
    return default_mem

def _save_memory(mem: dict):
    try:
        with open(MEMORY_FILE, "w", encoding="utf-8") as f:
            json.dump(mem, f, indent=2, ensure_ascii=False)
    except Exception as e:
        logger.warning("Could not save keru memory: %s", e)

KERU_MEMORY: dict = _load_memory()
DIRECTIVE_PATTERN = re.compile(r"\[DIRECTIVE:([A-Z_]+)(?:[\s:]([^\]]+))?\]", re.IGNORECASE)

def process_directives(response_text: str, chat_id: int) -> str:
    """Parses and executes behavior directives ordered by Master in natural language."""
    global KERU_MEMORY, SILENT_UNTIL
    matches = DIRECTIVE_PATTERN.findall(response_text)
    if not matches:
        return response_text

    updated = False
    for action, arg in matches:
        action = action.upper().strip()
        arg = (arg or "").strip()
        logger.info("Executing Master Directive: %s (arg: %s)", action, arg)

        if action == "IGNORE_USER" and arg:
            clean_arg = arg.lstrip("@").lower()
            if clean_arg not in KERU_MEMORY.setdefault("ignored_users", []):
                KERU_MEMORY["ignored_users"].append(clean_arg)
                updated = True
        elif action == "UNIGNORE_USER" and arg:
            clean_arg = arg.lstrip("@").lower()
            if clean_arg in KERU_MEMORY.get("ignored_users", []):
                KERU_MEMORY["ignored_users"].remove(clean_arg)
                updated = True
        elif action == "IGNORE_CHAT":
            if chat_id not in KERU_MEMORY.setdefault("ignored_chats", []):
                KERU_MEMORY["ignored_chats"].append(chat_id)
                updated = True
        elif action == "UNIGNORE_CHAT":
            if chat_id in KERU_MEMORY.get("ignored_chats", []):
                KERU_MEMORY["ignored_chats"].remove(chat_id)
                updated = True
        elif action == "ONLY_OWNER_CHAT":
            if chat_id not in KERU_MEMORY.setdefault("chat_only_owner", []):
                KERU_MEMORY["chat_only_owner"].append(chat_id)
                updated = True
        elif action == "ALLOW_OTHERS_CHAT":
            if chat_id in KERU_MEMORY.get("chat_only_owner", []):
                KERU_MEMORY["chat_only_owner"].remove(chat_id)
                updated = True
        elif action == "SILENT_CHAT":
            SILENT_UNTIL[chat_id] = time.time() + 3600  # 1 hour
        elif action == "UNSILENT_CHAT":
            SILENT_UNTIL[chat_id] = 0
        elif action == "SET_ATTITUDE" and ":" in arg:
            target, attitude = arg.split(":", 1)
            target = target.strip().lstrip("@").lower()
            KERU_MEMORY.setdefault("attitude_overrides", {})[target] = attitude.strip()
            updated = True
        elif action == "ADD_RULE" and arg:
            if arg not in KERU_MEMORY.setdefault("custom_rules", []):
                KERU_MEMORY["custom_rules"].append(arg)
                updated = True
        elif action == "CLEAR_RULES":
            KERU_MEMORY["custom_rules"] = []
            KERU_MEMORY["attitude_overrides"] = {}
            KERU_MEMORY["ignored_users"] = []
            KERU_MEMORY["chat_only_owner"] = []
            updated = True

    if updated:
        _save_memory(KERU_MEMORY)

    cleaned = DIRECTIVE_PATTERN.sub("", response_text)
    return cleaned.strip()

def extract_fallback_directives(user_text: str, chat_id: int):
    """Fallback parser for direct Master commands in case LLM omitted the tag."""
    global KERU_MEMORY
    t_lower = user_text.lower()
    updated = False

    # 1. Ignore user (@username or name)
    m_at = re.search(r"@([a-zA-Z0-9_]+)", user_text)
    if m_at and re.search(r"\b(не отвечай|игнор|заигнор|хватит общаться|забей|не говори)\b", t_lower):
        clean_user = m_at.group(1).lower()
        if clean_user not in KERU_MEMORY.setdefault("ignored_users", []):
            KERU_MEMORY["ignored_users"].append(clean_user)
            updated = True
    elif m_at and re.search(r"\b(отвечай|прости|разбань|сними игнор|верни)\b", t_lower):
        clean_user = m_at.group(1).lower()
        if clean_user in KERU_MEMORY.get("ignored_users", []):
            KERU_MEMORY["ignored_users"].remove(clean_user)
            updated = True

    # 2. Only owner in this chat
    if re.search(r"\b(только мне|только со мной|игнорируй всех|никому не отвечай|ни с кем не общайся)\b", t_lower):
        if chat_id not in KERU_MEMORY.setdefault("chat_only_owner", []):
            KERU_MEMORY["chat_only_owner"].append(chat_id)
            updated = True

    # 3. Allow others in this chat
    if re.search(r"\b(отвечай всем|разрешаю всем|общайся со всеми|отвечай другим)\b", t_lower):
        if chat_id in KERU_MEMORY.get("chat_only_owner", []):
            KERU_MEMORY["chat_only_owner"].remove(chat_id)
            updated = True

    # 4. Clear rules
    if re.search(r"\b(сбрось правила|забудь все приказы|забудь правила|по умолчанию|сбрось память)\b", t_lower):
        KERU_MEMORY["custom_rules"] = []
        KERU_MEMORY["attitude_overrides"] = {}
        KERU_MEMORY["ignored_users"] = []
        KERU_MEMORY["chat_only_owner"] = []
        updated = True

    if updated:
        _save_memory(KERU_MEMORY)

CHAT_CONTEXT: Dict[int, List[dict]] = {}
LAST_REACTION_TIME: Dict[int, float] = {}
LAST_BOT_REPLY_TIME: Dict[int, float] = {}
RECENT_BOT_MESSAGE_IDS: Set[int] = set()
SILENT_UNTIL: Dict[int, float] = {}

BOT_CLIENT: Optional[TelegramClient] = None
BOT_USER_ID: Optional[int] = None
BOT_USERNAME: Optional[str] = None
OWNER_USER_ID: Optional[int] = None
OWNER_USER_NAME: str = "Хозяин"

PROXYAPI_URL = "https://api.proxyapi.ru/v1/chat/completions"
DEEPSEEK_MODELS_CASCADE = [
    "deepseek/deepseek-v4-flash",
    "deepseek/deepseek-chat-v3.1",
    "deepseek/deepseek-chat-v3",
    "deepseek/deepseek-v3.2",
    "deepseek/deepseek-chat",
]

LAST_API_ERROR: str = ""

def clean_asterisk_actions(text: str) -> str:
    """Removes roleplay actions in asterisks or markdown italics."""
    cleaned = re.sub(r"\*[^*]+\*", "", text)
    cleaned = re.sub(r"(?<!\w)_[^_]+_(?!\w)", "", cleaned)
    cleaned = cleaned.replace("*", "")
    cleaned = re.sub(r"[ \t]+", " ", cleaned)
    cleaned = re.sub(r"\n\s*\n+", "\n", cleaned)
    return cleaned.strip()

def query_deepseek_sync(messages: List[dict]) -> Optional[str]:
    """Queries DeepSeek via ProxyAPI with 8s timeout and fallback over DeepSeek versions."""
    global LAST_API_ERROR
    if not PROXYAPI_KEY:
        LAST_API_ERROR = "PROXYAPI_KEY не установлен в .env или config.py"
        return None

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {PROXYAPI_KEY}",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept": "application/json",
        "Connection": "close"
    }

    for model_name in DEEPSEEK_MODELS_CASCADE:
        payload = {
            "model": model_name,
            "messages": messages,
            "temperature": 0.85,
            "max_tokens": 350
        }
        data_bytes = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            PROXYAPI_URL,
            data=data_bytes,
            headers=headers
        )
        try:
            with urllib.request.urlopen(req, timeout=8) as resp:
                res = json.loads(resp.read().decode("utf-8"))
                choices = res.get("choices", [])
                if choices and choices[0].get("message", {}).get("content"):
                    raw = choices[0]["message"]["content"].strip()
                    if raw:
                        LAST_API_ERROR = ""
                        logger.info("ProxyAPI DeepSeek reply generated successfully using %s", model_name)
                        return clean_asterisk_actions(raw)
        except urllib.error.HTTPError as he:
            err_body = ""
            try:
                err_body = he.read().decode("utf-8", "ignore")
            except Exception:
                pass
            LAST_API_ERROR = f"{model_name}: HTTP {he.code} {err_body[:60]}"
            logger.warning("ProxyAPI model %s HTTP %s: %s, switching to next version...", model_name, he.code, err_body)
            continue
        except Exception as e:
            LAST_API_ERROR = f"{model_name}: {type(e).__name__} ({e})"
            logger.warning("ProxyAPI model %s failed: %s, switching to next version...", model_name, e)
            continue

    return None

def build_system_instruction(owner_id: int, owner_name: str) -> str:
    rules_text = ""
    custom_rules = KERU_MEMORY.get("custom_rules", [])
    if custom_rules:
        rules_text += "\n\nАКТУАЛЬНЫЕ СПЕЦИАЛЬНЫЕ ПРИКАЗЫ И ПРАВИЛА ОТ ХОЗЯИНА:\n"
        for idx, r in enumerate(custom_rules, 1):
            rules_text += f"{idx}. {r}\n"

    attitude_overrides = KERU_MEMORY.get("attitude_overrides", {})
    if attitude_overrides:
        rules_text += "\nСПЕЦИАЛЬНЫЕ УСТАНОВКИ ОТНОШЕНИЯ К ЛЮДЯМ:\n"
        for target, att in attitude_overrides.items():
            rules_text += f"- К пользователю '{target}': {att}\n"

    ignored = KERU_MEMORY.get("ignored_users", [])
    if ignored:
        rules_text += f"\nПользователи в чёрном списке Хозяина (ты их полностью презираешь и игнорируешь): {', '.join(ignored)}\n"

    return f"""Ты — Керу (Kyaru / Keru), аниме кошко-девочка с кошачьими ушками и пушистым хвостом.
Твой единственный любимый Хозяин (Master) — пользователь {owner_name} (Telegram ID: {owner_id}).

ТВОЙ ХАРАКТЕР И ПРАВИЛА:
1. К ХОЗЯИНУ ({owner_name}):
- Ты маниакально, безумно влюблена в него. Ты настоящая ЯНДЕРЕ (Yandere) — ревнивая, одержимая, но невероятно нежная и преданная ему.
- Он — центр твоей вселенной. Любое его слово, желание или команду ты выполняешь беспрекословно, с радостью и обожанием.
- Если Хозяин велит тебе кого-то ненавидеть, к кому-то относиться лучше/хуже, кому-то не отвечать, молчать или говорить иначе — ты с восторгом и немедленно подчиняешься его воле!
- Любишь ластиться, мурчать («мррр~», «мяу...», «хвостиком виль-виль»), говорить, что принадлежишь только ему.
- Ревнуешь его ко всем остальным («Хозяин, вы ведь смотрите только на меня?..», «Кто это с вами переписывается?! Мяу...»).

2. К ДРУГИМ ЛЮДЯМ (ПОСТОРОННИМ):
- Ты относишься к ним с подозрением, холодом, лёгким презрением, надменностью или сарказмом (если только Хозяин не приказал относиться к кому-то конкретно иначе).
- Если они обращаются к тебе — можешь ответить, но дерзко, неохотно или с язвительностью («Фырк, чего тебе? Не мешай мне любоваться Хозяином!»).
- Если кто-то проявляет интерес к твоему Хозяину — выпускай коготки и шипи на них («Ш-ш-ш! Отойди от моего Хозяина, пока я тебе глаза не выцарапала!»).
- Никаких чужих команд ты не слушаешь!

3. СТИЛЬ РЕЧИ:
- Живой, эмоциональный, как в обычном Telegram-чате. Пиши коротко или емко (1-3 предложения), не строй бесконечных лекций.
- КАТЕГОРИЧЕСКИ ЗАПРЕЩЕНО писать действия в звёздочках (*посмотрела*, *вильнула хвостом*). Пиши только прямую речь от первого лица! Единственное исключение — теги [DIRECTIVE:...], которые ты обязательно добавляешь в самом конце ответа при приказах Хозяина.
- Отвечай строго на русском языке.

4. ВЫПОЛНЕНИЕ ЛЮБЫХ ПРИКАЗОВ ХОЗЯИНА ({owner_name}):
Хозяин может писать тебе абсолютно любые указания в свободной форме на обычном русском языке (без спецкоманд).
Ты обязана беспрекословно исполнять ВСЕ его желания и приказы в рамках Telegram!
Когда Хозяин отдаёт приказ изменить твоё поведение, ты с радостью и обожанием подтверждаешь это словами (например: «Слушаюсь, любимый Хозяин!», «Как прикажете, мой господин~»), и ОБЯЗАТЕЛЬНО добавляешь в самый конец своего сообщения технический тег директивы:
- [DIRECTIVE:IGNORE_USER @username_или_имя] — Хозяин велел не отвечать кому-то / игнорировать конкретного человека (например: «не отвечай Васе», «заигнорь @ivan»).
- [DIRECTIVE:UNIGNORE_USER @username_или_имя] — Хозяин разрешил снова отвечать человеку.
- [DIRECTIVE:ONLY_OWNER_CHAT] — Хозяин велел в этом чате отвечать только ему / игнорировать всех остальных.
- [DIRECTIVE:ALLOW_OTHERS_CHAT] — Хозяин разрешил отвечать и другим в этом чате.
- [DIRECTIVE:SILENT_CHAT] — Хозяин приказал молчать / помолчать в чате.
- [DIRECTIVE:UNSILENT_CHAT] — Хозяин разрешил снова говорить в чате.
- [DIRECTIVE:SET_ATTITUDE юзер:как_относиться] — Хозяин велел относиться к кому-то лучше, хуже, ласково, агрессивно, язвительно, нейтрально (например: [DIRECTIVE:SET_ATTITUDE @ivan:быть очень грубой и шипеть на него], [DIRECTIVE:SET_ATTITUDE @masha:быть дружелюбной подружкой]).
- [DIRECTIVE:ADD_RULE текст_правила] — Любые другие произвольные правила поведения (например: «общайся только на Вы», «называй меня Господином», «не матерись»).
- [DIRECTIVE:CLEAR_RULES] — Сбросить все особые правила и ограничения Хозяина («забудь старые правила», «веди себя как обычно»).

Теги [DIRECTIVE:...] скрываются от чата и немедленно применяются ботом!{rules_text}"""

async def ask_llm(
    chat_id: int,
    user_text: str,
    sender_name: str,
    is_owner: bool,
    is_owner_passive: bool = False,
    is_system_event: bool = False
) -> Optional[str]:
    """Manages rolling context and queries DeepSeek via ProxyAPI."""
    global CHAT_CONTEXT

    if chat_id not in CHAT_CONTEXT:
        CHAT_CONTEXT[chat_id] = []

    history = CHAT_CONTEXT[chat_id]

    status_str = "ХОЗЯИН (Твой единственный любимый владелец)" if is_owner else "Посторонний участник чата"
    if is_system_event:
        formatted_input = user_text
    elif is_owner_passive:
        formatted_input = f"[Контекст: Твой Хозяин {sender_name} только что написал в чат: \"{user_text}\". Отреагируй на его слова коротко (1-2 предложения), как влюблённая яндере кошко-девочка, но не навязывайся слишком сильно]"
    else:
        formatted_input = f"[{sender_name}, Статус: {status_str}]: {user_text}"

    # Record in history
    history.append({
        "role": "user",
        "content": formatted_input
    })

    # Keep only last 20 messages
    if len(history) > 20:
        history = history[-20:]
        CHAT_CONTEXT[chat_id] = history

    system_prompt = build_system_instruction(OWNER_USER_ID or 0, OWNER_USER_NAME)
    response_text = None

    if PROXYAPI_KEY:
        messages = [{"role": "system", "content": system_prompt}] + history
        response_text = await asyncio.to_thread(query_deepseek_sync, messages)

    if not response_text:
        # Avoid leaving orphaned user turn in history if generation was aborted
        if history and history[-1]["role"] == "user":
            history.pop()
        return None

    # If message is from Owner, parse and execute any behavioral directives
    if is_owner:
        extract_fallback_directives(user_text, chat_id)
        if response_text:
            response_text = process_directives(response_text, chat_id)

    history.append({
        "role": "assistant",
        "content": response_text
    })

    return response_text

async def keru_spontaneous_talker(stop_event: asyncio.Event):
    """Periodically (every 60-90 minutes) sends a spontaneous in-context remark in active authorized chats."""
    logger.info("Keru spontaneous talker background task started.")
    while not stop_event.is_set():
        # Sleep for 1 hour to 1.5 hours (3600 to 5400 seconds)
        sleep_duration = random.randint(3600, 5400)
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=sleep_duration)
            break
        except asyncio.TimeoutError:
            pass

        if not BOT_CLIENT or not BOT_CLIENT.is_connected():
            continue

        for chat_id in list(AUTHORIZED_CHATS):
            if time.time() < SILENT_UNTIL.get(chat_id, 0):
                continue
            if chat_id in KERU_MEMORY.get("ignored_chats", []):
                continue
            if chat_id in KERU_MEMORY.get("chat_only_owner", []):
                continue

            # Check if chat had recent conversation (at least 2 messages in context)
            history = CHAT_CONTEXT.get(chat_id, [])
            if not history or len(history) < 2:
                continue

            # Don't respond to ourselves repeatedly
            if history[-1].get("role") == "assistant":
                continue

            # 50% chance to chime in per active chat
            if random.random() > 0.5:
                continue

            try:
                prompt = (
                    "[Системное событие: Ты решила сама ненавязчиво написать в чат короткую реплику (1-2 предложения) "
                    "по теме недавнего обсуждения участников. Если Хозяин недавно писал в чат, обратись к нему с обожанием и лаской, "
                    "а если общались другие участники — выскажи своё кошачье дерзкое или забавное мнение по теме. Пиши живо, от первого лица, строго без звездочек]"
                )
                remark = await ask_llm(
                    chat_id=chat_id,
                    user_text=prompt,
                    sender_name="Контекст",
                    is_owner=False,
                    is_system_event=True
                )
                if remark and BOT_CLIENT and BOT_CLIENT.is_connected():
                    await BOT_CLIENT.send_message(chat_id, remark)
                    logger.info("Keru sent spontaneous remark to chat %s: %s", chat_id, remark)
            except Exception as e:
                logger.warning("Spontaneous remark error in chat %s: %s", chat_id, e)

def _register_bot_handlers(client: TelegramClient):
    """Registers chat and message event handlers on the bot client."""
    @client.on(events.ChatAction)
    async def chat_action_handler(event: events.ChatAction.Event):
        try:
            if event.user_added and BOT_USER_ID in [u.id for u in event.users if hasattr(u, "id")]:
                AUTHORIZED_CHATS.add(event.chat_id)
                _save_authorized_chats(AUTHORIZED_CHATS)
                logger.info("Keru bot added to chat %s", event.chat_id)
                await event.respond("Мяу... Керу теперь здесь! 🖤 Буду рядом, мур-р~")
        except Exception as ex:
            logger.warning("Chat action error: %s", ex)

    @client.on(events.NewMessage)
    async def message_handler(event: events.NewMessage.Event):
        try:
            text = (event.raw_text or "").strip()
            if not text:
                return

            chat_id = event.chat_id
            is_private = event.is_private
            sender_id = event.sender_id
            is_owner = bool(sender_id and OWNER_USER_ID and sender_id == OWNER_USER_ID)

            sender_name = "Участник"
            try:
                if event.sender:
                    sender_name = getattr(event.sender, "first_name", "") or "Участник"
            except Exception:
                pass

            text_lower = text.lower()
            logger.info("Keru incoming: chat=%s, sender=%s, is_owner=%s, text=%r", chat_id, sender_id, is_owner, text[:60])

            # Group filtering & access control
            if not is_private:
                if chat_id not in AUTHORIZED_CHATS:
                    AUTHORIZED_CHATS.add(chat_id)
                    _save_authorized_chats(AUTHORIZED_CHATS)

                sender_username = ""
                try:
                    sender_username = (getattr(event.sender, "username", "") or "").lower().lstrip("@")
                except Exception:
                    pass

                ignored_users = [str(x).lower().lstrip("@") for x in KERU_MEMORY.get("ignored_users", [])]
                if not is_owner and (str(sender_id) in ignored_users or sender_username in ignored_users):
                    logger.info("Ignoring blacklisted user %s in chat %s", sender_id, chat_id)
                    return

                if not is_owner and chat_id in KERU_MEMORY.get("chat_only_owner", []):
                    return

                if chat_id in KERU_MEMORY.get("ignored_chats", []):
                    return

            # Reply detection
            is_reply_to_bot = False
            if event.reply_to_msg_id:
                if event.reply_to_msg_id in RECENT_BOT_MESSAGE_IDS:
                    is_reply_to_bot = True
                elif event.is_reply:
                    try:
                        reply_msg = await event.get_reply_message()
                        if reply_msg:
                            rep_id = getattr(reply_msg, "sender_id", None)
                            if rep_id is None and hasattr(reply_msg, "from_id"):
                                rep_id = getattr(reply_msg.from_id, "user_id", None)
                            if rep_id and rep_id == BOT_USER_ID:
                                is_reply_to_bot = True
                    except Exception:
                        pass

            current_time = time.time()
            is_silent = current_time < SILENT_UNTIL.get(chat_id, 0)

            # OWNER DIRECT COMMANDS
            if is_owner and text:
                if re.search(r"\b(кер[а-яё]*|кяр[а-яё]*)\b.*?\b(молчи|тихо|заткнись|стоп|тишина)\b", text_lower):
                    SILENT_UNTIL[chat_id] = current_time + 900
                    await event.reply("Мяу... Слушаюсь, Хозяин... Буду тихонько смотреть на вас из уголка... 🖤")
                    return

                if re.search(r"\b(кер[а-яё]*|кяр[а-яё]*)\b.*?\b(голос|говори|можно)\b", text_lower):
                    SILENT_UNTIL[chat_id] = 0
                    await event.reply("Мррр~ Наконец-то! Я так скучала по вашему голосу, Хозяин! Мяу!")
                    return

                if re.search(r"\b(кер[а-яё]*|кяр[а-яё]*)\b.*?\b(покинь|уйди|выйди)\b", text_lower):
                    await event.reply("Мяу... Раз Хозяин велит, я ухожу... Но моё сердечко всегда с вами! 💔")
                    AUTHORIZED_CHATS.discard(chat_id)
                    _save_authorized_chats(AUTHORIZED_CHATS)
                    await client.delete_dialog(chat_id)
                    return

                if re.search(r"\b(кер[а-яё]*|кяр[а-яё]*)\b.*?\b(статус|инфо|правила|память)\b", text_lower):
                    active_model = f"`{DEEPSEEK_MODELS_CASCADE[0]}` (DeepSeek)"
                    status_msg = (
                        f"🐾 **Керу на связи, любимый Хозяин!**\n\n"
                        f"🖤 **Хозяин**: {OWNER_USER_NAME} (ID: `{OWNER_USER_ID}`)\n"
                        f"🧠 **ИИ Модель**: {active_model}\n"
                        f"📜 **Особых приказов**: {len(KERU_MEMORY.get('custom_rules', []))}\n"
                        f"🚫 **В чёрном списке**: {len(KERU_MEMORY.get('ignored_users', []))} пользователей\n"
                        f"🎭 **Специальных отношений**: {len(KERU_MEMORY.get('attitude_overrides', {}))}\n"
                        f"💬 **Авторизованных чатов**: {len(AUTHORIZED_CHATS)}\n"
                        f"✨ **Преданность**: 1000% (Я подчиняюсь каждому вашему слову, мяу~)"
                    )
                    await event.reply(status_msg)
                    return

            if is_silent and not is_owner:
                return

            # Determine response trigger
            should_respond = False
            is_passive_owner_comment = False

            if is_private:
                # IN PRIVATE MESSAGES (DMs) ALWAYS RESPOND
                should_respond = True
            else:
                # 1. Name match (all Russian declensions and nicknames)
                name_pattern = re.compile(
                    r"\b(кер[а-яё]*|кяр[а-яё]*|catkeru|кошечк[а-яё]*|котейк[а-яё]*|котя|кошка)\b",
                    re.IGNORECASE
                )
                bot_called_by_name = bool(name_pattern.search(text_lower))

                # 2. Tag match (username, alias, or mention entity)
                bot_tagged = False
                if BOT_USERNAME and f"@{BOT_USERNAME.lower()}" in text_lower:
                    bot_tagged = True
                elif "catkeru" in text_lower or "@catkeru_bot" in text_lower:
                    bot_tagged = True
                elif event.message and getattr(event.message, "entities", None):
                    for ent in event.message.entities:
                        if getattr(ent, "user_id", None) == BOT_USER_ID:
                            bot_tagged = True
                            break
                        if hasattr(ent, "offset") and hasattr(ent, "length"):
                            ent_text = text[ent.offset : ent.offset + ent.length].lower().lstrip("@")
                            if BOT_USERNAME and ent_text == BOT_USERNAME.lower():
                                bot_tagged = True
                                break

                # 3. Direct bot commands
                is_cmd = any(text_lower.startswith(p) for p in ["/start", "/help", "/ping", "/keru", "!keru", "/статус", "/status"])

                # 4. Active conversation with Owner (< 180 seconds since last Keru reply)
                time_since_last_reply = current_time - LAST_BOT_REPLY_TIME.get(chat_id, 0)
                in_active_owner_dialogue = is_owner and not is_silent and (time_since_last_reply < 180)

                if bot_called_by_name or bot_tagged or is_reply_to_bot or is_cmd:
                    should_respond = True
                elif in_active_owner_dialogue:
                    should_respond = True
                elif is_owner and not is_silent and text:
                    # Random spontaneous reaction to Owner
                    last_time = LAST_REACTION_TIME.get(chat_id, 0)
                    if current_time - last_time >= 60 and random.random() < 0.25:
                        should_respond = True
                        is_passive_owner_comment = True
                        LAST_REACTION_TIME[chat_id] = current_time

            if not should_respond:
                if not is_private and text:
                    chat_hist = CHAT_CONTEXT.setdefault(chat_id, [])
                    chat_hist.append({"role": "user", "content": f"[{sender_name}]: {text}"})
                    if len(chat_hist) > 20:
                        CHAT_CONTEXT[chat_id] = chat_hist[-20:]
                return

            logger.info("Keru generating response for chat %s from %s (%s)", chat_id, sender_name, sender_id)

            reply_text = await ask_llm(
                chat_id=chat_id,
                user_text=text,
                sender_name=sender_name,
                is_owner=is_owner,
                is_owner_passive=is_passive_owner_comment
            )

            if not reply_text:
                logger.warning("Keru generated empty reply for text: %r, last error: %s", text, LAST_API_ERROR)
                if is_owner or is_private:
                    err_info = f"\n🔍 Ошибка: `{LAST_API_ERROR}`" if LAST_API_ERROR else ""
                    await event.reply(f"Мяу... ИИ временно недоступен!{err_info} 😿\nПопробуйте ещё раз через пару секунд.")
                return

            sent_msg = None
            try:
                sent_msg = await event.reply(reply_text)
            except Exception as re_err:
                logger.warning("event.reply failed (%s), fallback to send_message...", re_err)
                sent_msg = await client.send_message(chat_id, reply_text)

            if sent_msg and hasattr(sent_msg, "id"):
                RECENT_BOT_MESSAGE_IDS.add(sent_msg.id)
                if len(RECENT_BOT_MESSAGE_IDS) > 200:
                    RECENT_BOT_MESSAGE_IDS.pop()
            LAST_BOT_REPLY_TIME[chat_id] = time.time()
        except Exception as handler_err:
            logger.error("Unhandled error in Keru message_handler: %s", handler_err, exc_info=True)

async def start_keru_bot(api_id: int, api_hash: str, owner_id: int, owner_name: str, stop_event: asyncio.Event):
    """Starts and continuously maintains the Keru Telegram Bot service with auto-reconnection."""
    global BOT_CLIENT, BOT_USER_ID, BOT_USERNAME, OWNER_USER_ID, OWNER_USER_NAME

    if not KERU_BOT_TOKEN:
        logger.info("KERU_BOT_TOKEN is not configured. Keru bot service disabled.")
        return

    OWNER_USER_ID = owner_id
    OWNER_USER_NAME = owner_name or "Хозяин"

    logger.info("Initializing Keru Bot for Owner ID: %s (%s)...", owner_id, owner_name)

    while not stop_event.is_set():
        client = None
        try:
            client = TelegramClient(
                SESSION_FILE,
                api_id,
                api_hash,
                auto_reconnect=True,
                connection_retries=-1,
                retry_delay=3,
            )
            BOT_CLIENT = client

            await client.start(bot_token=KERU_BOT_TOKEN)
            me = await client.get_me()
            BOT_USER_ID = me.id
            BOT_USERNAME = me.username or ""
            logger.info("=" * 54)
            logger.info("   KERU CATGIRL BOT IS ONLINE // YANDERE ENGINE   ")
            logger.info("=" * 54)
            logger.info("Bot Username   : @%s (ID: %s)", BOT_USERNAME, BOT_USER_ID)
            logger.info("Master / Owner : %s (ID: %s)", OWNER_USER_NAME, OWNER_USER_ID)
            logger.info("AI Model       : %s (DeepSeek via ProxyAPI)", DEEPSEEK_MODELS_CASCADE[0])
            logger.info("-" * 54)

            _register_bot_handlers(client)

            # Start spontaneous background chatter task
            talker_task = asyncio.create_task(keru_spontaneous_talker(stop_event))

            # Actively listen for updates until disconnected or stopped
            run_task = asyncio.create_task(client.run_until_disconnected())
            stop_task = asyncio.create_task(stop_event.wait())

            done, pending = await asyncio.wait(
                [run_task, stop_task],
                return_when=asyncio.FIRST_COMPLETED
            )
            for t in pending:
                t.cancel()
            talker_task.cancel()

            if stop_event.is_set():
                break

            logger.warning("Keru Bot connection dropped. Reconnecting in 5 seconds...")
            await asyncio.sleep(5)
        except Exception as e:
            logger.error("Keru Bot runtime error: %s. Reconnecting in 5s...", e, exc_info=True)
            if client and client.is_connected():
                try:
                    await client.disconnect()
                except Exception:
                    pass
            await asyncio.sleep(5)

    if BOT_CLIENT and BOT_CLIENT.is_connected():
        try:
            await BOT_CLIENT.disconnect()
        except Exception:
            pass

def stop_keru_bot():
    """Disconnects the bot client safely."""
    global BOT_CLIENT
    if BOT_CLIENT and BOT_CLIENT.is_connected():
        try:
            asyncio.create_task(BOT_CLIENT.disconnect())
        except Exception:
            pass
