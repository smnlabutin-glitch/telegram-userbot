import os
import sys
import time
import platform
import asyncio
from telethon import TelegramClient, events
from card_engine import render_card
from config import BASE_DIR

BOOT_TIME = time.monotonic()

def format_uptime(seconds: float) -> str:
    secs = int(seconds)
    hours, rem = divmod(secs, 3600)
    mins, sec = divmod(rem, 60)
    if hours > 0:
        return f"{hours}h {mins}m"
    if mins > 0:
        return f"{mins}m {sec}s"
    return f"{sec}s"

def get_ram_usage() -> str:
    """Returns memory usage of current process in MB."""
    # 1. Linux procfs VmRSS
    try:
        with open("/proc/self/status", "r", encoding="utf-8") as f:
            for line in f:
                if line.startswith("VmRSS:"):
                    parts = line.split()
                    kb = int(parts[1])
                    return f"{kb / 1024:.1f} MB"
    except Exception:
        pass

    # 2. Python resource module (macOS / Unix)
    try:
        import resource
        rusage = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        if sys.platform == "darwin":
            return f"{rusage / (1024 * 1024):.1f} MB"
        return f"{rusage / 1024:.1f} MB"
    except Exception:
        pass

    # 3. Windows / Fallback
    try:
        import ctypes
        from ctypes import wintypes
        class PROCESS_MEMORY_COUNTERS(ctypes.Structure):
            _fields_ = [
                ('cb', wintypes.DWORD),
                ('PageFaultCount', wintypes.DWORD),
                ('PeakWorkingSetSize', ctypes.c_size_t),
                ('WorkingSetSize', ctypes.c_size_t),
                ('QuotaPeakPagedPoolUsage', ctypes.c_size_t),
                ('QuotaPagedPoolUsage', ctypes.c_size_t),
                ('QuotaPeakNonPagedPoolUsage', ctypes.c_size_t),
                ('QuotaNonPagedPoolUsage', ctypes.c_size_t),
                ('PagefileUsage', ctypes.c_size_t),
                ('PeakPagefileUsage', ctypes.c_size_t)
            ]
        counters = PROCESS_MEMORY_COUNTERS()
        counters.cb = ctypes.sizeof(PROCESS_MEMORY_COUNTERS)
        handle = ctypes.windll.kernel32.GetCurrentProcess()
        if ctypes.windll.psapi.GetProcessMemoryInfo(handle, ctypes.byref(counters), counters.cb):
            return f"{counters.WorkingSetSize / (1024 * 1024):.1f} MB"
    except Exception:
        pass

    return "Active"

async def perform_graceful_restart(client: TelegramClient):
    """Instantly kills process at OS level so systemd triggers clean fresh restart."""
    try:
        from plugins.keru_bot import stop_keru_bot
        stop_keru_bot()
    except Exception:
        pass
    os._exit(0)

_perform_graceful_restart = perform_graceful_restart

