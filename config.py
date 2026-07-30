import os

# --- Mandatory Environment Variables ---
API_ID = int(os.environ.get("API_ID", "0"))
API_HASH = os.environ.get("API_HASH", "")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")

# --- Owner & Admin Configuration ---
OWNER_ID = int(os.environ.get("OWNER_ID", "0"))
SUDO_USERS = (
    list(map(int, os.environ.get("SUDO_USERS", "").split()))
    if os.environ.get("SUDO_USERS")
    else [OWNER_ID]
)

# --- Database & Server Settings ---
MONGO_URL = os.environ.get("MONGO_URL", "")
CHANNEL_ID = int(os.environ.get("CHANNEL_ID", "0"))
LOG_CHANNEL = int(os.environ.get("LOG_CHANNEL", str(CHANNEL_ID)))
PORT = int(os.environ.get("PORT", "8080"))
COOKIES_FILE = os.environ.get("COOKIES_FILE", "youtube_cookies.txt")