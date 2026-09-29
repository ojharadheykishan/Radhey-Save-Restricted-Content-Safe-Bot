"""Chat-specific Settings — get/update chat preferences."""
import os
import json
import asyncio
from datetime import datetime, timezone

from safe_repo.core.mongo.mongo_client import get_mongo_db, is_mongo_available

STORAGE = os.path.join(os.path.dirname(__file__), "chat_settings.json")


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
    return db["chat_settings"]


def _serialize(doc):
    if doc is None:
        return None
    doc = dict(doc)
    doc.pop("_id", None)
    return doc


async def get_chat_settings(chat_id):
    """Return settings for a chat. Primary: MongoDB. Fallback: JSON file."""
    chat_id = str(chat_id)
    if is_mongo_available():
        coll = _get_coll()
        if coll is not None:
            doc = await coll.find_one({"chat_id": chat_id})
            if doc:
                return _serialize(doc)

    data = await asyncio.to_thread(_read)
    return data.get(chat_id)


async def update_chat_settings(chat_id, **kwargs):
    """Update chat settings (merge with existing)."""
    chat_id = str(chat_id)
    kwargs["updated_at"] = datetime.now(timezone.utc)

    # JSON
    data = await asyncio.to_thread(_read)
    existing = data.get(chat_id, {})
    existing.update(kwargs)
    data[chat_id] = existing
    await asyncio.to_thread(_write, data)

    # MongoDB
    if is_mongo_available():
        coll = _get_coll()
        if coll is not None:
            await coll.update_one(
                {"chat_id": chat_id},
                {"$set": {"chat_id": chat_id, **kwargs}},
                upsert=True,
            )
    return True


async def set_chat_preference(chat_id, key, value):
    """Set a single chat preference."""
    return await update_chat_settings(chat_id, **{key: value})


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