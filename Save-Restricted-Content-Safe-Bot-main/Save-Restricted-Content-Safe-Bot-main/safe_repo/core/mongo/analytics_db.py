"""Usage Analytics — track bot usage events with MongoDB + JSON fallback."""
import os
import json
import asyncio
from datetime import datetime, timezone, timedelta

from safe_repo.core.mongo.mongo_client import get_mongo_db, is_mongo_available

STORAGE = os.path.join(os.path.dirname(__file__), "analytics.json")


def _read():
    if not os.path.exists(STORAGE):
        return {"events": []}
    try:
        with open(STORAGE, "r") as f:
            return json.load(f)
    except Exception:
        return {"events": []}


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
    return db["analytics"]


def _serialize(doc):
    if doc is None:
        return None
    doc = dict(doc)
    doc.pop("_id", None)
    return doc


async def log_event(event_type, user_id, metadata=None):
    """Log a usage event. Primary: MongoDB. Fallback: JSON file."""
    user_id = str(user_id)
    event = {
        "event_type": event_type,
        "user_id": user_id,
        "metadata": metadata or {},
        "timestamp": datetime.now(timezone.utc),
    }
    # JSON
    data = await asyncio.to_thread(_read)
    events = data.get("events", [])
    event_json = dict(event)
    event_json["timestamp"] = event["timestamp"].isoformat()
    events.append(event_json)
    data["events"] = events
    await asyncio.to_thread(_write, data)
    # MongoDB
    if is_mongo_available():
        coll = _get_coll()
        if coll is not None:
            await coll.insert_one(event)
    return True


async def get_analytics_summary(days=7):
    """Return summary of events in the last N days."""
    since = datetime.now(timezone.utc) - timedelta(days=days)
    summary = {"total_events": 0, "by_type": {}, "period_days": days}

    if is_mongo_available():
        coll = _get_coll()
        if coll is not None:
            cursor = coll.find({"timestamp": {"$gte": since}})
            docs = await cursor.to_list(length=100000)
            summary["total_events"] = len(docs)
            for doc in docs:
                etype = doc.get("event_type", "unknown")
                summary["by_type"][etype] = summary["by_type"].get(etype, 0) + 1
            return summary

    data = await asyncio.to_thread(_read)
    events = data.get("events", [])
    for ev in events:
        try:
            ts = datetime.fromisoformat(ev.get("timestamp", "")).replace(tzinfo=timezone.utc)
        except Exception:
            continue
        if ts >= since:
            summary["total_events"] += 1
            etype = ev.get("event_type", "unknown")
            summary["by_type"][etype] = summary["by_type"].get(etype, 0) + 1
    return summary


async def get_top_users(limit=10):
    """Return top users by event count."""
    if is_mongo_available():
        coll = _get_coll()
        if coll is not None:
            pipeline = [
                {"$group": {"_id": "$user_id", "count": {"$sum": 1}}},
                {"$sort": {"count": -1}},
                {"$limit": limit},
            ]
            docs = await coll.aggregate(pipeline).to_list(length=limit)
            return [{"user_id": int(d["_id"]), "count": d["count"]} for d in docs]

    data = await asyncio.to_thread(_read)
    events = data.get("events", [])
    counts = {}
    for ev in events:
        uid = ev.get("user_id")
        if uid:
            counts[uid] = counts.get(uid, 0) + 1
    sorted_users = sorted(counts.items(), key=lambda x: x[1], reverse=True)[:limit]
    return [{"user_id": int(uid), "count": cnt} for uid, cnt in sorted_users]


async def get_daily_stats(days=7):
    """Return daily event counts for the last N days."""
    since = datetime.now(timezone.utc) - timedelta(days=days)
    stats = {}

    if is_mongo_available():
        coll = _get_coll()
        if coll is not None:
            cursor = coll.find({"timestamp": {"$gte": since}})
            docs = await cursor.to_list(length=100000)
            for doc in docs:
                day = doc.get("timestamp").strftime("%Y-%m-%d") if hasattr(doc.get("timestamp"), "strftime") else str(doc.get("timestamp", ""))[:10]
                stats[day] = stats.get(day, 0) + 1
            return stats

    data = await asyncio.to_thread(_read)
    events = data.get("events", [])
    for ev in events:
        try:
            ts = datetime.fromisoformat(ev.get("timestamp", "")).replace(tzinfo=timezone.utc)
        except Exception:
            continue
        if ts >= since:
            day = ts.strftime("%Y-%m-%d")
            stats[day] = stats.get(day, 0) + 1
    return stats


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