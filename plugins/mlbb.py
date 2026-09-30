import io
import os
import json
import time
import asyncio
import logging
import urllib.request
import urllib.error
from typing import Dict, Tuple, Optional, List
from telethon import TelegramClient, events

from card_engine import render_card, render_mlbb_card
from plugins import get_plugin_config, update_plugin_config

logger = logging.getLogger("userbot.plugins.mlbb")

API_BASE_URL = os.getenv("MLBB_API_BASE_URL", "https://mlbb-stats.ru/api").rstrip("/")
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"

# In-memory session tracking for two-step authentication: sender_id -> (role_id, zone_id, timestamp)
PENDING_AUTH: Dict[int, Tuple[int, int, float]] = {}

# Simple TTL cache for player profiles and avatars (roleId-zoneId -> (data, timestamp))
PROFILE_CACHE: Dict[str, Tuple[dict, float]] = {}
AVATAR_CACHE: Dict[str, Tuple[bytes, float]] = {}
CACHE_TTL = 300  # 5 minutes


def _http_get(url: str, timeout: int = 10) -> Tuple[int, bytes]:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, resp.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()
    except Exception as e:
        logger.debug("HTTP GET error for %s: %s", url, e)
        return 0, b""


def _http_post_json(url: str, payload: dict, timeout: int = 15) -> Tuple[int, bytes]:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={"User-Agent": USER_AGENT, "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, resp.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()
    except Exception as e:
        logger.debug("HTTP POST error for %s: %s", url, e)
        return 0, b""


async def fetch_player_profile(role_id: int, zone_id: int) -> Tuple[Optional[dict], Optional[str]]:
    """Fetches player dossier from MLBB telemetry API."""
    cache_key = f"{role_id}-{zone_id}"
    now = time.time()
    if cache_key in PROFILE_CACHE:
        data, ts = PROFILE_CACHE[cache_key]
        if now - ts < CACHE_TTL:
            return data, None

    url = f"{API_BASE_URL}/profile/{role_id}-{zone_id}"
    try:
        status, body = await asyncio.to_thread(_http_get, url, 12)
        if status == 200:
            json_data = json.loads(body.decode("utf-8", "ignore"))
            profile = json_data.get("profile")
            if profile:
                PROFILE_CACHE[cache_key] = (profile, now)
                return profile, None
            return None, "Пустые данные профиля"
        elif status == 404:
            return None, "Игрок не найден в базе данных"
        else:
            return None, f"HTTP {status}"
    except Exception as e:
        logger.error("Error fetching MLBB profile %s-%s: %s", role_id, zone_id, e)
        return None, f"Ошибка сети: {e}"


async def fetch_player_avatar(role_id: int, zone_id: int) -> Optional[bytes]:
    """Fetches player avatar binary bytes."""
    cache_key = f"{role_id}-{zone_id}"
    now = time.time()
    if cache_key in AVATAR_CACHE:
        av_bytes, ts = AVATAR_CACHE[cache_key]
        if now - ts < CACHE_TTL:
            return av_bytes

    url = f"{API_BASE_URL}/profile/{role_id}-{zone_id}/avatar"
    try:
        status, data = await asyncio.to_thread(_http_get, url, 10)
        if status == 200 and data and len(data) > 100:
            AVATAR_CACHE[cache_key] = (data, now)
            return data
    except Exception as e:
        logger.debug("Could not fetch avatar for %s-%s: %s", role_id, zone_id, e)
    return None


async def request_auth_code(role_id: int, zone_id: int) -> Tuple[bool, str]:
    """Sends verification code request to player in-game mailbox."""
    url = f"{API_BASE_URL}/auth/send-code"
    payload = {"roleId": role_id, "zoneId": zone_id}

    try:
        status, body = await asyncio.to_thread(_http_post_json, url, payload, 15)
        if status in (200, 201):
            return True, "Код успешно отправлен во внутриигровую почту Mobile Legends"
        try:
            data = json.loads(body.decode("utf-8", "ignore"))
            err = data.get("error") or data.get("message") or f"HTTP {status}"
        except Exception:
            err = f"HTTP {status}"
        return False, str(err)
    except Exception as e:
        logger.error("Error sending MLBB auth code: %s", e)
        return False, f"Сетевая ошибка: {e}"


async def verify_player_code(role_id: int, zone_id: int, code: str) -> Tuple[bool, str, Optional[dict]]:
    """Verifies the code from in-game mail and links the profile."""
    url = f"{API_BASE_URL}/auth/verify"
    payload = {"roleId": role_id, "zoneId": zone_id, "code": code.strip()}

    try:
        status, body = await asyncio.to_thread(_http_post_json, url, payload, 15)
        try:
            data = json.loads(body.decode("utf-8", "ignore"))
        except Exception:
            data = {}

        if status in (200, 201):
            user_data = data.get("user") or {}
            return True, "Авторизация успешно завершена", user_data
        err = data.get("error") or data.get("message") or f"Неверный код (HTTP {status})"
        return False, str(err), None
    except Exception as e:
        logger.error("Error verifying MLBB code: %s", e)
        return False, f"Сетевая ошибка: {e}", None


async def fetch_leaderboard() -> Optional[List[dict]]:
    """Fetches top ranking players."""
    url = f"{API_BASE_URL}/rankings/rank"
    try:
        status, body = await asyncio.to_thread(_http_get, url, 12)
        if status == 200:
            data = json.loads(body.decode("utf-8", "ignore"))
            return data.get("rankings") or []
    except Exception as e:
        logger.error("Error fetching MLBB leaderboard: %s", e)
    return None


def register_mlbb(client: TelegramClient, prefix: str):
    """Registers Mobile Legends statistics plugin command handlers."""

    pattern = rf"^{prefix}mlbb(?:\s+(.*))?$"

    @client.on(events.NewMessage(outgoing=True, pattern=pattern))
    async def mlbb_handler(event: events.NewMessage.Event):
        raw_arg = (event.pattern_match.group(1) or "").strip()
        args = raw_arg.split()
        subcmd = args[0].lower() if args else ""

        # --- SUBCMD: .mlbb auth <roleId> <zoneId> ---
        if subcmd == "auth":
            if len(args) < 3 or not args[1].isdigit() or not args[2].isdigit():
                card = render_card(
                    title="Привязка аккаунта MLBB",
                    subtitle="Укажите ваш игровой ID и Zone ID (сервер в скобках)",
                    badge_text="ПАРАМЕТРЫ",
                    badge_type="warn",
                    items=[
                        (f"{prefix}mlbb auth <id> <zone>", "Запросить код подтверждения в игру"),
                        (f"{prefix}mlbb verify <code>", "Подтвердить полученный 6-значный код"),
                        ("Пример", f"{prefix}mlbb auth 314626595 6242"),
                    ],
                    category="MLBB // AUTHENTICATION",
                )
                try:
                    await event.delete()
                except Exception:
                    pass
                return await client.send_file(event.chat_id, file=card)

            role_id = int(args[1])
            zone_id = int(args[2])

            ok, msg = await request_auth_code(role_id, zone_id)
            if ok:
                PENDING_AUTH[event.sender_id] = (role_id, zone_id, time.time())
                card = render_card(
                    title="Код отправлен в игру",
                    subtitle="Откройте почту в Mobile Legends: Bang Bang",
                    badge_text="ОЖИДАНИЕ КОДА",
                    badge_type="running",
                    stats=[
                        ("ИГРОВОЙ ID", str(role_id)),
                        ("ЗОНА / СЕРВЕР", str(zone_id)),
                        ("ТАЙМАУТ КОДА", "5 минут"),
                        ("КОМАНДА", f"{prefix}mlbb verify <код>"),
                    ],
                    items=[
                        ("Инструкция", "Зайдите в игру -> Почта -> Системные -> Скопируйте код"),
                        (f"{prefix}mlbb verify 123456", "Отправьте код в этот чат для завершения привязки"),
                    ],
                    category="MLBB // MAIL VERIFICATION",
                )
            else:
                card = render_card(
                    title="Ошибка отправки кода",
                    subtitle=msg,
                    badge_text="ОШИБКА",
                    badge_type="error",
                    stats=[
                        ("ЦЕЛЕВОЙ ID", str(role_id)),
                        ("СЕРВЕР", str(zone_id)),
                        ("СТАТУС", "ОТКЛОНЕНО"),
                        ("ПОВТОР", "Через 1 минуту"),
                    ],
                    category="MLBB // AUTH ERROR",
                )
            try:
                await event.delete()
            except Exception:
                pass
            return await client.send_file(event.chat_id, file=card)

        # --- SUBCMD: .mlbb verify <code> ---
        if subcmd == "verify":
            if len(args) < 2:
                card = render_card(
                    title="Подтверждение кода",
                    subtitle="Укажите код из внутриигровой почты",
                    badge_text="ТРЕБУЕТСЯ КОД",
                    badge_type="warn",
                    items=[
                        (f"{prefix}mlbb verify <код>", "Подтвердить код верификации"),
                        ("Пример", f"{prefix}mlbb verify 582914"),
                    ],
                    category="MLBB // CODE VERIFY",
                )
                try:
                    await event.delete()
                except Exception:
                    pass
                return await client.send_file(event.chat_id, file=card)

            code = args[1]
            pending = PENDING_AUTH.get(event.sender_id)
            if not pending or (time.time() - pending[2] > 300):
                card = render_card(
                    title="Сессия не найдена",
                    subtitle="Время ожидания кода истекло или вы не отправляли запрос",
                    badge_text="ТАЙМАУТ",
                    badge_type="error",
                    items=[
                        (f"{prefix}mlbb auth <id> <zone>", "Сначала запросите код в игру"),
                    ],
                    category="MLBB // SESSION EXPIRED",
                )
                try:
                    await event.delete()
                except Exception:
                    pass
                return await client.send_file(event.chat_id, file=card)

            role_id, zone_id, _ = pending
            ok, msg, _ = await verify_player_code(role_id, zone_id, code)

            if ok:
                PENDING_AUTH.pop(event.sender_id, None)
                # Persist as default account in plugin config
                update_plugin_config("mlbb", default_role_id=str(role_id), default_zone_id=str(zone_id))

                # Immediately fetch profile and avatar
                profile, _ = await fetch_player_profile(role_id, zone_id)
                avatar_bytes = await fetch_player_avatar(role_id, zone_id)

                if profile:
                    card = render_mlbb_card(profile, avatar_bytes)
                else:
                    card = render_card(
                        title="Аккаунт успешно привязан",
                        subtitle=f"ID: {role_id} ({zone_id}) сохранен как основной",
                        badge_text="УСПЕШНО",
                        badge_type="success",
                        stats=[
                            ("АККАУНТ", f"{role_id} ({zone_id})"),
                            ("СТАТУС", "АВТОРИЗОВАН"),
                            ("ПРОСМОТР", f"{prefix}mlbb"),
                            ("СИНХРОНИЗАЦИЯ", "АКТИВНА"),
                        ],
                        category="MLBB // ACCOUNT LINKED",
                    )
            else:
                card = render_card(
                    title="Ошибка верификации",
                    subtitle=msg,
                    badge_text="НЕВЕРНЫЙ КОД",
                    badge_type="error",
                    stats=[
                        ("ИГРОВОЙ ID", str(role_id)),
                        ("ВВЕДЕННЫЙ КОД", code),
                        ("СТАТУС", "ОТКЛОНЕНО"),
                        ("ДЕЙСТВИЕ", "Проверьте код в почте игры"),
                    ],
                    category="MLBB // VERIFY ERROR",
                )

            try:
                await event.delete()
            except Exception:
                pass
            return await client.send_file(event.chat_id, file=card)

        # --- SUBCMD: .mlbb set <roleId> <zoneId> ---
        if subcmd == "set":
            if len(args) < 3 or not args[1].isdigit() or not args[2].isdigit():
                card = render_card(
                    title="Установка основного ID",
                    subtitle="Укажите ID и сервер для быстрого вызова по команде .mlbb",
                    badge_text="СИНТАКСИС",
                    badge_type="info",
                    items=[
                        (f"{prefix}mlbb set <id> <zone>", "Сохранить профиль по умолчанию"),
                        ("Пример", f"{prefix}mlbb set 314626595 6242"),
                    ],
                    category="MLBB // CONFIGURATION",
                )
                try:
                    await event.delete()
                except Exception:
                    pass
                return await client.send_file(event.chat_id, file=card)

            r_id, z_id = args[1], args[2]
            update_plugin_config("mlbb", default_role_id=r_id, default_zone_id=z_id)
            card = render_card(
                title="Профиль сохранен",
                subtitle=f"ID {r_id} ({z_id}) установлен по умолчанию",
                badge_text="СОХРАНЕНО",
                badge_type="success",
                stats=[
                    ("ОСНОВНОЙ ID", str(r_id)),
                    ("ЗОНА", str(z_id)),
                    ("ВЫЗОВ КАРТОЧКИ", f"{prefix}mlbb"),
                    ("ОБНОВЛЕНИЕ", "Автоматически"),
                ],
                category="MLBB // DEFAULT PROFILE",
            )
            try:
                await event.delete()
            except Exception:
                pass
            return await client.send_file(event.chat_id, file=card)

        # --- SUBCMD: .mlbb top ---
        if subcmd == "top":
            rankings = await fetch_leaderboard()
            if not rankings:
                card = render_card(
                    title="Рейтинг игроков недоступен",
                    subtitle="Не удалось получить актуальные данные лидерборда",
                    badge_text="ОШИБКА",
                    badge_type="error",
                    category="MLBB // LEADERBOARD",
                )
                try:
                    await event.delete()
                except Exception:
                    pass
                return await client.send_file(event.chat_id, file=card)

            top_items = []
            for p in rankings[:7]:
                pos = p.get("position", "")
                p_name = p.get("name", "Unknown")
                p_rank = p.get("rankName", "")
                p_stars = p.get("rankStars", 0)
                p_id = f"{p.get('roleId')} ({p.get('zoneId')})"
                top_items.append((f"#{pos} {p_name}", f"{p_rank} {p_stars}★ • {p_id}"))

            card = render_card(
                title="Топ игроков сезона // MLBB",
                subtitle="Актуальный глобальный лидерборд Mobile Legends: Bang Bang",
                badge_text="TOP RANKINGS",
                badge_type="warn",
                items=top_items,
                meta_left="MLBB TELEMETRY // GLOBAL LEADERBOARD",
                meta_right="DATA VERIFIED",
                category="MLBB // SEASON RANKINGS",
            )
            try:
                await event.delete()
            except Exception:
                pass
            return await client.send_file(event.chat_id, file=card)

        # --- SUBCMD: .mlbb <roleId> <zoneId> (Direct lookup) ---
        target_role = ""
        target_zone = ""

        if len(args) >= 2 and args[0].isdigit() and args[1].isdigit():
            target_role = args[0]
            target_zone = args[1]
        elif len(args) == 0:
            cfg = get_plugin_config("mlbb")
            target_role = cfg.get("default_role_id", "")
            target_zone = cfg.get("default_zone_id", "")

        if not target_role or not target_zone:
            # Show Help Card
            card = render_card(
                title="Статистика Mobile Legends",
                subtitle="Просмотр досье игроков, винрейта и ранга в реальном времени",
                badge_text="СПРАВКА",
                badge_type="info",
                items=[
                    (f"{prefix}mlbb <id> <zone>", "Показать подробную карточку игрока"),
                    (f"{prefix}mlbb auth <id> <zone>", "Отправить код в игру для авторизации"),
                    (f"{prefix}mlbb verify <код>", "Подтвердить код из почты игры"),
                    (f"{prefix}mlbb set <id> <zone>", "Сохранить свой ID по умолчанию"),
                    (f"{prefix}mlbb top", "Глобальный лидерборд лучших игроков сезона"),
                ],
                meta_left="MLBB TELEMETRY ENGINE v1.0",
                meta_right=f"PREFIX: '{prefix}'",
                category="MLBB // USER GUIDE",
            )
            try:
                await event.delete()
            except Exception:
                pass
            return await client.send_file(event.chat_id, file=card)

        # Lookup player profile
        profile, err = await fetch_player_profile(int(target_role), int(target_zone))
        if not profile:
            card = render_card(
                title="Досье игрока не найдено",
                subtitle=err or "Игрок отсутствует в базе данных",
                badge_text="НЕ НАЙДЕН",
                badge_type="error",
                items=[
                    ("Почему не найден?", "Игрок ещё не был проиндексирован через систему авторизации"),
                    (f"{prefix}mlbb auth {target_role} {target_zone}", "Авторизовать этот аккаунт через код из игры"),
                    ("Проверьте ID", "Убедитесь, что ID и сервер указаны без ошибок"),
                ],
                stats=[
                    ("ЗАПРОШЕННЫЙ ID", str(target_role)),
                    ("ЗОНА / СЕРВЕР", str(target_zone)),
                    ("СТАТУС БАЗЫ", "404 NOT FOUND"),
                    ("РЕШЕНИЕ", f"{prefix}mlbb auth"),
                ],
                category="MLBB // PROFILE SEARCH",
            )
            try:
                await event.delete()
            except Exception:
                pass
            return await client.send_file(event.chat_id, file=card)

        # Player found - fetch avatar and render card
        avatar_bytes = await fetch_player_avatar(int(target_role), int(target_zone))
        card_image = render_mlbb_card(profile, avatar_bytes)

        try:
            await event.delete()
        except Exception:
            pass

        await client.send_file(event.chat_id, file=card_image)
