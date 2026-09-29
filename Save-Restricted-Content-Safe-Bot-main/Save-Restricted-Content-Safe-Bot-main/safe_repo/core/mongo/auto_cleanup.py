"""Auto Session Cleanup — TTL index on sessions collection + cleanup_expired_sessions()."""
import os
import json
import asyncio
from datetime import datetime, timezone, timedelta

from safe_repo.core.mongo.mongo_client import get_mongo_db, is_mongo_available

STORAGE = os.path.join(os.path.dirname(__file__), "sessions.json")

SESSION_TTL_SECONDS = 86400  # 24 hours default TTL


def _read():
    if not os.path.exists(STORAGE):
        return {}
    try:
        with open(STORAGE, "r") as f:
            return json.load(f)
    except Exception:
        return {}


def _write(data):
    try:
        with open(STORAGE, "w") as f:
            json.dump(data, f, default=str)
    except Exception:
        pass


def _get_coll():
    db = get_mongo_db()
    if db is None:
        return None
    return db["sessions"]


def ensure_ttl_index(ttl_seconds=SESSION_TTL_SECONDS):
    """Create a TTL index on the sessions collection (idempotent)."""
    if not is_mongo_available():
        return False
    coll = _get_coll()
    if coll is None:
        return False
    try:
        coll.create_index("expire_at", expireAfterSeconds=ttl_seconds)
        return True
    except Exception:
        return False


async def cleanup_expired_sessions(ttl_seconds=SESSION_TTL_SECONDS):
    """Remove expired sessions. Primary: MongoDB TTL. Fallback: JSON file."""
    cutoff = datetime.now(timezone.utc) - timedelta(seconds=ttl_seconds)

    if is_mongo_available():
        coll = _get_coll()
        if coll is not None:
            result = await coll.delete_many({"expire_at": {"$lte": datetime.now(timezone.utc)}})
            return result.deleted_count

    data = await asyncio.to_thread(_read)
    removed = 0
    for key in list(data.keys()):
        entry = data.get(key, {})
        try:
            expire_at = datetime.fromisoformat(entry.get("expire_at", "")).replace(tzinfo=timezone.utc)
            if expire_at <= datetime.now(timezone.utc):
                data.pop(key, None)
                removed += 1
        except Exception:
            continue
    if removed:
        await asyncio.to_thread(_write, data)
    return removed


async def set_session_expiry(user_id, ttl_seconds=SESSION_TTL_SECONDS):
    """Set a session's expire_at timestamp for TTL purposes."""
    user_id = str(user_id)
    expire_at = datetime.now(timezone.utc) + timedelta(seconds=ttl_seconds)
    data = await asyncio.to_thread(_read)
    data.setdefault(user_id, {})
    data[user_id]["expire_at"] = expire_at.isoformat()
    await asyncio.to_thread(_write, data)
    if is_mongo_available():
        coll = _get_coll()
        if coll is not None:
            await coll.update_one(
                {"user_id": user_id},
                {"$set": {"user_id": user_id, "expire_at": expire_at}},
                upsert=True,
            )
    return True


def _run_async(coro):
    """Sync wrapper for Flask route usage."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()