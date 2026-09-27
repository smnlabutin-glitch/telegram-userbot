import io
import time
import asyncio
import difflib
import logging
import re
from typing import Dict, Optional
import urllib.request

from telethon import TelegramClient, events
from card_engine import render_card
from plugins import get_plugin_config
from plugins.anime_database import get_random_anime

logger = logging.getLogger("userbot.plugins.anime_quiz")

class QuizSession:
    def __init__(self, chat_id: int, anime: dict, game_msg_id: int, client: TelegramClient):
        self.chat_id = chat_id
        self.anime = anime
        self.game_msg_id = game_msg_id
        self.client = client
        self.start_time = time.time()
        self.lock = asyncio.Lock()
        self.is_active = True
        self.timeout_task: Optional[asyncio.Task] = None

# Active game sessions per chat_id
ACTIVE_QUIZZES: Dict[int, QuizSession] = {}

def normalize_text(text: str) -> str:
    """Cleans up text for robust fuzzy matching."""
    text = text.lower().replace("ё", "е")
    # Remove special punctuation and symbols, retain letters, digits and spaces
    text = re.sub(r"[^\w\s]", "", text)
    return " ".join(text.split())

def check_answer(user_input: str, anime_data: dict, threshold: float = 0.80) -> bool:
    """
    Evaluates whether user input matches any canonical or alias answers.
    Supports exact, substring, and Levenshtein/difflib similarity >= 80%.
    """
    norm_user = normalize_text(user_input)
    if not norm_user:
        return False

    for alias in anime_data.get("answers", []):
        norm_alias = normalize_text(alias)
        if not norm_alias:
            continue

        # Exact match
        if norm_user == norm_alias:
            return True

        # Substring match if input is long enough
        if len(norm_alias) >= 4 and norm_user in norm_alias and len(norm_user) >= len(norm_alias) * 0.75:
            return True
        if len(norm_user) >= 4 and norm_alias in norm_user and len(norm_alias) >= len(norm_user) * 0.75:
            return True

        # Fuzzy sequence matcher ratio
        ratio = difflib.SequenceMatcher(None, norm_user, norm_alias).ratio()
        if ratio >= threshold:
            return True

    return False

def _fetch_image(url: str, timeout: int = 5) -> Optional[bytes]:
    """Downloads remote image into bytes with user-agent."""
    try:
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            if resp.status == 200:
                return resp.read()
    except Exception as e:
        logger.warning("Failed to download anime cover from %s: %s", url, e)
    return None

async def download_cover_bytes(url: str) -> Optional[bytes]:
    return await asyncio.to_thread(_fetch_image, url)

async def run_quiz_timeout(session: QuizSession, duration: int = 45):
    """Waits for round expiration and announces timeout if unanswered."""
    try:
        await asyncio.sleep(duration)
        async with session.lock:
            if not session.is_active:
                return
            session.is_active = False
            ACTIVE_QUIZZES.pop(session.chat_id, None)

        # Render timeout announcement card
        card_img = render_card(
            title="ВРЕМЯ ВЫШЛО!",
            subtitle="Никто не успел назвать правильный тайтл",
            badge_text="ТАЙМАУТ",
            badge_type="warn",
            stats=[
                ("ТАЙТЛ", session.anime["canonical"][:25]),
                ("РЕЛИЗ", session.anime["year"]),
                ("СТАТУС", "Раунд окончен"),
            ],
            meta_left="ANIME QUIZ ENGINE // TIMEOUT 45S",
            meta_right="ROUND EXPIRED",
            category="ROUND TIMEOUT // ANIME TRIVIA",
        )

        timeout_text = (
            f"⌛ **Время вышло!** Никто не смог отгадать аниме за 45 секунд.\n\n"
            f"🎬 **Правильный ответ**: `{session.anime['canonical']}`\n"
            f"📖 **Оригинальное название**: {session.anime['title']}\n"
            f"🎭 **Жанры**: {session.anime['genres']}\n\n"
            f"💡 Чтобы начать новый раунд, отправьте `.animequiz`"
        )

        await session.client.send_file(session.chat_id, file=card_img, caption=timeout_text)

    except asyncio.CancelledError:
        pass
    except Exception as e:
        logger.error("Error in quiz timeout handler: %s", e)

