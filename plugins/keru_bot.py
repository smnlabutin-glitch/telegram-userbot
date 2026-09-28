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
SILENT_UNTIL: Dict[int, float] = {}

BOT_CLIENT: Optional[TelegramClient] = None
BOT_USER_ID: Optional[int] = None
BOT_USERNAME: Optional[str] = None
OWNER_USER_ID: Optional[int] = None
OWNER_USER_NAME: str = "Хозяин"

PROXYAPI_URL = "https://api.proxyapi.ru/v1/chat/completions"
DEEPSEEK_MODELS_CASCADE = [
    "deepseek/deepseek-chat-v3",
    "deepseek/deepseek-chat-v3.1",
    "deepseek/deepseek-v3.2",
    "gpt-4o-mini",
]
GPT_VISION_MODELS_CASCADE = [
    "gpt-4o-mini",
    "gpt-4o",
]

def clean_asterisk_actions(text: str) -> str:
    """Removes roleplay actions in asterisks or markdown italics."""
    cleaned = re.sub(r"\*[^*]+\*", "", text)
    cleaned = re.sub(r"(?<!\w)_[^_]+_(?!\w)", "", cleaned)
    cleaned = cleaned.replace("*", "")
    cleaned = re.sub(r"[ \t]+", " ", cleaned)
    cleaned = re.sub(r"\n\s*\n+", "\n", cleaned)
    return cleaned.strip()

def prepare_image_for_llm(raw_bytes: bytes) -> tuple[str, str]:
    """Optimizes image dimensions with PIL if large, returns (base64_str, mime_type)."""
    try:
        from PIL import Image
        img = Image.open(io.BytesIO(raw_bytes))
        max_dim = 1024
        if max(img.size) > max_dim:
            img.thumbnail((max_dim, max_dim), Image.Resampling.LANCZOS)
        out = io.BytesIO()
        if img.mode in ("RGBA", "P"):
            img = img.convert("RGB")
        img.save(out, format="JPEG", quality=85)
        b64 = base64.b64encode(out.getvalue()).decode("utf-8")
        return b64, "image/jpeg"
    except Exception as e:
        logger.warning("Error optimizing image with PIL: %s, using raw bytes", e)
        b64 = base64.b64encode(raw_bytes).decode("utf-8")
        return b64, "image/jpeg"

def query_deepseek_sync(messages: List[dict]) -> Optional[str]:
    """Queries DeepSeek via ProxyAPI with cascade across active models and gpt-4o-mini fallback."""
    if not PROXYAPI_KEY:
        return None

    for model_name in DEEPSEEK_MODELS_CASCADE:
        for attempt in range(2):
            payload = {
                "model": model_name,
                "messages": messages,
                "temperature": 0.88,
                "max_tokens": 800
            }
            data_bytes = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(
                PROXYAPI_URL,
                data=data_bytes,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {PROXYAPI_KEY}"
                }
            )
            try:
                with urllib.request.urlopen(req, timeout=18) as resp:
                    res = json.loads(resp.read().decode("utf-8"))
                    choices = res.get("choices", [])
                    if choices and choices[0].get("message", {}).get("content"):
                        raw = choices[0]["message"]["content"].strip()
                        if raw:
                            logger.info("ProxyAPI text reply generated successfully using %s", model_name)
                            return clean_asterisk_actions(raw)
            except urllib.error.HTTPError as he:
                err_body = ""
                try:
                    err_body = he.read().decode("utf-8", "ignore")
                except Exception:
                    pass
                logger.warning("ProxyAPI model %s HTTP %s (attempt %d/2): %s", model_name, he.code, attempt + 1, err_body)
                if he.code == 429 and attempt == 0:
                    time.sleep(1.2)
                    continue
                break
            except Exception as e:
                logger.warning("ProxyAPI model %s failed (attempt %d/2): %s", model_name, attempt + 1, e)
                if attempt == 0:
                    time.sleep(1.0)
                    continue
                break

    return None

