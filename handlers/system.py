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
    """Gracefully closes sessions and restarts service via systemd or in-place execv."""
    try:
        from plugins.keru_bot import stop_keru_bot
        stop_keru_bot()
    except Exception:
        pass
    try:
        await client.disconnect()
    except Exception:
        pass
    await asyncio.sleep(1)

    # 1. Try systemctl restart first
    try:
        code = os.system("sudo -n systemctl restart telegram-userbot 2>/dev/null || systemctl restart telegram-userbot 2>/dev/null")
        if code == 0:
            os._exit(0)
    except Exception:
        pass

    # 2. If running under systemd, systemd has Restart=always configured in deploy.sh.
    # Exiting the process forces systemd to spawn a clean new process with updated files.
    is_systemd = bool(os.getenv("INVOCATION_ID") or os.getenv("JOURNAL_STREAM"))
    if not is_systemd and os.path.exists("/proc/self/cgroup"):
        try:
            with open("/proc/self/cgroup", "r") as f:
                if "systemd" in f.read():
                    is_systemd = True
        except Exception:
            pass

    if is_systemd:
        os._exit(0)

    # 3. Fallback to in-place execv for interactive or standalone execution
    try:
        main_py = os.path.join(BASE_DIR, "main.py")
        os.execv(sys.executable, [sys.executable, main_py])
    except Exception:
        pass

    # 4. Final hard exit to ensure old process never hangs in RAM
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
                (f"{prefix}animequiz [stop]", "Мини-игра 'Угадай аниме по кадру' в реальном времени"),
                (f"{prefix}online [on|off]", "Вечный онлайн (автоматический статус 'В сети' 24/7)"),
                (f"{prefix}autoname [on|off]", "Динамическое время в никнейме (поминутно)"),
                (f"{prefix}delall", "Удалить все свои сообщения в текущем чате"),
                (f"{prefix}delall <chat>", "Удалить свои сообщения в указанном чате"),
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
