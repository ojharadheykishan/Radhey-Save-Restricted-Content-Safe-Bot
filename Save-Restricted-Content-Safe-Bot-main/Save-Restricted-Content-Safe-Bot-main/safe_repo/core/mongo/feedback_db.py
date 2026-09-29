"""User Feedback System — store user feedback and reports."""
import os
import json
import asyncio
from datetime import datetime, timezone

from safe_repo.core.mongo.mongo_client import get_mongo_db, is_mongo_available

STORAGE = os.path.join(os.path.dirname(__file__), "feedback.json")


def _read():
    if not os.path.exists(STORAGE):
        return {"feedback": []}
    try:
        with open(STORAGE, "r") as f:
            return json.load(f)
    except Exception:
        return {"feedback": []}


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
    return db["user_feedback"]


def _serialize(doc):
    if doc is None:
        return None
    doc = dict(doc)
    doc.pop("_id", None)
    return doc


async def save_feedback(user_id, message, category, token=None):
    """Save user feedback or a report."""
    user_id = str(user_id)
    entry = {
        "user_id": user_id,
        "message": message,
        "category": category,
        "token": token,
        "status": "pending",
        "created_at": datetime.now(timezone.utc),
        "resolved_at": None,
    }
    # JSON
    data = await asyncio.to_thread(_read)
    feedback = data.get("feedback", [])
    entry_json = dict(entry)
    entry_json["created_at"] = entry["created_at"].isoformat()
    feedback.append(entry_json)
    data["feedback"] = feedback
    await asyncio.to_thread(_write, data)
    # MongoDB
    if is_mongo_available():
        coll = _get_coll()
        if coll is not None:
            await coll.insert_one(entry)
    return True


async def get_pending_feedback(limit=50):
    """Return pending feedback entries."""
    if is_mongo_available():
        coll = _get_coll()
        if coll is not None:
            cursor = coll.find({"status": "pending"}).sort("created_at", -1).limit(limit)
            docs = await cursor.to_list(length=limit)
            return [_serialize(d) for d in docs]

    data = await asyncio.to_thread(_read)
    feedback = data.get("feedback", [])
    pending = [f for f in feedback if f.get("status") == "pending"]
    return pending[-limit:]


async def resolve_feedback(feedback_id):
    """Mark a feedback entry as resolved."""
    if is_mongo_available():
        coll = _get_coll()
        if coll is not None:
            result = await coll.update_one(
                {"_id": feedback_id},
                {"$set": {"status": "resolved", "resolved_at": datetime.now(timezone.utc)}},
            )
            return result.modified_count > 0

    # Fallback: feedback_id is a JSON index
    try:
        idx = int(feedback_id)
        data = await asyncio.to_thread(_read)
        feedback = data.get("feedback", [])
        if 0 <= idx < len(feedback):
            feedback[idx]["status"] = "resolved"
            feedback[idx]["resolved_at"] = datetime.now(timezone.utc).isoformat()
            await asyncio.to_thread(_write, data)
            return True
    except Exception:
        pass
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