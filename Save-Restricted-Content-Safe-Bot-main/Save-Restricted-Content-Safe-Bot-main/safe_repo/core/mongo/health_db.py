"""Bot Resource Monitoring — save and retrieve health metrics."""
import os
import json
import asyncio
from datetime import datetime, timezone, timedelta

from safe_repo.core.mongo.mongo_client import get_mongo_db, is_mongo_available

STORAGE = os.path.join(os.path.dirname(__file__), "health.json")


def _read():
    if not os.path.exists(STORAGE):
        return {"metrics": []}
    try:
        with open(STORAGE, "r") as f:
            return json.load(f)
    except Exception:
        return {"metrics": []}


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
    return db["health_metrics"]


def _serialize(doc):
    if doc is None:
        return None
    doc = dict(doc)
    doc.pop("_id", None)
    return doc


async def save_health_metric(metric_name, value):
    """Save a health metric value."""
    entry = {
        "metric_name": metric_name,
        "value": value,
        "timestamp": datetime.now(timezone.utc),
    }
    # JSON
    data = await asyncio.to_thread(_read)
    metrics = data.get("metrics", [])
    entry_json = dict(entry)
    entry_json["timestamp"] = entry["timestamp"].isoformat()
    metrics.append(entry_json)
    data["metrics"] = metrics
    await asyncio.to_thread(_write, data)
    # MongoDB
    if is_mongo_available():
        coll = _get_coll()
        if coll is not None:
            await coll.insert_one(entry)
    return True


async def get_health_history(metric_name, hours=24):
    """Return health metric history for the last N hours."""
    since = datetime.now(timezone.utc) - timedelta(hours=hours)
    if is_mongo_available():
        coll = _get_coll()
        if coll is not None:
            cursor = coll.find({
                "metric_name": metric_name,
                "timestamp": {"$gte": since},
            }).sort("timestamp", 1)
            docs = await cursor.to_list(length=10000)
            return [_serialize(d) for d in docs]

    data = await asyncio.to_thread(_read)
    metrics = data.get("metrics", [])
    result = []
    for m in metrics:
        if m.get("metric_name") != metric_name:
            continue
        try:
            ts = datetime.fromisoformat(m.get("timestamp", "")).replace(tzinfo=timezone.utc)
        except Exception:
            continue
        if ts >= since:
            result.append(m)
    return result


async def cleanup_old_metrics(days=7):
    """Remove health metrics older than N days."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    removed = 0

    if is_mongo_available():
        coll = _get_coll()
        if coll is not None:
            result = await coll.delete_many({"timestamp": {"$lt": cutoff}})
            removed = result.deleted_count

    data = await asyncio.to_thread(_read)
    metrics = data.get("metrics", [])
    new_metrics = []
    for m in metrics:
        try:
            ts = datetime.fromisoformat(m.get("timestamp", "")).replace(tzinfo=timezone.utc)
            if ts >= cutoff:
                new_metrics.append(m)
            else:
                removed += 1
        except Exception:
            new_metrics.append(m)
    if len(new_metrics) != len(metrics):
        data["metrics"] = new_metrics
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