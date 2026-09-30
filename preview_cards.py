import os
from card_engine import render_card

def generate_samples():
    os.makedirs("previews", exist_ok=True)

    # 1. Purge Completed Card
    card_purge = render_card(
        title="Все сообщения удалены",
        subtitle="История сообщений пользователя успешно очищена в целевом чате",
        badge_text="ОЧИЩЕНО",
        badge_type="success",
        stats=[
            ("УДАЛЕНО СООБЩЕНИЙ", "1,428"),
            ("ЦЕЛЕВОЙ ДИАЛОГ", "@design_team"),
            ("ВРЕМЯ РАБОТЫ", "4.18s"),
            ("СКОРОСТЬ", "341 msg/s"),
        ],
        meta_left="TELEGRAM USERBOT // PURGE ENGINE",
        meta_right="CHUNKS: 15 • LATENCY: 28ms",
        category="DATABASE PURGE OPERATION",
    )
    with open("previews/sample_purge.png", "wb") as f:
        f.write(card_purge.getvalue())
    print("Generated previews/sample_purge.png")

    # 2. Plugins Dashboard Menu Card
    card_plugins = render_card(
        title="Центр управления плагинами",
        subtitle="Каталог расширений и фоновых демонов Telegram юзербота",
        badge_text="2/2 АКТИВНО",
        badge_type="running",
        items=[
            (".online [on|off]", "Вечный онлайн [ВКЛ] — Удерживает статус 'В сети' 24/7"),
            (".autoname [on|off]", "Время в никнейме [ВКЛ] — Обновляет время в имени каждую минуту"),
        ],
        meta_left="USERBOT EXTENSION ENGINE // 2 ACTIVE",
        meta_right="PREFIX: '.'",
        category="PLUGIN REGISTRY & DASHBOARD",
    )
    with open("previews/sample_plugins.png", "wb") as f:
        f.write(card_plugins.getvalue())
    print("Generated previews/sample_plugins.png")

    # 3. Help Card with items list
    card_help = render_card(
        title="Справка по командам",
        subtitle="Доступные команды и параметры управления юзерботом",
        badge_text="РУКОВОДСТВО",
        badge_type="info",
        items=[
            (".plugins", "Центр управления плагинами (каталог расширений)"),
            (".online [on|off]", "Вечный онлайн (автоматический статус 'В сети' 24/7)"),
            (".autoname [on|off]", "Динамическое время в никнейме (поминутно)"),
            (".delall", "Удалить все свои сообщения в текущем чате"),
            (".delall <chat>", "Удалить свои сообщения в указанном чате"),
            (".ping", "Проверить статус работы, задержку MTProto и аптайм"),
            (".help", "Показать эту графическую карточку помощи"),
        ],
        meta_left="COMMAND REGISTRY // v1.3",
        meta_right="PREFIX: '.'",
        category="SYSTEM DOCUMENTATION",
    )
    with open("previews/sample_help.png", "wb") as f:
        f.write(card_help.getvalue())
    print("Generated previews/sample_help.png")

    # 4. System Status / Ping Card
    card_ping = render_card(
        title="Система активна 24/7",
        subtitle="Шлюзы связи и Telethon работают стабильно на Linux Server",
        badge_text="ОНЛАЙН",
        badge_type="info",
        stats=[
            ("ПИНГ MTPROTO", "38 ms"),
            ("ОПЕРАТИВНАЯ ПАМЯТЬ", "42.8 MB"),
            ("АПТАЙМ", "18h 42m"),
            ("ВЕРСИЯ ЯДРА", "v1.3.0"),
        ],
        meta_left="HOST: LINUX SERVER // POLLING 24/7",
        meta_right="TELETHON 1.45.0",
        category="DIAGNOSTICS & TELEMETRY",
    )
    with open("previews/sample_ping.png", "wb") as f:
        f.write(card_ping.getvalue())
    print("Generated previews/sample_ping.png")

    # 5. Anime Quiz Question Card
    from card_engine import render_quiz_card, render_mlbb_card
    card_quiz = render_quiz_card(
        frame_bytes=None,
        masked_hint="А _ _ _ а   т _ _ _ _ в",
        genres="Экшен, Драма, Фэнтези",
        year_season="2013 (Весна 2013)",
    )
    with open("previews/sample_animequiz.png", "wb") as f:
        f.write(card_quiz.getvalue())
    print("Generated previews/sample_animequiz.png")

    # 6. Mobile Legends Player Dossier Card
    sample_player = {
        "roleId": 314626595,
        "zoneId": 6242,
        "name": "RRebySSSA",
        "level": 111,
        "currentRank": {
            "name": "Mythical Immortal",
            "stars": 124,
            "tier": "mythic",
        },
        "historyRank": {
            "name": "Mythical Immortal",
        },
        "stats": [
            {"season": 37, "mode": 2, "games": 42, "winRate": 64.3, "kda": 4.12, "mvp": 14},
            {"season": 36, "mode": 2, "games": 185, "winRate": 61.8, "kda": 3.75, "mvp": 38},
            {"season": 35, "mode": 2, "games": 310, "winRate": 59.4, "kda": 3.28, "mvp": 52},
            {"season": 34, "mode": 2, "games": 161, "winRate": 60.2, "kda": 3.33, "mvp": 22},
        ],
    }
    card_mlbb = render_mlbb_card(sample_player)
    with open("previews/sample_mlbb.png", "wb") as f:
        f.write(card_mlbb.getvalue())
    print("Generated previews/sample_mlbb.png")

if __name__ == "__main__":
    generate_samples()

