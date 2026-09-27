import random
import re

ANIME_DATASET = [
    {
        "id": "attack_on_titan",
        "title": "Атака титанов (Attack on Titan)",
        "canonical": "Атака титанов",
        "image_url": "https://shikimori.one/system/animes/original/16498.jpg",
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
        "image_url": "https://shikimori.one/system/animes/original/1535.jpg",
        "genres": "Детектив, Триллер, Психологическое, Мистика",
        "year": "2006",
        "season": "Осень 2006",
        "answers": [
            "тетрадь смерти", "death note", "тетрадка смерти", "дез нот", "дэт ноут",
            "deathnote", "тетрадь"
        ]
    },
    {
        "id": "kaguya_sama",
        "title": "Госпожа Кагуя: В любви как на войне (Kaguya-sama)",
        "canonical": "Госпожа Кагуя",
        "image_url": "https://shikimori.one/system/animes/original/37999.jpg",
        "genres": "Комедия, Романтика, Школа",
        "year": "2019",
        "season": "Зима 2019",
        "answers": [
            "госпожа кагуя", "kaguya sama", "kaguya-sama", "кагуя", "kaguya",
            "в любви как на войне", "кагуя сама", "kaguyasama"
        ]
    },
    {
        "id": "demon_slayer",
        "title": "Клинок, рассекающий демонов (Demon Slayer)",
        "canonical": "Клинок рассекающий демонов",
        "image_url": "https://shikimori.one/system/animes/original/38000.jpg",
        "genres": "Экшен, Сверхъестественное, Исторический",
        "year": "2019",
        "season": "Весна 2019",
        "answers": [
            "клинок рассекающий демонов", "demon slayer", "kimetsu no yaiba", "крд",
            "клинок", "клинок демонов", "demonslayer", "kimetsunoyaiba"
        ]
    },
    {
        "id": "jujutsu_kaisen",
        "title": "Магическая битва (Jujutsu Kaisen)",
        "canonical": "Магическая битва",
        "image_url": "https://shikimori.one/system/animes/original/40748.jpg",
        "genres": "Экшен, Фэнтези, Школа, Сверхъестественное",
        "year": "2020",
        "season": "Осень 2020",
        "answers": [
            "магическая битва", "jujutsu kaisen", "магичка", "jjk", "магическая битва",
            "жужутсу кайсен", "магическая", "дзюдзюцу кайсен", "jujutsukaisen"
        ]
    },
    {
        "id": "chainsaw_man",
        "title": "Человек-бензопила (Chainsaw Man)",
        "canonical": "Человек-бензопила",
        "image_url": "https://shikimori.one/system/animes/original/44511.jpg",
        "genres": "Экшен, Сверхъестественное, Ужасы",
        "year": "2022",
        "season": "Осень 2022",
        "answers": [
            "человек бензопила", "человек-бензопила", "chainsaw man", "бензопила",
            "бензопильщик", "человек бензопила", "chainsawman", "пила"
        ]
    },
    {
        "id": "steins_gate",
        "title": "Врата Штейна (Steins;Gate)",
        "canonical": "Врата Штейна",
        "image_url": "https://shikimori.one/system/animes/original/9253.jpg",
        "genres": "Фантастика, Триллер, Драма",
        "year": "2011",
        "season": "Весна 2011",
        "answers": [
            "врата штейна", "steins gate", "steins;gate", "врата штейнера",
            "штайнс гейт", "врата", "steinsgate"
        ]
    },
    {
        "id": "frieren",
        "title": "Провожающая в последний путь Фрирен (Frieren)",
        "canonical": "Фрирен",
        "image_url": "https://shikimori.one/system/animes/original/52991.jpg",
        "genres": "Приключения, Драма, Фэнтези",
        "year": "2023",
        "season": "Осень 2023",
        "answers": [
            "фрирен", "frieren", "провожающая в последний путь фрирен",
            "sousou no frieren", "фрирен провожающая в последний путь"
        ]
    },
    {
        "id": "cyberpunk_edgerunners",
        "title": "Киберпанк: Бегущие по краю (Cyberpunk: Edgerunners)",
        "canonical": "Киберпанк Бегущие по краю",
        "image_url": "https://shikimori.one/system/animes/original/42310.jpg",
        "genres": "Экшен, Киберпанк, Фантастика, Драма",
        "year": "2022",
        "season": "Осень 2022",
        "answers": [
            "киберпанк", "cyberpunk", "cyberpunk edgerunners", "бегущие по краю",
            "киберпанк бегущие по краю", "эджраннеры", "edgerunners"
        ]
    },
    {
        "id": "tokyo_ghoul",
        "title": "Токийский гуль (Tokyo Ghoul)",
        "canonical": "Токийский гуль",
        "image_url": "https://shikimori.one/system/animes/original/22319.jpg",
        "genres": "Экшен, Драма, Ужасы, Психологическое",
        "year": "2014",
        "season": "Лето 2014",
        "answers": [
            "токийский гуль", "tokyo ghoul", "гуль", "токийскийгуль", "tokyoghouil"
        ]
    },
    {
        "id": "evangelion",
        "title": "Евангелион (Neon Genesis Evangelion)",
        "canonical": "Евангелион",
        "image_url": "https://shikimori.one/system/animes/original/30.jpg",
        "genres": "Меха, Психологическое, Драма, Фантастика",
        "year": "1995",
        "season": "Осень 1995",
        "answers": [
            "евангелион", "evangelion", "ева", "neon genesis evangelion",
            "нге", "nge", "евангелион нового поколения"
        ]
    },
    {
        "id": "naruto",
        "title": "Наруто (Naruto)",
        "canonical": "Наруто",
        "image_url": "https://shikimori.one/system/animes/original/20.jpg",
        "genres": "Экшен, Приключения, Фэнтези, Ниндзя",
        "year": "2002",
        "season": "Осень 2002",
        "answers": [
            "наруто", "naruto", "наруто ураганные хроники", "шиппуден", "shippuden"
        ]
    },
    {
        "id": "one_piece",
        "title": "Ван-Пис / Большой куш (One Piece)",
        "canonical": "Ван Пис",
        "image_url": "https://shikimori.one/system/animes/original/21.jpg",
        "genres": "Приключения, Комедия, Фэнтези, Сёнэн",
        "year": "1999",
        "season": "Осень 1999",
        "answers": [
            "ван пис", "one piece", "ванпис", "большой куш", "onepiece", "луффи"
        ]
    },
    {
        "id": "bleach",
        "title": "Блич (Bleach)",
        "canonical": "Блич",
        "image_url": "https://shikimori.one/system/animes/original/269.jpg",
        "genres": "Экшен, Приключения, Сверхъестественное",
        "year": "2004",
        "season": "Осень 2004",
        "answers": [
            "блич", "bleach", "ичиго"
        ]
    },
    {
        "id": "code_geass",
        "title": "Код Гиас (Code Geass)",
        "canonical": "Код Гиас",
        "image_url": "https://shikimori.one/system/animes/original/1575.jpg",
        "genres": "Меха, Военное, Драма, Фантастика",
        "year": "2006",
        "season": "Осень 2006",
        "answers": [
            "код гиас", "code geass", "лелуш", "код гиасс", "codegeass"
        ]
    },
    {
        "id": "re_zero",
        "title": "Re:Zero — Жизнь с нуля в другом мире",
        "canonical": "Re:Zero",
        "image_url": "https://shikimori.one/system/animes/original/31240.jpg",
        "genres": "Драма, Фэнтези, Исекай, Триллер",
        "year": "2016",
        "season": "Весна 2016",
        "answers": [
            "re zero", "re:zero", "ре зеро", "жизнь с нуля", "жизнь с нуля в другом мире",
            "rezero", "резеро"
        ]
    },
    {
        "id": "vinland_saga",
        "title": "Сага о Винланде (Vinland Saga)",
        "canonical": "Сага о Винланде",
        "image_url": "https://shikimori.one/system/animes/original/37521.jpg",
        "genres": "Экшен, Приключения, Исторический, Драма",
        "year": "2019",
        "season": "Лето 2019",
        "answers": [
            "сага о винланде", "vinland saga", "винланд", "торфинн", "vinlandsaga"
        ]
    },
    {
        "id": "oshi_no_ko",
        "title": "Звёздное дитя (Oshi no Ko)",
        "canonical": "Звездное дитя",
        "image_url": "https://shikimori.one/system/animes/original/52034.jpg",
        "genres": "Драма, Шоу-бизнес, Сверхъестественное",
        "year": "2023",
        "season": "Весна 2023",
        "answers": [
            "звездное дитя", "звёздное дитя", "oshi no ko", "оши но ко", "oshinoko", "ай хосино"
        ]
    },
    {
        "id": "bocchi_the_rock",
        "title": "Одинокий рокер! (Bocchi the Rock!)",
        "canonical": "Одинокий рокер",
        "image_url": "https://shikimori.one/system/animes/original/47917.jpg",
        "genres": "Комедия, Музыка, Повседневность",
        "year": "2022",
        "season": "Осень 2022",
        "answers": [
            "боччи", "bocchi the rock", "одинокий рокер", "bocchi", "боччи зе рок", "bocchitherock"
        ]
    },
    {
        "id": "violet_evergarden",
        "title": "Вайолет Эвергарден (Violet Evergarden)",
        "canonical": "Вайолет Эвергарден",
        "image_url": "https://shikimori.one/system/animes/original/33352.jpg",
        "genres": "Драма, Фэнтези, Повседневность",
        "year": "2018",
        "season": "Зима 2018",
        "answers": [
            "вайолет эвергарден", "violet evergarden", "вайолет", "эвергарден", "violetevergarden"
        ]
    },
    {
        "id": "sword_art_online",
        "title": "Мастера Меча Онлайн (Sword Art Online / SAO)",
        "canonical": "Мастера Меча Онлайн",
        "image_url": "https://shikimori.one/system/animes/original/11757.jpg",
        "genres": "Экшен, Приключения, Фэнтези, Игры",
        "year": "2012",
        "season": "Лето 2012",
        "answers": [
            "сао", "sao", "мастера меча онлайн", "sword art online", "мастера меча",
            "кирито", "swordartonline"
        ]
    },
    {
        "id": "fullmetal_alchemist",
        "title": "Стальной алхимик (Fullmetal Alchemist)",
        "canonical": "Стальной алхимик",
        "image_url": "https://shikimori.one/system/animes/original/5114.jpg",
        "genres": "Экшен, Приключения, Драма, Фэнтези",
        "year": "2009",
        "season": "Весна 2009",
        "answers": [
            "стальной алхимик", "fullmetal alchemist", "алхимик", "fma", "братство",
            "fullmetal alchemist brotherhood", "fullmetalalchemist"
        ]
    },
    {
        "id": "no_game_no_life",
        "title": "Нет игры — нет жизни (No Game No Life)",
        "canonical": "Нет игры нет жизни",
        "image_url": "https://shikimori.one/system/animes/original/19815.jpg",
        "genres": "Комедия, Фэнтези, Игры, Исекай",
        "year": "2014",
        "season": "Весна 2014",
        "answers": [
            "нет игры нет жизни", "no game no life", "нгнл", "ngnl", "но гейм но лайф", "nogamenolife"
        ]
    },
    {
        "id": "spirited_away",
        "title": "Унесённые призраками (Spirited Away)",
        "canonical": "Унесённые призраками",
        "image_url": "https://shikimori.one/system/animes/original/199.jpg",
        "genres": "Приключения, Сверхъестественное, Миядзаки",
        "year": "2001",
        "season": "Лето 2001",
        "answers": [
            "унесенные призраками", "унесённые призраками", "spirited away",
            "сен и тихиро", "тихиро", "spiritedaway"
        ]
    },
    {
        "id": "your_name",
        "title": "Твоё имя (Your Name / Kimi no Na wa)",
        "canonical": "Твоё имя",
        "image_url": "https://shikimori.one/system/animes/original/32281.jpg",
        "genres": "Драма, Романтика, Сверхъестественное, Синкай",
        "year": "2016",
        "season": "Лето 2016",
        "answers": [
            "твое имя", "твоё имя", "your name", "kimi no na wa", "kimi no nawa", "yourname"
        ]
    }
]

def generate_masked_hint(title: str) -> str:
    """
    Creates an aesthetic masked hint.
    E.g. "Атака титанов" -> "А _ _ _ а  т _ _ _ _ в"
    Preserves first and last letter of each word of length >= 3.
    """
    words = title.split()
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