def register_system_handlers(client: TelegramClient, prefix: str):
    """Registers system diagnostic and help commands."""

    # .ping
    @client.on(events.NewMessage(outgoing=True, pattern=rf"^{prefix}ping$"))
    async def ping_handler(event: events.NewMessage.Event):
        start = time.monotonic()
        me = await client.get_me()
        latency_ms = (time.monotonic() - start) * 1000
        uptime = format_uptime(time.monotonic() - BOOT_TIME)
        ram = get_ram_usage()

        op_name = f"@{me.username}" if me.username else (me.first_name or "Me")
        system_os = "Linux Server" if sys.platform.startswith("linux") else platform.system()

        card = render_card(
            title="Система активна 24/7",
            subtitle=f"Шлюзы связи и Telethon работают стабильно на {system_os}",
            badge_text="ОНЛАЙН",
            badge_type="info",
            stats=[
                ("ПИНГ MTPROTO", f"{latency_ms:.1f} ms"),
                ("ОПЕРАТИВНАЯ ПАМЯТЬ", ram),
                ("АПТАЙМ БОТА", uptime),
                ("ВЕРСИЯ ЯДРА", "v1.3.0"),
            ],
            meta_left=f"HOST: {system_os.upper()} // POLLING 24/7",
            meta_right=f"SESSION: OK • ID: {me.id}",
            category="SERVER HEALTH & TELEMETRY",
        )

        try:
            await event.delete()
        except Exception:
            pass

        await client.send_file(event.chat_id, file=card)

    # .help
    @client.on(events.NewMessage(outgoing=True, pattern=rf"^{prefix}help$"))
    async def help_handler(event: events.NewMessage.Event):
        card = render_card(
            title="Справка по командам",
            subtitle="Доступные команды и параметры управления юзерботом",
            badge_text="РУКОВОДСТВО",
            badge_type="info",
            items=[
                (f"{prefix}update", "Обновить юзербота (git pull + автоперезапуск)"),
                (f"{prefix}restart", "Перезапустить службу юзербота 24/7"),
                (f"{prefix}plugins", "Центр управления плагинами (каталог расширений)"),
                (f"{prefix}mlbb [id zone|auth|top]", "Карточка статистики Mobile Legends (MLBB)"),
                (f"{prefix}animequiz [stop]", "Мини-игра 'Угадай аниме по кадру' в реальном времени"),
                (f"{prefix}online [on|off]", "Вечный онлайн (автоматический статус 'В сети' 24/7)"),
                (f"{prefix}autoname [on|off]", "Динамическое время в никнейме (поминутно)"),
                (f"{prefix}delall", "Удалить все свои сообщения в текущем чате"),
                (f"{prefix}delall <chat>", "Удалить свои сообщения в указанном чате"),
                (f"{prefix}id [user|reply]", "Узнать Telegram ID пользователя или чата (по реплаю/юзернейму)"),
                (f"{prefix}ping", "Проверить статус работы, задержку MTProto, RAM и аптайм"),
                (f"{prefix}help", "Показать эту графическую карточку справки"),
            ],
            meta_left="COMMAND REGISTRY // MINIMAL DARK UI",
            meta_right=f"PREFIX: '{prefix}'",
            category="SYSTEM DOCUMENTATION",
        )

        try:
            await event.delete()
        except Exception:
            pass

        await client.send_file(event.chat_id, file=card)

    # .keru / .kstatus (Instant Diagnostic Card)
    @client.on(events.NewMessage(outgoing=True, pattern=rf"^{prefix}(?:keru|kstatus)$"))
    async def keru_diagnostic_handler(event: events.NewMessage.Event):
        from plugins.keru_bot import BOT_CLIENT, BOT_USERNAME, BOT_USER_ID, OWNER_USER_ID, AUTHORIZED_CHATS, KERU_MEMORY, LAST_API_ERROR, DEEPSEEK_MODELS_CASCADE, KERU_BUILD_VERSION
        from config import KERU_BOT_TOKEN, PROXYAPI_KEY

        is_connected = bool(BOT_CLIENT and BOT_CLIENT.is_connected())
        badge_text = "АКТИВЕН (ONLINE)" if is_connected else "НЕ ЗАПУЩЕН (OFFLINE)"
        badge_type = "success" if is_connected else "danger"

        card = render_card(
            title="Диагностика Керу",
            subtitle="Текущий статус сервиса кошкодевочки Керу",
            badge_text=badge_text,
            badge_type=badge_type,
            stats=[
                ("БОТ TELEGRAM", f"@{BOT_USERNAME}" if BOT_USERNAME else ("Токен задан" if KERU_BOT_TOKEN else "Нет токена")),
                ("ОСНОВНАЯ МОДЕЛЬ", DEEPSEEK_MODELS_CASCADE[0] if PROXYAPI_KEY else "ОТСУТСТВУЕТ"),
                ("ВЕРСИЯ ЯДРА", KERU_BUILD_VERSION),
                ("СТАТУС СЕТИ", "Подключен" if is_connected else "Отключен"),
            ],
            items=[
                ("ID Владельца", str(OWNER_USER_ID or "Не задан")),
                ("ID Бота Керу", str(BOT_USER_ID or "Не авторизован")),
                ("Авторизованных чатов", f"{len(AUTHORIZED_CHATS)} чатов"),
                ("Последняя ошибка ИИ", LAST_API_ERROR[:32] if LAST_API_ERROR else "Ошибок нет (OK)"),
            ],
            meta_left=f"KERU BOT // {KERU_BUILD_VERSION}",
            meta_right="MTPROTO DAEMON",
            category="AI SERVICE STATUS",
        )
        try:
            await event.delete()
        except Exception:
            pass
        await client.send_file(event.chat_id, file=card)

    # .update / .upgrade
    @client.on(events.NewMessage(outgoing=True, pattern=rf"^{prefix}(?:update|upgrade)$"))
    async def update_handler(event: events.NewMessage.Event):
        try:
            await event.edit("`[OTA UPDATE] Проверка и скачивание обновлений из GitHub...`")
        except Exception:
            pass

        cmd = "git config --global --add safe.directory '*' 2>/dev/null; git fetch origin main && git reset --hard origin/main"
        try:
            proc = await asyncio.create_subprocess_shell(
                cmd,
                cwd=BASE_DIR,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await proc.communicate()
            output = stdout.decode().strip()
            err = stderr.decode().strip()
            return_code = proc.returncode
        except Exception as ex:
            output = ""
            err = str(ex)
            return_code = 1

        if return_code != 0:
            err_msg = (err or output or "Неизвестная ошибка git")[:120]
            card = render_card(
                title="Ошибка обновления",
                subtitle=f"Не удалось стянуть код: {err_msg}",
                badge_text="ОШИБКА",
                badge_type="danger",
                stats=[
                    ("СТАТУС", "Сбой git"),
                    ("КОД ВОЗВРАТА", str(return_code)),
                    ("ВЕТКА", "main"),
                    ("ДЕЙСТВИЕ", "Отменено"),
                ],
                meta_left="OTA UPDATE ENGINE // ERROR",
                meta_right="GIT ERROR",
                category="SYSTEM UPDATE MANAGER",
            )
            try:
                await event.delete()
            except Exception:
                pass
            await client.send_file(event.chat_id, file=card)
            return

        # Get latest commit info
        commit_info = "Обновлено"
        try:
            c_proc = await asyncio.create_subprocess_shell(
                'git log -1 --format="%h: %s"',
                cwd=BASE_DIR,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            c_out, _ = await c_proc.communicate()
            if c_out:
                commit_info = c_out.decode().strip()[:40]
        except Exception:
            pass

        card = render_card(
            title="Обновление установлено",
            subtitle=f"Код синхронизирован: {commit_info}. Перезапуск службы...",
            badge_text="ОБНОВЛЕНО",
            badge_type="success",
            stats=[
                ("КОММИТ", commit_info[:20]),
                ("СТАТУС", "Перезапуск..."),
                ("СЕССИЯ", "Сохранена"),
                ("ВРЕМЯ", "< 2 сек"),
            ],
            meta_left="OTA UPDATE ENGINE // SUCCESS",
            meta_right="AUTO-RESTARTING",
            category="SYSTEM UPDATE MANAGER",
        )
        try:
            await event.delete()
        except Exception:
            pass
        await client.send_file(event.chat_id, file=card)
        await asyncio.sleep(2)
        await perform_graceful_restart(client)

    # .restart / .reboot
    @client.on(events.NewMessage(outgoing=True, pattern=rf"^{prefix}(?:restart|reboot)$"))
    async def restart_handler(event: events.NewMessage.Event):
        card = render_card(
            title="Перезапуск юзербота",
            subtitle="Выполняется контролируемый перезапуск службы 24/7...",
            badge_text="ПЕРЕЗАПУСК",
            badge_type="warn",
            stats=[
                ("СТАТУС", "Перезагрузка"),
                ("ДЕМОН", "systemd / in-place"),
                ("ВРЕМЯ", "~2 сек"),
                ("СЕССИЯ", "Сохранена"),
            ],
            meta_left="SYSTEM DAEMON // RESTART",
            meta_right="GRACEFUL EXIT",
            category="LIFECYCLE MANAGEMENT",
        )
        try:
            await event.delete()
        except Exception:
            pass
        await client.send_file(event.chat_id, file=card)
        await asyncio.sleep(2)
        await _perform_graceful_restart(client)

    # .clean (kill duplicate processes & disable conflicting services)
    @client.on(events.NewMessage(outgoing=True, pattern=rf"^{prefix}clean$"))
    async def clean_handler(event: events.NewMessage.Event):
        card = render_card(
            title="Очистка дубликатов",
            subtitle="Уничтожение висящих фоновых копий бота...",
            badge_text="ОЧИСТКА",
            badge_type="info",
            stats=[
                ("СЛУЖБА", "userbot -> disabled"),
                ("ПРОЦЕССЫ", "Уничтожение лишних"),
                ("РЕЗУЛЬТАТ", "Один процесс 24/7"),
            ],
            category="PROCESS MANAGER"
        )
        try:
            await event.delete()
        except Exception:
            pass
        await client.send_file(event.chat_id, file=card)

        import subprocess
        my_pid = os.getpid()
        try:
            subprocess.run(["systemctl", "stop", "userbot"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            subprocess.run(["systemctl", "disable", "userbot"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception:
            pass
        try:
            raw = subprocess.check_output(["pgrep", "-f", "python.*main.py"]).decode().strip()
            for p in raw.splitlines():
                pid = int(p.strip())
                if pid != my_pid:
                    try:
                        os.kill(pid, 9)
                    except Exception:
                        pass
        except Exception:
            pass

    # .cmd <shell command>
    @client.on(events.NewMessage(outgoing=True, pattern=rf"^{prefix}cmd\s+(.+)$"))
    async def cmd_handler(event: events.NewMessage.Event):
        cmd = event.pattern_match.group(1).strip()
        msg = await event.reply(f"⏳ **Выполняю:** `{cmd}`...")
        import subprocess
        try:
            proc = subprocess.run(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, timeout=30)
            res = (proc.stdout or "").strip()
            if not res:
                res = "Команда выполнена успешно (вывод пуст)"
            if len(res) > 3500:
                res = res[:3500] + "\n... (обрезано)"
            await msg.edit(f"💻 **Результат (`{cmd}`):**\n```\n{res}\n```")
        except Exception as e:
            await msg.edit(f"❌ **Ошибка выполнения:** `{e}`")

    # .id [user | reply]
    @client.on(events.NewMessage(outgoing=True, pattern=rf"^{prefix}id(?:(?:\s+)(.*))?$"))
    async def id_handler(event: events.NewMessage.Event):
        from telethon.tl.types import User, Channel, Chat
        args = (event.pattern_match.group(1) or "").strip()
        reply_msg = await event.get_reply_message()
        target_entity = None
        source_desc = "Текущий аккаунт"

        if args:
            source_desc = f"Запрос: {args}"
            try:
                target_val = int(args) if (args.isdigit() or (args.startswith("-") and args[1:].isdigit())) else args
                target_entity = await client.get_entity(target_val)
            except Exception as e:
                card = render_card(
                    title="Объект не найден",
                    subtitle=f"Не удалось найти пользователя или чат: {args}",
                    badge_text="ОШИБКА",
                    badge_type="error",
                    items=[
                        ("Запрос", args),
                        ("Причина", str(e)),
                        ("Форматы", f"{prefix}id @username, {prefix}id 12345678 или реплай"),
                    ],
                    stats=[
                        ("СТАТУС", "НЕ НАЙДЕН"),
                        ("ТИП ПОИСКА", "ENTITY LOOKUP"),
                    ],
                    category="TELEGRAM IDENTIFIER",
                )
                try:
                    await event.delete()
                except Exception:
                    pass
                return await client.send_file(event.chat_id, file=card)
        elif reply_msg:
            source_desc = "Ответ на сообщение"
            if reply_msg.sender:
                target_entity = reply_msg.sender
            elif reply_msg.sender_id:
                try:
                    target_entity = await client.get_entity(reply_msg.sender_id)
                except Exception:
                    pass

            if not target_entity and reply_msg.forward:
                source_desc = "Пересланное сообщение"
                if reply_msg.forward.sender:
                    target_entity = reply_msg.forward.sender
                elif reply_msg.forward.sender_id:
                    try:
                        target_entity = await client.get_entity(reply_msg.forward.sender_id)
                    except Exception:
                        pass
        else:
            source_desc = "Текущий профиль"
            target_entity = await client.get_me()

        if not target_entity:
            sender_id = reply_msg.sender_id if reply_msg else None
            if sender_id:
                target_id = sender_id
                name_str = "Скрытый пользователь"
                username_str = "Скрыт настройками"
                type_str = "Пользователь (Аноним)"
                dc_str = "—"
            else:
                card = render_card(
                    title="Не удалось определить ID",
                    subtitle="Сообщение отправлено анонимно либо автор скрыт",
                    badge_text="СКРЫТО",
                    badge_type="warn",
                    stats=[("ЧАТ", str(event.chat_id)), ("СТАТУС", "НЕ ОПРЕДЕЛЕН")],
                    category="TELEGRAM IDENTIFIER",
                )
                try:
                    await event.delete()
                except Exception:
                    pass
                return await client.send_file(event.chat_id, file=card)
        else:
            target_id = target_entity.id
            if isinstance(target_entity, User):
                name_parts = [target_entity.first_name or "", target_entity.last_name or ""]
                name_str = " ".join(p for p in name_parts if p).strip() or "Без имени"
                username_str = f"@{target_entity.username}" if target_entity.username else "Нет юзернейма"
                if target_entity.bot:
                    type_str = "Бот Telegram"
                elif getattr(target_entity, "premium", False):
                    type_str = "Telegram Premium"
                else:
                    type_str = "Пользователь"
                dc_id = getattr(getattr(target_entity, "photo", None), "dc_id", None)
                dc_str = f"DC {dc_id}" if dc_id else "—"
            elif isinstance(target_entity, (Channel, Chat)):
                name_str = getattr(target_entity, "title", "Группа / Канал")
                username_str = f"@{target_entity.username}" if getattr(target_entity, "username", None) else "Приватный"
                type_str = "Канал" if getattr(target_entity, "broadcast", False) else "Супергруппа"
                dc_id = getattr(getattr(target_entity, "photo", None), "dc_id", None)
                dc_str = f"DC {dc_id}" if dc_id else "—"
            else:
                name_str = str(target_entity)
                username_str = "—"
                type_str = "Сущность"
                dc_str = "—"

        caption = f"🆔 **Telegram ID:** `{target_id}`\n👤 **Объект:** {name_str} ({username_str})"

        stats_list = [
            ("TELEGRAM ID", str(target_id)),
            ("ТИП АККАУНТА", type_str.upper()),
            ("ДАТАЦЕНТР", dc_str),
            ("ТЕКУЩИЙ ЧАТ", str(event.chat_id)),
        ]

        items_list = [
            ("Имя / Название", name_str),
            ("Юзернейм", username_str),
            ("Источник запроса", source_desc),
        ]
        if reply_msg:
            items_list.append(("ID Сообщения", str(reply_msg.id)))

        card = render_card(
            title=f"ID: {target_id}",
            subtitle=f"{name_str} • {username_str}",
            badge_text=type_str.upper(),
            badge_type="info" if type_str != "Бот Telegram" else "warn",
            stats=stats_list,
            items=items_list,
            meta_left=f"TELEGRAM RESOLVER // {source_desc.upper()}",
            meta_right=f"PEER ID: {target_id}",
            category="TELEGRAM IDENTIFIER",
        )

        try:
            await event.delete()
        except Exception:
            pass

        await client.send_file(event.chat_id, file=card, caption=caption)

