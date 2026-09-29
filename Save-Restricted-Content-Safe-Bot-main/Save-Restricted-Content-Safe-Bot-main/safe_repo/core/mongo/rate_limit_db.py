"""API Rate Limiting — track request counts per key with sliding window."""
import os
import json
import asyncio
import time
from datetime import datetime, timezone, timedelta

from safe_repo.core.mongo.mongo_client import get_mongo_db, is_mongo_available

STORAGE = os.path.join(os.path.dirname(__file__), "rate_limits.json")


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
    return db["rate_limits"]


def _serialize(doc):
    if doc is None:
        return None
    doc = dict(doc)
    doc.pop("_id", None)
    return doc


async def record_request(key):
    """Record a request for a given key."""
    key = str(key)
    now = datetime.now(timezone.utc)
    window_start = now - timedelta(seconds=60)

    # JSON
    data = await asyncio.to_thread(_read)
    entry = data.setdefault(key, {
        "key": key,
        "requests": [],
    })
    requests = entry.get("requests", [])
    # Remove old requests
    requests = [r for r in requests if datetime.fromisoformat(r).replace(tzinfo=timezone.utc) > window_start]
    requests.append(now.isoformat())
    entry["requests"] = requests
    await asyncio.to_thread(_write, data)

    # MongoDB
    if is_mongo_available():
        coll = _get_coll()
        if coll is not None:
            await coll.update_one(
                {"key": key},
                {
                    "$push": {"requests": now},
                    "$set": {"key": key, "last_request": now},
                },
                upsert=True,
            )
            # Clean up old entries
            await coll.update_one(
                {"key": key},
                {"$pull": {"requests": {"$lt": window_start}}},
            )
    return True


async def check_rate_limit(key, limit=60, window=60):
    """Check if a key has exceeded its rate limit."""
    key = str(key)
    now = datetime.now(timezone.utc)
    window_start = now - timedelta(seconds=window)

    if is_mongo_available():
        coll = _get_coll()
        if coll is not None:
            doc = await coll.find_one({"key": key})
            if doc:
                requests = doc.get("requests", [])
                # Filter to current window
                valid = [r for r in requests if r > window_start]
                count = len(valid)
                return {
                    "allowed": count < limit,
                    "count": count,
                    "limit": limit,
                    "window": window,
                    "reset_in": window - (now - max(valid)).total_seconds() if valid else window,
                }
            return {"allowed": True, "count": 0, "limit": limit, "window": window, "reset_in": window}

    data = await asyncio.to_thread(_read)
    entry = data.get(key)
    if not entry:
        return {"allowed": True, "count": 0, "limit": limit, "window": window, "reset_in": window}
    requests = entry.get("requests", [])
    valid = []
    for r in requests:
        try:
            ts = datetime.fromisoformat(r).replace(tzinfo=timezone.utc)
            if ts > window_start:
                valid.append(ts)
        except Exception:
            continue
    count = len(valid)
    return {
        "allowed": count < limit,
        "count": count,
        "limit": limit,
        "window": window,
        "reset_in": window - (now - max(valid)).total_seconds() if valid else window,
    }


async def reset_rate_limits():
    """Reset all rate limit counters."""
    if is_mongo_available():
        coll = _get_coll()
        if coll is not None:
            result = await coll.delete_many({})
            return result.deleted_count

    data = await asyncio.to_thread(_read)
    count = len(data)
    await asyncio.to_thread(_write, {})
    return count


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