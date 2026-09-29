"""Download Statistics — track views/downloads per media token."""
import os
import json
import asyncio
from datetime import datetime, timezone, timedelta

from safe_repo.core.mongo.mongo_client import get_mongo_db, is_mongo_available

STORAGE = os.path.join(os.path.dirname(__file__), "download_stats.json")


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
    return db["download_stats"]


def _serialize(doc):
    if doc is None:
        return None
    doc = dict(doc)
    doc.pop("_id", None)
    return doc


async def increment_views(token):
    """Increment view/download count for a media token."""
    token = str(token)
    now = datetime.now(timezone.utc)
    today = now.strftime("%Y-%m-%d")

    # JSON
    data = await asyncio.to_thread(_read)
    entry = data.setdefault(token, {
        "token": token,
        "views": 0,
        "completion_count": 0,
        "daily": {},
        "last_viewed": None,
    })
    entry["views"] = entry.get("views", 0) + 1
    entry["daily"][today] = entry["daily"].get(today, 0) + 1
    entry["last_viewed"] = now.isoformat()
    await asyncio.to_thread(_write, data)

    # MongoDB
    if is_mongo_available():
        coll = _get_coll()
        if coll is not None:
            await coll.update_one(
                {"token": token},
                {
                    "$inc": {"views": 1, f"daily.{today}": 1},
                    "$set": {"token": token, "last_viewed": now},
                },
                upsert=True,
            )
    return True


async def get_top_downloads(limit=20):
    """Return top downloaded media tokens."""
    if is_mongo_available():
        coll = _get_coll()
        if coll is not None:
            cursor = coll.find({}).sort("views", -1).limit(limit)
            docs = await cursor.to_list(length=limit)
            return [_serialize(d) for d in docs]

    data = await asyncio.to_thread(_read)
    sorted_entries = sorted(data.values(), key=lambda x: x.get("views", 0), reverse=True)
    return sorted_entries[:limit]


async def get_media_stats(token):
    """Return stats for a specific media token."""
    token = str(token)
    if is_mongo_available():
        coll = _get_coll()
        if coll is not None:
            doc = await coll.find_one({"token": token})
            if doc:
                return _serialize(doc)

    data = await asyncio.to_thread(_read)
    return data.get(token)


async def update_completion_count(token):
    """Increment the completion count for a media token."""
    token = str(token)
    now = datetime.now(timezone.utc)
    today = now.strftime("%Y-%m-%d")

    # JSON
    data = await asyncio.to_thread(_read)
    entry = data.setdefault(token, {
        "token": token,
        "views": 0,
        "completion_count": 0,
        "daily": {},
        "last_viewed": None,
    })
    entry["completion_count"] = entry.get("completion_count", 0) + 1
    entry["last_viewed"] = now.isoformat()
    await asyncio.to_thread(_write, data)

    # MongoDB
    if is_mongo_available():
        coll = _get_coll()
        if coll is not None:
            await coll.update_one(
                {"token": token},
                {
                    "$inc": {"completion_count": 1},
                    "$set": {"token": token, "last_viewed": now},
                },
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