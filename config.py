import os
import logging
import warnings
from pathlib import Path
from dotenv import load_dotenv

# Suppress LibreSSL warning on macOS Python 3.9
warnings.filterwarnings("ignore", message="urllib3 v2 only supports OpenSSL")

# Load .env file
load_dotenv()

# Logging setup
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=getattr(logging, LOG_LEVEL, logging.INFO)
)
logger = logging.getLogger("MediaDownloaderBot")

# Bot credentials
BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()

if not BOT_TOKEN:
    logger.warning("BOT_TOKEN is not set in environment or .env file! Bot will fail to start until configured.")

# Access control (optional)
_allowed_users_raw = os.getenv("ALLOWED_USERS", "").strip()
if _allowed_users_raw:
    ALLOWED_USERS = {int(uid.strip()) for uid in _allowed_users_raw.split(",") if uid.strip().isdigit()}
else:
    ALLOWED_USERS = set()

# Cookies for authenticated extraction (Instagram / TikTok stories)
COOKIES_FILE = os.getenv("COOKIES_FILE", "cookies.txt").strip()
if COOKIES_FILE and not os.path.isabs(COOKIES_FILE):
    COOKIES_FILE = str(Path(__file__).parent / COOKIES_FILE)

# Download parameters
MAX_FILE_SIZE_MB = int(os.getenv("MAX_FILE_SIZE_MB", "50"))
MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024

TEMP_DIR = os.getenv("TEMP_DIR", "downloads")
if not os.path.isabs(TEMP_DIR):
    TEMP_DIR = str(Path(__file__).parent / TEMP_DIR)

# Ensure temp directory exists
os.makedirs(TEMP_DIR, exist_ok=True)
