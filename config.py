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
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "AIzaSyApl0JZ3L_rBfcVh5sMD7-gLJ5r3oQJ42g").strip()
PROXYAPI_KEY = os.getenv("PROXYAPI_KEY", "sk-JDq7q3OebJRruvZrV5ho4tCOp1DPHtkS").strip()

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
