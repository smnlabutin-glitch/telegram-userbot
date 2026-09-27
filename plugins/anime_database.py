import os
import json
import random
import re
import logging

logger = logging.getLogger("userbot.plugins.anime_database")

DATASET_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "anime_dataset.json")

FALLBACK_DATASET = [
    {
        "id": "attack_on_titan",
        "title": "Атака титанов (Attack on Titan)",
        "canonical": "Атака титанов",
        "image_url": "https://s4.anilist.co/file/anilistcdn/media/anime/banner/16498-8jpFCOcDmneX.jpg",
        "genres": "Экшен, Драма, Фэнтези, Военное",
        "year": "2013",
        "season": "Весна 2013",
        "answers": [
            "атака титанов", "attack on titan", "shingeki no kyojin", "snk", "атака на титанов",
            "вторжение гигантов", "титаны", "attackontitan", "shingekinokyojin"
        ]
    },
    {
        "id": "death_note",
        "title": "Тетрадь смерти (Death Note)",
        "canonical": "Тетрадь смерти",
        "image_url": "https://s4.anilist.co/file/anilistcdn/media/anime/banner/1535.jpg",
        "genres": "Детектив, Триллер, Психологическое, Мистика",
        "year": "2006",
        "season": "Осень 2006",
        "answers": [
            "тетрадь смерти", "death note", "тетрадка смерти", "дез нот", "дэт ноут",
            "deathnote", "тетрадь"
        ]
    },
    {
        "id": "demon_slayer",
        "title": "Клинок, рассекающий демонов (Demon Slayer)",
        "canonical": "Клинок рассекающий демонов",
        "image_url": "https://s4.anilist.co/file/anilistcdn/media/anime/banner/101922-33MtJGsUSxga.jpg",
        "genres": "Экшен, Сверхъестественное, Исторический",
        "year": "2019",
        "season": "Весна 2019",
        "answers": [
            "клинок рассекающий демонов", "demon slayer", "kimetsu no yaiba", "крд",
            "клинок", "клинок демонов", "demonslayer", "kimetsunoyaiba"
        ]
    }
]

def load_dataset() -> list:
    if os.path.isfile(DATASET_FILE):
        try:
            with open(DATASET_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list) and len(data) > 0:
                    return data
        except Exception as e:
            logger.error("Failed to load anime_dataset.json: %s", e)
    return FALLBACK_DATASET

ANIME_DATASET = load_dataset()

def generate_masked_hint(title: str) -> str:
    """
    Creates an aesthetic masked hint.
    E.g. "Атака титанов" -> "А _ _ _ а   т _ _ _ _ в"
    Preserves first and last letter of each word of length >= 3.
    """
    base_title = re.sub(r"\s*\(.*?\)", "", title).strip() or title
    words = base_title.split()
    masked_words = []
    for word in words:
        clean = re.sub(r"[^\w]", "", word)
        if len(clean) <= 2:
            masked_words.append(word)
        elif len(clean) == 3:
            masked_words.append(f"{clean[0]} _ {clean[-1]}")
        else:
            middle_count = len(clean) - 2
            masked_middle = " ".join(["_"] * middle_count)
            masked_words.append(f"{clean[0]} {masked_middle} {clean[-1]}")
    return "   ".join(masked_words)

HISTORY_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "anime_quiz_history.json")

def _load_history() -> dict:
    if os.path.isfile(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    return data
        except Exception as e:
            logger.warning("Could not read anime quiz history: %s", e)
    return {}

def _save_history(history: dict):
    try:
        with open(HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(history, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.warning("Could not save anime quiz history: %s", e)

CHAT_PLAYED_CYCLE: dict = _load_history()

def get_random_anime(exclude_id: str = None, chat_id: int = None) -> dict:
    """
    Selects a random anime with dynamic cycle weighting:
    - Never repeats exclude_id directly.
    - Anime that haven't appeared in current cycle have 100x higher probability (weight=100).
    - Anime that already appeared have 1x weight (greatly reduced chance).
    - Once all anime have appeared (full circle), the cycle resets automatically.
    - Preserves cycle history across bot restarts per chat.
    """
    chat_key = str(chat_id) if chat_id is not None else "global"
    played_list = list(CHAT_PLAYED_CYCLE.get(chat_key, []))
    played_set = set(played_list)

    # Full cycle completed: reset cycle history for this chat
    if len(played_set) >= len(ANIME_DATASET):
        played_set.clear()
        played_list.clear()
        CHAT_PLAYED_CYCLE[chat_key] = []
        _save_history(CHAT_PLAYED_CYCLE)

    # Pool of available candidates excluding the immediate predecessor
    pool = [a for a in ANIME_DATASET if a["id"] != exclude_id]
    if not pool:
        pool = ANIME_DATASET

    # Assign weights: 100 for unplayed in current cycle, 1 for already played
    weights = [1 if a["id"] in played_set else 100 for a in pool]

    chosen = random.choices(pool, weights=weights, k=1)[0]
    choice = chosen.copy()

    # Track chosen anime in the current cycle
    played_list.append(choice["id"])
    CHAT_PLAYED_CYCLE[chat_key] = played_list
    _save_history(CHAT_PLAYED_CYCLE)

    choice["masked_hint"] = generate_masked_hint(choice["canonical"])
    return choice

