import os
import sys
from dotenv import load_dotenv

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Load environment variables from .env if present
load_dotenv(os.path.join(BASE_DIR, ".env"))

API_ID_RAW = os.getenv("TELEGRAM_API_ID", "39361099").strip()
API_HASH = os.getenv("TELEGRAM_API_HASH", "fb78e6edaec2381e33a6f7435df3094f").strip()
SESSION_NAME = os.getenv("SESSION_NAME", "userbot_session").strip()
COMMAND_PREFIX = os.getenv("COMMAND_PREFIX", ".").strip()
KERU_BOT_TOKEN = os.getenv("KERU_BOT_TOKEN", "8905001669:AAF7ZpBvNvTsJoXalnXio-TjYJcEjfqfX9A").strip()
_raw_key = os.getenv("PROXYAPI_KEY", "").strip()
if not _raw_key or _raw_key.startswith("sk-JDq7"):
    PROXYAPI_KEY = "sk-YwKlpXZJYYpZzdamjy30Znf3b3wSju09fKQ0YnnW5jh2lX1h"
else:
    PROXYAPI_KEY = _raw_key

KERU_API_URL = os.getenv("KERU_API_URL", "https://api.zexkora.cc/v1/chat/completions").strip()
if "proxyapi.ru" in KERU_API_URL:
    KERU_API_URL = "https://api.zexkora.cc/v1/chat/completions"

KERU_MODEL = "deepseek-v4-flash"

# 24/7 Server Tuning Settings
FLOOD_SLEEP_THRESHOLD = int(os.getenv("FLOOD_SLEEP_THRESHOLD", "120"))
LOG_DIR = os.getenv("LOG_DIR", os.path.join(BASE_DIR, "logs"))
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
LOG_MAX_BYTES = int(os.getenv("LOG_MAX_BYTES", str(10 * 1024 * 1024)))  # 10 MB per file
LOG_BACKUP_COUNT = int(os.getenv("LOG_BACKUP_COUNT", "5"))               # Keep up to 5 rotated log files

def validate_config() -> tuple[int, str]:
    """Validates configuration parameters and returns (api_id, api_hash)."""
    if not API_ID_RAW or not API_HASH:
        print("\n[ERROR] Telegram API credentials are missing!")
        print("Please set TELEGRAM_API_ID and TELEGRAM_API_HASH in your .env file.")
        print("You can obtain them for free at https://my.telegram.org (under 'API development tools').\n")
        sys.exit(1)

    try:
        api_id = int(API_ID_RAW)
    except ValueError:
        print(f"\n[ERROR] Invalid TELEGRAM_API_ID: '{API_ID_RAW}'. It must be an integer.\n")
        sys.exit(1)

    return api_id, API_HASH
