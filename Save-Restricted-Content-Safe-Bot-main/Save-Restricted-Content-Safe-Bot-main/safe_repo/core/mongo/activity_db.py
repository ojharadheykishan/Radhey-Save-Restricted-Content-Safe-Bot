"""User Activity Timeline — log watched/downloaded/uploaded activities."""
import os
import json
import asyncio
from datetime import datetime, timezone, timedelta

from safe_repo.core.mongo.mongo_client import get_mongo_db, is_mongo_available

STORAGE = os.path.join(os.path.dirname(__file__), "activity.json")


def _read():
    if not os.path.exists(STORAGE):
        return {"activities": []}
    try:
        with open(STORAGE, "r") as f:
            return json.load(f)
    except Exception:
        return {"activities": []}


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
    return db["user_activity"]


def _serialize(doc):
    if doc is None:
        return None
    doc = dict(doc)
    doc.pop("_id", None)
    if "timestamp" in doc and hasattr(doc["timestamp"], "isoformat"):
        doc["timestamp"] = doc["timestamp"].isoformat()
    return doc


async def log_activity(user_id, action, target, metadata=None):
    """Log a user activity (watched/downloaded/uploaded)."""
    user_id = str(user_id)
    entry = {
        "user_id": user_id,
        "action": action,
        "target": target,
        "metadata": metadata or {},
        "timestamp": datetime.now(timezone.utc),
    }
    # JSON
    data = await asyncio.to_thread(_read)
    activities = data.get("activities", [])
    entry_json = dict(entry)
    entry_json["timestamp"] = entry["timestamp"].isoformat()
    activities.append(entry_json)
    data["activities"] = activities
    await asyncio.to_thread(_write, data)
    # MongoDB
    if is_mongo_available():
        coll = _get_coll()
        if coll is not None:
            await coll.insert_one(entry)
    return True


async def get_user_activity(user_id, limit=20):
    """Return recent activities for a user."""
    user_id = str(user_id)
    if is_mongo_available():
        coll = _get_coll()
        if coll is not None:
            cursor = coll.find({"user_id": user_id}).sort("timestamp", -1).limit(limit)
            docs = await cursor.to_list(length=limit)
            return [_serialize(d) for d in docs]

    data = await asyncio.to_thread(_read)
    activities = data.get("activities", [])
    filtered = [a for a in activities if a.get("user_id") == user_id]
    return filtered[-limit:]


async def clear_old_activity(days=30):
    """Remove activities older than N days."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    removed = 0

    if is_mongo_available():
        coll = _get_coll()
        if coll is not None:
            result = await coll.delete_many({"timestamp": {"$lt": cutoff}})
            removed = result.deleted_count

    data = await asyncio.to_thread(_read)
    activities = data.get("activities", [])
    new_activities = []
    for a in activities:
        try:
            ts = datetime.fromisoformat(a.get("timestamp", "")).replace(tzinfo=timezone.utc)
            if ts >= cutoff:
                new_activities.append(a)
            else:
                removed += 1
        except Exception:
            new_activities.append(a)
    if len(new_activities) != len(activities):
        data["activities"] = new_activities
        await asyncio.to_thread(_write, data)
    return removed


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