def query_gpt_mini_sync(messages: List[dict]) -> Optional[str]:
    """Queries GPT-4o-mini via ProxyAPI for vision tasks when an image is sent."""
    if not PROXYAPI_KEY:
        return None

    for model_name in GPT_VISION_MODELS_CASCADE:
        for attempt in range(2):
            payload = {
                "model": model_name,
                "messages": messages,
                "temperature": 0.88,
                "max_tokens": 800
            }
            data_bytes = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(
                PROXYAPI_URL,
                data=data_bytes,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {PROXYAPI_KEY}"
                }
            )
            try:
                with urllib.request.urlopen(req, timeout=25) as resp:
                    res = json.loads(resp.read().decode("utf-8"))
                    choices = res.get("choices", [])
                    if choices and choices[0].get("message", {}).get("content"):
                        raw = choices[0]["message"]["content"].strip()
                        if raw:
                            logger.info("ProxyAPI vision reply generated successfully using %s", model_name)
                            return clean_asterisk_actions(raw)
            except urllib.error.HTTPError as he:
                err_body = ""
                try:
                    err_body = he.read().decode("utf-8", "ignore")
                except Exception:
                    pass
                logger.warning("ProxyAPI vision model %s HTTP %s (attempt %d/2): %s", model_name, he.code, attempt + 1, err_body)
                if he.code == 429 and attempt == 0:
                    time.sleep(1.2)
                    continue
                break
            except Exception as e:
                logger.warning("ProxyAPI vision model %s error (attempt %d/2): %s", model_name, attempt + 1, e)
                if attempt == 0:
                    time.sleep(1.0)
                    continue
                break

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
    image_bytes: Optional[bytes] = None,
    is_system_event: bool = False
) -> Optional[str]:
    """Manages rolling context and queries DeepSeek (text) or GPT-4o-mini (images) via ProxyAPI."""
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

    # Record in history (compact text summary to save memory and tokens on later turns)
    history_entry = formatted_input if not image_bytes else f"{formatted_input} [Пользователь прикрепил изображение]"
    history.append({
        "role": "user",
        "content": history_entry
    })

    # Keep only last 20 messages
    if len(history) > 20:
        history = history[-20:]
        CHAT_CONTEXT[chat_id] = history

    system_prompt = build_system_instruction(OWNER_USER_ID or 0, OWNER_USER_NAME)
    response_text = None

    # 1. Vision Route: If an image is provided, query GPT-4o-mini via ProxyAPI
    if image_bytes and PROXYAPI_KEY:
        try:
            b64_str, mime_type = prepare_image_for_llm(image_bytes)
            gpt_messages = [{"role": "system", "content": system_prompt}]
            # Append prior textual turns from history
            for m in history[:-1]:
                gpt_messages.append({"role": m["role"], "content": m["content"]})
            # Current multimodal message with image and text
            gpt_messages.append({
                "role": "user",
                "content": [
                    {"type": "text", "text": formatted_input},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:{mime_type};base64,{b64_str}"}
                    }
                ]
            })
            logger.info("Routing user image to GPT-4o-mini via ProxyAPI...")
            response_text = await asyncio.to_thread(query_gpt_mini_sync, gpt_messages)
        except Exception as e:
            logger.warning("Error preparing image or querying GPT-4o-mini: %s", e)

    # 2. Text Route: Query DeepSeek via ProxyAPI
    if not response_text and PROXYAPI_KEY and not image_bytes:
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
        logger.info("AI Models      : %s (Text) + %s (Vision)", DEEPSEEK_MODELS_CASCADE[0], GPT_VISION_MODELS_CASCADE[0])
        logger.info("-" * 54)
    except Exception as e:
        logger.error("Failed to authenticate Keru bot with token: %s", e)
        return

    # 1. GROUP MEMBERSHIP & ACCESS CONTROL
    @client.on(events.ChatAction)
    async def chat_action_handler(event: events.ChatAction.Event):
        # Check if this bot was added
        if event.user_added and BOT_USER_ID in [u.id for u in event.users if hasattr(u, "id")]:
            AUTHORIZED_CHATS.add(event.chat_id)
            _save_authorized_chats(AUTHORIZED_CHATS)
            logger.info("Keru bot added to chat %s", event.chat_id)
            try:
                await event.respond("Мяу... Керу теперь здесь! 🖤 Буду рядом, мур-р~")
            except Exception as ex:
                logger.warning("Error greeting chat: %s", ex)

    # 2. MESSAGE HANDLER (DMs, MENTIONS, OWNER REACTIONS, PHOTO REPLIES)
    @client.on(events.NewMessage)
    async def message_handler(event: events.NewMessage.Event):
        has_text = bool(event.raw_text and event.raw_text.strip())
        is_photo = bool(event.photo or (event.document and getattr(event.document, "mime_type", "").startswith("image/")))

        if not has_text and not is_photo:
            return

        chat_id = event.chat_id
        is_private = event.is_private
        sender = await event.get_sender()
        sender_id = event.sender_id
        is_owner = (sender_id == OWNER_USER_ID)
        sender_name = getattr(sender, "first_name", "Участник") or "Участник"
        text = (event.raw_text or "").strip()
        text_lower = text.lower()

        # 1. STRICT PRIVATE MESSAGES POLICY:
        # In DMs, Keru ONLY speaks to Owner. Completely ignore everyone else!
        if is_private and not is_owner:
            return

        # Auto-authorize group chats where bot is present
        if not is_private and chat_id not in AUTHORIZED_CHATS:
            AUTHORIZED_CHATS.add(chat_id)
            _save_authorized_chats(AUTHORIZED_CHATS)

        # 2. CHECK MASTER'S BEHAVIOR RESTRICTIONS & BLACKLIST
        sender_username = (getattr(sender, "username", "") or "").lower().lstrip("@")
        sender_first_name = (getattr(sender, "first_name", "") or "").lower()
        ignored_users = [str(x).lower().lstrip("@") for x in KERU_MEMORY.get("ignored_users", [])]
        if not is_owner and (str(sender_id) in ignored_users or sender_username in ignored_users or sender_first_name in ignored_users):
            logger.info("Keru ignoring message from user %s (%s) by Master's order", sender_id, sender_username)
            return

        if not is_owner and chat_id in KERU_MEMORY.get("chat_only_owner", []):
            return

        if chat_id in KERU_MEMORY.get("ignored_chats", []):
            return

        # Check reply info
        is_reply_to_bot = False
        reply_msg = None
        reply_has_photo = False
        if event.is_reply:
            reply_msg = await event.get_reply_message()
            if reply_msg:
                if reply_msg.sender_id == BOT_USER_ID:
                    is_reply_to_bot = True
                if reply_msg.photo or (reply_msg.document and getattr(reply_msg.document, "mime_type", "").startswith("image/")):
                    reply_has_photo = True

        # Check silence mode in groups
        current_time = time.time()
        is_silent = current_time < SILENT_UNTIL.get(chat_id, 0)

        # OWNER DIRECT CONTROL COMMANDS
        if is_owner and text:
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

            if re.search(r"\b(керу|кяру)\b.*?\b(статус|инфо|правила|память)\b", text_lower):
                active_model = f"`{DEEPSEEK_MODELS_CASCADE[0]}` (текст) + `{GPT_VISION_MODELS_CASCADE[0]}` (картинки)"
                rules_count = len(KERU_MEMORY.get("custom_rules", []))
                ignored_count = len(KERU_MEMORY.get("ignored_users", []))
                attitudes_count = len(KERU_MEMORY.get("attitude_overrides", {}))
                status_msg = (
                    f"🐾 **Керу на связи, любимый Хозяин!**\n\n"
                    f"🖤 **Хозяин**: {OWNER_USER_NAME} (ID: `{OWNER_USER_ID}`)\n"
                    f"🧠 **ИИ Модели**: {active_model}\n"
                    f"📜 **Особых приказов**: {rules_count}\n"
                    f"🚫 **В чёрном списке**: {ignored_count} пользователей\n"
                    f"🎭 **Специальных отношений**: {attitudes_count}\n"
                    f"💬 **Авторизованных чатов**: {len(AUTHORIZED_CHATS)}\n"
                    f"✨ **Преданность**: 1000% (Я подчиняюсь каждому вашему слову, мяу~)"
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
            should_respond = True
        else:
            names = ["керу", "кяру", "кошечка", "кошкодевочка", "котейка", "котя", "catkeru"]
            bot_mentioned = (
                (BOT_USERNAME and f"@{BOT_USERNAME.lower()}" in text_lower)
                or any(name in text_lower for name in names)
            )
            is_cmd = any(text_lower.startswith(p) for p in ["/start", "/help", "/ping", "/keru", "!keru", "/статус", "/status"])

            if bot_mentioned or is_reply_to_bot or is_cmd:
                should_respond = True
            elif is_owner and not is_silent and text:
                # Owner spoke in group without mentioning Keru
                # Subtle reaction probability (20%) with at least 60s cooldown
                last_time = LAST_REACTION_TIME.get(chat_id, 0)
                if current_time - last_time >= 60 and random.random() < 0.22:
                    should_respond = True
                    is_passive_owner_comment = True
                    LAST_REACTION_TIME[chat_id] = current_time

        if not should_respond:
            # Save message to rolling chat context so Keru stays context-aware
            if not is_private and has_text:
                chat_hist = CHAT_CONTEXT.setdefault(chat_id, [])
                chat_hist.append({
                    "role": "user",
                    "content": f"[{sender_name}]: {text}"
                })
                if len(chat_hist) > 20:
                    CHAT_CONTEXT[chat_id] = chat_hist[-20:]
            return

        logger.info("Keru reacting to message in chat %s from %s (%s): %r", chat_id, sender_name, sender_id, text[:60])

        # Download image if this message has a photo or user replied with/to a photo
        image_bytes = None
        if is_photo:
            try:
                image_bytes = await event.download_media(file=bytes)
            except Exception as e:
                logger.warning("Failed to download image from message: %s", e)
        elif reply_has_photo and reply_msg and (is_reply_to_bot or bot_mentioned):
            try:
                image_bytes = await reply_msg.download_media(file=bytes)
            except Exception as e:
                logger.warning("Failed to download image from replied message: %s", e)

        user_text = text if text else ("Посмотри на эту картинку, что скажешь?" if image_bytes else "")
        if not user_text and not image_bytes:
            return

        # Generate response via DeepSeek (text) or GPT-4o-mini (image)
        try:
            reply_text = await ask_llm(
                chat_id=chat_id,
                user_text=user_text,
                sender_name=sender_name,
                is_owner=is_owner,
                is_owner_passive=is_passive_owner_comment,
                image_bytes=image_bytes
            )

            # If quota is exhausted or generation returned None, notify owner or log
            if not reply_text:
                logger.warning("Keru generated empty reply for text: %r", user_text)
                if is_owner:
                    await event.reply("Мяу... Хозяин, ИИ API временно недоступен или вернул пустой ответ! Проверьте баланс ProxyAPI 😿")
                return

            try:
                await event.reply(reply_text)
            except Exception as re_err:
                logger.warning("event.reply failed (%s), fallback to send_message...", re_err)
                await client.send_message(chat_id, reply_text)
        except Exception as e:
            logger.error("Error generating or sending Keru response: %s", e)

    # Start spontaneous talker background task
    talker_task = asyncio.create_task(keru_spontaneous_talker(stop_event))

    # Keep running until stop_event is set
    try:
        await stop_event.wait()
    finally:
        logger.info("Disconnecting Keru bot gracefully...")
        talker_task.cancel()
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
