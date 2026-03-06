# safe_repo
# Note if you are trying to deploy on vps then directly fill values in ("")
import os

API_HASH = os.environ.get("API_HASH", "f150646c78f09b4f88bef191a22539c0")
API_ID = int(os.environ.get("API_ID", 26704085))
BOT_TOKEN = os.environ.get("BOT_TOKEN", "8564747078:AAF39Ekn22SZxQB7ShELURFel981IFhrmoM")
CHANNEL_ID = int(os.environ.get("CHANNEL_ID", -1003818713803))
LOG_GROUP = int(os.environ.get("LOG_GROUP", -1005121908460))
# Owner(s) of the bot. Keep as a list for filters.user compatibility.
OWNER_ID = list(map(int, os.environ.get("OWNER_ID", "8552899459").split(",")))

# MongoDB removed from this codebase; keep MONGO_DB for backwards compatibility
MONGO_DB = os.environ.get("MONGO_DB", "")
