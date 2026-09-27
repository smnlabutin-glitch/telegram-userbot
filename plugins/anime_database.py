import random
import re

ANIME_DATASET = [
    {
        "id": "attack_on_titan",
        "title": "Атака титанов (Attack on Titan)",
        "canonical": "Атака титанов",
        "image_url": "https://media.kitsu.app/episodes/thumbnails/104938/original.jpg",
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
        "image_url": "https://media.kitsu.app/episodes/thumbnails/24569/original.jpg",
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
        "image_url": "https://media.kitsu.app/episodes/thumbnails/257362/original.jpg",
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
        "image_url": "https://media.kitsu.app/episodes/thumbnails/246946/original.jpg",
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
        "image_url": "https://media.kitsu.app/episodes/thumbnails/277464/original.png",
        "genres": "Экшен, Сверхъестественное, Сёнен",
        "year": "2020",
        "season": "Осень 2020",
        "answers": [
            "магическая битва", "jujutsu kaisen", "jjk", "магичка", "битва магов", "jujutsukaisen"
        ]
    },
    {
        "id": "chainsaw_man",
        "title": "Человек-бензопила (Chainsaw Man)",
        "canonical": "Человек бензопила",
        "image_url": "https://s4.anilist.co/file/anilistcdn/media/anime/banner/127230-o8IRwCGVr9KW.jpg",
        "genres": "Экшен, Сверхъестественное, Ужасы",
        "year": "2022",
        "season": "Осень 2022",
        "answers": [
            "человек бензопила", "человек-бензопила", "chainsaw man", "бензопила", "пила",
            "chainsawman"
        ]
    },
    {
        "id": "steins_gate",
        "title": "Врата Штейна (Steins;Gate)",
        "canonical": "Врата Штейна",
        "image_url": "https://media.kitsu.app/episodes/thumbnails/86680/original.jpg",
        "genres": "Фантастика, Триллер, Драма",
        "year": "2011",
        "season": "Весна 2011",
        "answers": [
            "врата штейна", "steins gate", "steins;gate", "врата штайнера", "штайн",
            "steinsgate", "калитка"
        ]
    },
    {
        "id": "frieren",
        "title": "Провожающая в последний путь Фрирен (Frieren)",
        "canonical": "Фрирен",
        "image_url": "https://media.kitsu.app/episode/353471/thumbnail/586ff8f159af3cefedfe7c48d454c982.png",
        "genres": "Фэнтези, Приключения, Драма",
        "year": "2023",
        "season": "Осень 2023",
        "answers": [
            "фрирен", "frieren", "провожающая в последний путь фрирен", "sousou no frieren",
            "провожающая фрирен"
        ]
    },
    {
        "id": "cyberpunk_edgerunners",
        "title": "Киберпанк: Бегущие по краю (Cyberpunk: Edgerunners)",
        "canonical": "Киберпанк",
        "image_url": "https://s4.anilist.co/file/anilistcdn/media/anime/banner/120377-c15oLS8CA31s.jpg",
        "genres": "Экшен, Киберпанк, Фантастика, Драма",
        "year": "2022",
        "season": "Осень 2022",
        "answers": [
            "киберпанк", "cyberpunk", "edgerunners", "бегущие по краю", "cyberpunk edgerunners",
            "cyberpunk 2077"
        ]
    },
    {
        "id": "tokyo_ghoul",
        "title": "Токийский гуль (Tokyo Ghoul)",
        "canonical": "Токийский гуль",
        "image_url": "https://media.kitsu.app/episodes/thumbnails/116052/original.jpg",
        "genres": "Экшен, Ужасы, Драма, Мистика",
        "year": "2014",
        "season": "Лето 2014",
        "answers": [
            "токийский гуль", "tokyo ghoul", "гуль", "дед инсайд", "tokyoghouil", "tokyogoul"
        ]
    },
    {
        "id": "evangelion",
        "title": "Евангелион (Neon Genesis Evangelion)",
        "canonical": "Евангелион",
        "image_url": "https://s4.anilist.co/file/anilistcdn/media/anime/banner/30-gEMoHHIqxDgN.jpg",
        "genres": "Меха, Психологическое, Драма, Фантастика",
        "year": "1995",
        "season": "Осень 1995",
        "answers": [
            "евангелион", "evangelion", "eva", "neon genesis evangelion", "ева", "нге"
        ]
    },
    {
        "id": "naruto",
        "title": "Наруто (Naruto)",
        "canonical": "Наруто",
        "image_url": "https://media.kitsu.app/episodes/thumbnails/105967/original.jpeg",
        "genres": "Экшен, Приключения, Сёнен, Ниндзя",
        "year": "2002",
        "season": "Осень 2002",
        "answers": [
            "наруто", "naruto", "ураганные хроники", "шиппуден", "shippuden"
        ]
    },
    {
        "id": "one_piece",
        "title": "Ван Пис (One Piece)",
        "canonical": "Ван Пис",
        "image_url": "https://media.kitsu.app/episodes/thumbnails/103482/original.jpg",
        "genres": "Экшен, Приключения, Фэнтези, Пираты",
        "year": "1999",
        "season": "Осень 1999",
        "answers": [
            "ван пис", "one piece", "ванпис", "onepiece", "луффи"
        ]
    },
    {
        "id": "bleach",
        "title": "Блич (Bleach)",
        "canonical": "Блич",
        "image_url": "https://media.kitsu.app/episodes/thumbnails/106778/original.jpg",
        "genres": "Экшен, Сверхъестественное, Сёнен",
        "year": "2004",
        "season": "Осень 2004",
        "answers": [
            "блич", "bleach", "синигами", "ichigo"
        ]
    },
    {
        "id": "code_geass",
        "title": "Код Гиас (Code Geass)",
        "canonical": "Код Гиас",
        "image_url": "https://media.kitsu.app/episodes/thumbnails/25771/original.jpg",
        "genres": "Меха, Военное, Детектив, Драма",
        "year": "2006",
        "season": "Осень 2006",
        "answers": [
            "код гиас", "code geass", "лелуш", "гиас", "codegeass"
        ]
    },
    {
        "id": "re_zero",
        "title": "Re:Zero — Жизнь с нуля в другом мире",
        "canonical": "Re Zero",
        "image_url": "https://s4.anilist.co/file/anilistcdn/media/anime/banner/21355-f9SjOfEJMk5P.jpg",
        "genres": "Исекай, Драма, Фэнтези, Триллер",
        "year": "2016",
        "season": "Весна 2016",
        "answers": [
            "re zero", "re:zero", "ре зеро", "жизнь с нуля", "жизнь с чистого листа", "резеро"
        ]
    },
    {
        "id": "vinland_saga",
        "title": "Сага о Винланде (Vinland Saga)",
        "canonical": "Сага о Винланде",
        "image_url": "https://media.kitsu.app/episodes/thumbnails/250571/original.jpg",
        "genres": "Экшен, Исторический, Приключения, Драма",
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
        "image_url": "https://s4.anilist.co/file/anilistcdn/media/anime/banner/150672-ISwoA0eS722H.jpg",
        "genres": "Драма, Музыка, Мистика, Сверхъестественное",
        "year": "2023",
        "season": "Весна 2023",
        "answers": [
            "звездное дитя", "звёздное дитя", "oshi no ko", "оши но ко", "oshinoko"
        ]
    },
    {
        "id": "bocchi_the_rock",
        "title": "Рок-тихоня! (Bocchi the Rock!)",
        "canonical": "Рок тихоня",
        "image_url": "https://media.kitsu.app/episode/335115/thumbnail/9cdd76f0cad3ef9bb37cfe3eadd99e60.jpg",
        "genres": "Комедия, Музыка, Повседневность",
        "year": "2022",
        "season": "Осень 2022",
        "answers": [
            "рок тихоня", "рок-тихоня", "bocchi the rock", "ботти", "боччи", "bocchi", "bocchitherock"
        ]
    },
    {
        "id": "violet_evergarden",
        "title": "Вайолет Эвергарден (Violet Evergarden)",
        "canonical": "Вайолет Эвергарден",
        "image_url": "https://media.kitsu.app/episodes/thumbnails/235467/original.jpg",
        "genres": "Драма, Фэнтези, Повседневность",
        "year": "2018",
        "season": "Зима 2018",
        "answers": [
            "вайолет эвергарден", "violet evergarden", "вайолет", "эвергарден", "violetevergarden"
        ]
    },
    {
        "id": "sword_art_online",
        "title": "Мастера Меча Онлайн (Sword Art Online)",
        "canonical": "Мастера Меча Онлайн",
        "image_url": "https://media.kitsu.app/episodes/thumbnails/97395/original.jpg",
        "genres": "Экшен, Приключения, Фэнтези, Игра",
        "year": "2012",
        "season": "Лето 2012",
        "answers": [
            "мастера меча онлайн", "sword art online", "sao", "сао", "мастера меча", "swordartonline"
        ]
    },
    {
        "id": "fullmetal_alchemist",
        "title": "Стальной алхимик (Fullmetal Alchemist: Brotherhood)",
        "canonical": "Стальной алхимик",
        "image_url": "https://media.kitsu.app/episodes/thumbnails/3015/original.jpg",
        "genres": "Экшен, Приключения, Драма, Фэнтези",
        "year": "2009",
        "season": "Весна 2009",
        "answers": [
            "стальной алхимик", "fullmetal alchemist", "fma", "алхимик", "братство",
            "fullmetalalchemist"
        ]
    },
    {
        "id": "no_game_no_life",
        "title": "Нет игры — нет жизни (No Game No Life)",
        "canonical": "Нет игры нет жизни",
        "image_url": "https://media.kitsu.app/episodes/thumbnails/159084/original.jpg",
        "genres": "Комедия, Фэнтези, Исекай, Игры",
        "year": "2014",
        "season": "Весна 2014",
        "answers": [
            "нет игры нет жизни", "нет игры - нет жизни", "no game no life", "ngnl",
            "но гейм но лайф", "nogamenolife"
        ]
    },
    {
        "id": "spirited_away",
        "title": "Унесённые призраками (Spirited Away)",
        "canonical": "Унесенные призраками",
        "image_url": "https://s4.anilist.co/file/anilistcdn/media/anime/banner/199-Sm2RU5PSqw7T.jpg",
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
        "image_url": "https://s4.anilist.co/file/anilistcdn/media/anime/banner/21519-1ayMXgNlmByb.jpg",
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
