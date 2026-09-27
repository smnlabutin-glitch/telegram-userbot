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

    # 2. Help Card with items list
    card_help = render_card(
        title="Справка по командам",
        subtitle="Доступные команды и параметры управления юзерботом",
        badge_text="РУКОВОДСТВО",
        badge_type="info",
        items=[
            (".delall", "Удалить все свои сообщения в текущем чате"),
            (".delall <chat>", "Удалить все свои сообщения в указанном чате (@username / ID)"),
            (".purge_me", "Синоним команды .delall"),
            (".ping", "Проверить статус работы, задержку MTProto и аптайм"),
            (".help", "Показать эту графическую карточку помощи"),
        ],
        meta_left="COMMAND REGISTRY // v1.2",
        meta_right="PREFIX: '.'",
        category="SYSTEM DOCUMENTATION",
    )
    with open("previews/sample_help.png", "wb") as f:
        f.write(card_help.getvalue())
    print("Generated previews/sample_help.png")

    # 3. System Status / Ping Card
    card_ping = render_card(
        title="Система активна",
        subtitle="Все шлюзы связи и клиент Telethon функционируют в штатном режиме",
        badge_text="ОНЛАЙН",
        badge_type="info",
        stats=[
            ("ПИНГ MTPROTO", "38 ms"),
            ("ОПЕРАТОР", "User @smnla"),
            ("АПТАЙМ", "18h 42m"),
            ("ВЕРСИЯ ЯДРА", "v1.2.0"),
        ],
        meta_left="HOST: WIN32 // DC 2 (AMSTERDAM)",
        meta_right="TELETHON 1.45.0",
        category="DIAGNOSTICS & TELEMETRY",
    )
    with open("previews/sample_ping.png", "wb") as f:
        f.write(card_ping.getvalue())
    print("Generated previews/sample_ping.png")

if __name__ == "__main__":
    generate_samples()
