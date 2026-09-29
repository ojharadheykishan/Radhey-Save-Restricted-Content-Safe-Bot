"""Premium Quota Tracking — daily/monthly usage per user."""
import os
import json
import asyncio
from datetime import datetime, timezone, timedelta

from safe_repo.core.mongo.mongo_client import get_mongo_db, is_mongo_available

STORAGE = os.path.join(os.path.dirname(__file__), "quotas.json")

DEFAULT_DAILY_LIMIT = 50 * 1024 * 1024  # 50 MB
DEFAULT_MONTHLY_LIMIT = 500 * 1024 * 1024  # 500 MB


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
    return db["user_quotas"]


def _serialize(doc):
    if doc is None:
        return None
    doc = dict(doc)
    doc.pop("_id", None)
    return doc


def _today_str():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _month_str():
    return datetime.now(timezone.utc).strftime("%Y-%m")


async def get_user_quota(user_id):
    """Return quota info for a user. Primary: MongoDB. Fallback: JSON file."""
    user_id = str(user_id)
    if is_mongo_available():
        coll = _get_coll()
        if coll is not None:
            doc = await coll.find_one({"user_id": user_id})
            if doc:
                return _serialize(doc)

    data = await asyncio.to_thread(_read)
    return data.get(user_id)


async def increment_quota(user_id, bytes_used=0):
    """Increment daily/monthly usage counters for a user."""
    user_id = str(user_id)
    today = _today_str()
    month = _month_str()

    # JSON
    data = await asyncio.to_thread(_read)
    entry = data.setdefault(user_id, {
        "daily": {},
        "monthly": {},
        "daily_limit": DEFAULT_DAILY_LIMIT,
        "monthly_limit": DEFAULT_MONTHLY_LIMIT,
    })
    entry.setdefault("daily", {})
    entry.setdefault("monthly", {})
    entry["daily"][today] = entry["daily"].get(today, 0) + bytes_used
    entry["monthly"][month] = entry["monthly"].get(month, 0) + bytes_used
    await asyncio.to_thread(_write, data)

    # MongoDB
    if is_mongo_available():
        coll = _get_coll()
        if coll is not None:
            await coll.update_one(
                {"user_id": user_id},
                {
                    "$inc": {
                        f"daily.{today}": bytes_used,
                        f"monthly.{month}": bytes_used,
                    },
                    "$set": {"user_id": user_id, "last_updated": datetime.now(timezone.utc)},
                },
                upsert=True,
            )
    return True


async def reset_daily_quotas():
    """Reset daily usage counters for all users (called at midnight UTC)."""
    today = _today_str()

    if is_mongo_available():
        coll = _get_coll()
        if coll is not None:
            cursor = coll.find({})
            docs = await cursor.to_list(length=100000)
            for doc in docs:
                daily = doc.get("daily", {})
                daily.clear()
                daily[today] = 0
                await coll.update_one(
                    {"_id": doc["_id"]},
                    {"$set": {"daily": daily, "last_reset": datetime.now(timezone.utc)}},
                )
            return len(docs)

    data = await asyncio.to_thread(_read)
    count = 0
    for uid, entry in data.items():
        entry["daily"] = {today: 0}
        count += 1
    await asyncio.to_thread(_write, data)
    return count


async def check_quota(user_id):
    """Check if user has exceeded their daily/monthly quota."""
    user_id = str(user_id)
    quota = await get_user_quota(user_id)
    if quota is None:
        return {"allowed": True, "daily_used": 0, "monthly_used": 0}

    today = _today_str()
    month = _month_str()
    daily_used = quota.get("daily", {}).get(today, 0)
    monthly_used = quota.get("monthly", {}).get(month, 0)
    daily_limit = quota.get("daily_limit", DEFAULT_DAILY_LIMIT)
    monthly_limit = quota.get("monthly_limit", DEFAULT_MONTHLY_LIMIT)

    return {
        "allowed": daily_used < daily_limit and monthly_used < monthly_limit,
        "daily_used": daily_used,
        "daily_limit": daily_limit,
        "monthly_used": monthly_used,
        "monthly_limit": monthly_limit,
    }


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