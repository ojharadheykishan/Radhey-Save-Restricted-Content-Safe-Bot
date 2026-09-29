"""Cloud Session Backup — save/load userbot session data to MongoDB with JSON fallback."""
import os
import json
import asyncio
from datetime import datetime, timezone

from safe_repo.core.mongo.mongo_client import get_mongo_db, is_mongo_available

STORAGE = os.path.join(os.path.dirname(__file__), "cloud_sessions.json")


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
    return db["cloud_sessions"]


def _serialize(doc):
    if doc is None:
        return None
    doc = dict(doc)
    doc.pop("_id", None)
    return doc


async def save_cloud_session(user_id, session_data):
    """Save userbot session data. Primary: MongoDB. Fallback: JSON file."""
    user_id = str(user_id)
    entry = {
        "user_id": user_id,
        "session_data": session_data,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    # JSON
    data = await asyncio.to_thread(_read)
    data[user_id] = entry
    await asyncio.to_thread(_write, data)
    # MongoDB
    if is_mongo_available():
        coll = _get_coll()
        if coll is not None:
            await coll.update_one(
                {"user_id": user_id},
                {"$set": entry},
                upsert=True,
            )
    return True


async def load_cloud_session(user_id):
    """Load userbot session data. Primary: MongoDB. Fallback: JSON file."""
    user_id = str(user_id)
    if is_mongo_available():
        coll = _get_coll()
        if coll is not None:
            doc = await coll.find_one({"user_id": user_id})
            if doc:
                return _serialize(doc).get("session_data")
    data = await asyncio.to_thread(_read)
    entry = data.get(user_id)
    if entry:
        return entry.get("session_data")
    return None


async def delete_cloud_session(user_id):
    """Delete userbot session data. Primary: MongoDB. Fallback: JSON file."""
    user_id = str(user_id)
    data = await asyncio.to_thread(_read)
    data.pop(user_id, None)
    await asyncio.to_thread(_write, data)
    if is_mongo_available():
        coll = _get_coll()
        if coll is not None:
            await coll.delete_one({"user_id": user_id})
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