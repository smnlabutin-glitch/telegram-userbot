import os
import json
import logging
from config import BASE_DIR

logger = logging.getLogger("userbot.plugins")

STATE_FILE = os.path.join(BASE_DIR, "plugins_state.json")

DEFAULT_STATE = {
    "always_online": {
        "enabled": False,
        "title": "Вечный онлайн",
        "description": "Автоматически удерживает статус 'В сети' 24/7",
        "command": ".online [on|off]",
    },
    "time_name": {
        "enabled": False,
        "title": "Время в никнейме",
        "description": "Отображает текущее время в имени и обновляет каждую минуту",
        "command": ".autoname [on|off]",
        "tz_offset": 3,  # Default MSK (UTC+3)
        "original_first_name": "",
        "original_last_name": "",
        "format": "{name} | {time}",
    },
    "anime_quiz": {
        "enabled": True,
        "title": "Аниме викторина",
        "description": "Интерактивная игра 'Угадай аниме по кадру' в реальном времени",
        "command": ".animequiz [stop]",
    }
}

def load_state() -> dict:
    if os.path.isfile(STATE_FILE):
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                # Merge defaults for any missing keys
                for k, v in DEFAULT_STATE.items():
                    if k not in data:
                        data[k] = v
                    else:
                        for sub_k, sub_v in v.items():
                            if sub_k not in data[k]:
                                data[k][sub_k] = sub_v
                return data
        except Exception as e:
            logger.error("Error reading plugins_state.json: %s", e)
    return DEFAULT_STATE.copy()

def save_state(state: dict):
    try:
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error("Error writing plugins_state.json: %s", e)

# Singleton state container
PLUGIN_STATE = load_state()

def get_plugin_config(plugin_name: str) -> dict:
    if plugin_name not in PLUGIN_STATE:
        PLUGIN_STATE[plugin_name] = DEFAULT_STATE.get(plugin_name, {"enabled": False})
    return PLUGIN_STATE[plugin_name]

def update_plugin_config(plugin_name: str, **kwargs):
    if plugin_name not in PLUGIN_STATE:
        PLUGIN_STATE[plugin_name] = DEFAULT_STATE.get(plugin_name, {"enabled": False}).copy()
    PLUGIN_STATE[plugin_name].update(kwargs)
    save_state(PLUGIN_STATE)
