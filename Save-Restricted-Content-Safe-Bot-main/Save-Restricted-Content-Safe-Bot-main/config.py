# safe_repo
# Note if you are trying to deploy on vps then directly fill values in (""
import os

API_HASH = os.environ.get("API_HASH", "").strip()
API_ID = int(os.environ.get("API_ID") or "0")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "").strip()
CHANNEL_ID = -1003818713803
LOG_GROUP = -1005121908460
CLONE_LOG_CHANNEL = -1003886456761
# Keep this channel private and add only admins/lifetime members.
PREMIUM_ARCHIVE_CHANNEL = int(os.environ.get("PREMIUM_ARCHIVE_CHANNEL") or CLONE_LOG_CHANNEL)
# Public channel where cloned media is also posted so users get an
# MX Player / VLC streamable link (t.me/Link09660/MSGID)
STREAM_CHANNEL = -1004332477626
STREAM_CHANNEL_USERNAME = "Link09660"
# Owner(s) of the bot. Keep as a list for filters.user compatibility.
OWNER_ID = [8552899459]

# MongoDB connection string (optional). When set, the app uses MongoDB as primary
# storage with JSON files as automatic fallback. Set via env var MONGO_DB.
# NOTE: never hardcode the production URI here. A fallback string made local runs
# and the test suite connect to the live database, where catalog rewrites wiped
# saved links. Without this variable the app runs on the JSON fallback only.
MONGO_DB = os.environ.get("MONGO_DB", "").strip()


def validate_required_config():
    """Fail before bot startup when Telegram credentials are missing."""
    missing = [
        name
        for name, value in (
            ("API_ID", API_ID),
            ("API_HASH", API_HASH),
            ("BOT_TOKEN", BOT_TOKEN),
        )
        if not value
    ]
    if missing:
        raise RuntimeError(
            "Missing required environment variables: " + ", ".join(missing)
        )
