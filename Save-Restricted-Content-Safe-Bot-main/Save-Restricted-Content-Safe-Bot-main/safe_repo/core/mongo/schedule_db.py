"""Scheduled Auto-Copy — save user scheduled copy jobs."""
import os
import json
import asyncio
from datetime import datetime, timezone, timedelta

from safe_repo.core.mongo.mongo_client import get_mongo_db, is_mongo_available

STORAGE = os.path.join(os.path.dirname(__file__), "schedules.json")


def _read():
    if not os.path.exists(STORAGE):
        return {"schedules": []}
    try:
        with open(STORAGE, "r") as f:
            return json.load(f)
    except Exception:
        return {"schedules": []}


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
    return db["scheduled_copies"]


def _serialize(doc):
    if doc is None:
        return None
    doc = dict(doc)
    doc.pop("_id", None)
    return doc


async def create_schedule(user_id, chat_id, timeframe):
    """Create a scheduled copy job."""
    user_id = str(user_id)
    schedule = {
        "user_id": user_id,
        "chat_id": chat_id,
        "timeframe": timeframe,
        "active": True,
        "created_at": datetime.now(timezone.utc),
        "last_run": None,
    }
    # JSON
    data = await asyncio.to_thread(_read)
    schedules = data.get("schedules", [])
    schedules.append(schedule)
    data["schedules"] = schedules
    await asyncio.to_thread(_write, data)
    # MongoDB
    if is_mongo_available():
        coll = _get_coll()
        if coll is not None:
            await coll.insert_one(schedule)
    return schedule


async def get_active_schedules():
    """Return all active schedules."""
    if is_mongo_available():
        coll = _get_coll()
        if coll is not None:
            cursor = coll.find({"active": True})
            docs = await cursor.to_list(length=10000)
            return [_serialize(d) for d in docs]

    data = await asyncio.to_thread(_read)
    schedules = data.get("schedules", [])
    return [s for s in schedules if s.get("active")]


async def delete_schedule(schedule_id):
    """Delete a schedule by ID."""
    if is_mongo_available():
        coll = _get_coll()
        if coll is not None:
            result = await coll.delete_one({"_id": schedule_id})
            return result.deleted_count > 0

    try:
        idx = int(schedule_id)
        data = await asyncio.to_thread(_read)
        schedules = data.get("schedules", [])
        if 0 <= idx < len(schedules):
            schedules.pop(idx)
            data["schedules"] = schedules
            await asyncio.to_thread(_write, data)
            return True
    except Exception:
        pass
    return False


async def run_due_schedules():
    """Run all due schedules (timeframe-based). Returns list of executed schedules."""
    active = await get_active_schedules()
    due = []
    now = datetime.now(timezone.utc)
    for schedule in active:
        timeframe = schedule.get("timeframe", "")
        if _is_due(schedule, now):
            due.append(schedule)
    return due


def _is_due(schedule, now):
    """Check if a schedule is due based on its timeframe."""
    timeframe = schedule.get("timeframe", "")
    last_run = schedule.get("last_run")
    if last_run:
        try:
            last = datetime.fromisoformat(last_run).replace(tzinfo=timezone.utc)
        except Exception:
            last = None
    else:
        last = None

    if "hour" in timeframe.lower():
        return last is None or (now - last) >= timedelta(hours=1)
    if "day" in timeframe.lower():
        return last is None or (now - last) >= timedelta(days=1)
    if "week" in timeframe.lower():
        return last is None or (now - last) >= timedelta(weeks=1)
    if "minute" in timeframe.lower():
        return last is None or (now - last) >= timedelta(minutes=1)
    return False


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