def register_anime_quiz(client: TelegramClient, prefix: str):
    """Registers anime quiz game command and real-time answer listener."""

    # Trigger: .animequiz or .guess [stop]
    @client.on(events.NewMessage(outgoing=True, pattern=rf"^{prefix}(?:animequiz|guess)(?:\s+(stop))?$"))
    async def anime_quiz_command(event: events.NewMessage.Event):
        subcommand = event.pattern_match.group(1)
        chat_id = event.chat_id

        # Check plugin enabled status
        config = get_plugin_config("anime_quiz")
        if not config.get("enabled", True):
            await event.edit(f"⚠️ Плагин аниме-викторины выключен.\nВключите его командой: `{prefix}plugin quiz on`")
            return

        # Check if user requested stop
        if subcommand and subcommand.lower() == "stop":
            session = ACTIVE_QUIZZES.pop(chat_id, None)
            if session:
                async with session.lock:
                    session.is_active = False
                    if session.timeout_task and not session.timeout_task.done():
                        session.timeout_task.cancel()
                await event.edit("🛑 **Раунд аниме-викторины был принудительно остановлен.**")
            else:
                await event.edit("ℹ️ В этом чате сейчас нет активного раунда викторины.")
            return

        # Check if already running in this chat
        if chat_id in ACTIVE_QUIZZES and ACTIVE_QUIZZES[chat_id].is_active:
            await event.edit(
                f"⚠️ В этом чате уже идет раунд!\n"
                f"Отправьте `{prefix}animequiz stop`, если хотите остановить его."
            )
            return

        # Phase 1: Animated preparation preview
        anim_frames = [
            "╭───「 ✦ АНИМЕ ВИКТОРИНА ✦ 」\n│  ⏳ Инициализация раунда...\n│  [■□□□□□□□] 15%\n╰───────────────────────",
            "╭───「 ✦ АНИМЕ ВИКТОРИНА ✦ 」\n│  🎲 Выбор тайтла из базы...\n│  [■■■■□□□□] 50%\n╰───────────────────────",
            "╭───「 ✦ АНИМЕ ВИКТОРИНА ✦ 」\n│  🖼 Загрузка кадра / обложки...\n│  [■■■■■■■■] 100%\n╰───────────────────────",
        ]

        for frame in anim_frames:
            try:
                await event.edit(frame)
                await asyncio.sleep(0.35)
            except Exception:
                pass

        # Select anime & download image
        anime = get_random_anime()
        img_bytes = await download_cover_bytes(anime["image_url"])

        # Phase 2: Send game card with timer & masked hint
        caption = (
            f"╭───「 ✦ УГАДАЙ АНИМЕ ПО КАДРУ ✦ 」\n"
            f"│\n"
            f"│ 🎭 **Жанры**: {anime['genres']}\n"
            f"│ 📅 **Релиз**: {anime['year']} ({anime['season']})\n"
            f"│ 💡 **Подсказка**: `{anime['masked_hint']}`\n"
            f"│\n"
            f"│ ⏱ **Время**: 45 секунд\n"
            f"│ 💬 Пишите название прямо в чат!\n"
            f"╰────────────────────────────────"
        )

        try:
            await event.delete()
        except Exception:
            pass

        if img_bytes:
            photo_file = io.BytesIO(img_bytes)
            photo_file.name = "anime_quiz.jpg"
            game_msg = await client.send_file(chat_id, file=photo_file, caption=caption)
        else:
            # Fallback to render_card if CDN image failed to fetch
            fallback_card = render_card(
                title="Угадай аниме по подсказке",
                subtitle=f"{anime['genres']} • {anime['year']}",
                badge_text="ВИКТОРИНА",
                badge_type="info",
                stats=[
                    ("ПОДСКАЗКА", anime["masked_hint"][:25]),
                    ("РЕЛИЗ", anime["year"]),
                    ("ТАЙМЕР", "45 сек"),
                ],
                category="ANIME QUIZ MINI-GAME",
            )
            game_msg = await client.send_file(chat_id, file=fallback_card, caption=caption)

        # Initialize session & start 45s countdown timer
        session = QuizSession(
            chat_id=chat_id,
            anime=anime,
            game_msg_id=game_msg.id if game_msg else 0,
            client=client,
        )
        session.timeout_task = asyncio.create_task(run_quiz_timeout(session, duration=45))
        ACTIVE_QUIZZES[chat_id] = session
        logger.info("Started anime quiz in chat %s for title '%s'", chat_id, anime["canonical"])

    # Phase 3: Answer listener for incoming chat messages
    @client.on(events.NewMessage)
    async def anime_quiz_answer_listener(event: events.NewMessage.Event):
        chat_id = event.chat_id
        if chat_id not in ACTIVE_QUIZZES:
            return

        session = ACTIVE_QUIZZES.get(chat_id)
        if not session or not session.is_active:
            return

        user_text = event.raw_text.strip() if event.raw_text else ""
        if not user_text or user_text.startswith(prefix):
            return

        # Check fuzzy matching against answer pool
        if not check_answer(user_text, session.anime):
            return

        # Phase 4: Atomic lock check to guarantee exactly one winner
        async with session.lock:
            if not session.is_active:
                return
            session.is_active = False
            ACTIVE_QUIZZES.pop(chat_id, None)
            if session.timeout_task and not session.timeout_task.done():
                session.timeout_task.cancel()

        # Calculate exact elapsed reaction time
        elapsed = round(time.time() - session.start_time, 2)

        # Winner sender details
        try:
            sender = await event.get_sender()
            if sender:
                if getattr(sender, "username", None):
                    winner_name = f"@{sender.username}"
                else:
                    first = getattr(sender, "first_name", "") or ""
                    last = getattr(sender, "last_name", "") or ""
                    winner_name = f"{first} {last}".strip() or "Участник"
            else:
                winner_name = "Участник"
        except Exception:
            winner_name = "Участник"

        # Generate victory card
        card_img = render_card(
            title="ПРАВИЛЬНЫЙ ОТВЕТ!",
            subtitle=f"Аниме отгадано всего за {elapsed:.2f} сек.!",
            badge_text="ПОБЕДА",
            badge_type="success",
            stats=[
                ("ПОБЕДИТЕЛЬ", winner_name[:20]),
                ("ВРЕМЯ", f"{elapsed:.2f}s"),
                ("ТАЙТЛ", session.anime["canonical"][:25]),
            ],
            meta_left="ANIME QUIZ ENGINE // ROUND CLEARED",
            meta_right=f"TIME: {elapsed:.2f}s",
            category="VICTORY // ANIME TRIVIA",
        )

        victory_text = (
            f"🎉 **Браво, {winner_name}!** Ты угадал аниме!\n\n"
            f"🎬 **Тайтл**: `{session.anime['canonical']}`\n"
            f"📖 **Оригинал**: {session.anime['title']}\n"
            f"⚡ **Время реакции**: `{elapsed:.2f}` сек.\n\n"
            f"💡 Чтобы запустить следующий раунд, отправьте `.animequiz`"
        )

        try:
            await event.reply(file=card_img, message=victory_text)
        except Exception as e:
            logger.error("Failed to send victory response: %s", e)
