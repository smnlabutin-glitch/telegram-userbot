import os
import sys
import time
import platform
from telethon import TelegramClient, events
from card_engine import render_card

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
                (f"{prefix}delall", "Удалить все свои сообщения в текущем чате"),
                (f"{prefix}delall <chat>", "Удалить свои сообщения в указанном чате (@username / ID)"),
                (f"{prefix}purge_me", "Синоним команды удаления сообщений"),
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
