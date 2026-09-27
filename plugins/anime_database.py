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

def get_random_anime(exclude_id: str = None) -> dict:
    pool = [a for a in ANIME_DATASET if a["id"] != exclude_id] if exclude_id else ANIME_DATASET
    choice = random.choice(pool if pool else ANIME_DATASET).copy()
    choice["masked_hint"] = generate_masked_hint(choice["canonical"])
    return choice
