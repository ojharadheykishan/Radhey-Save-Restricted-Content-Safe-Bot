"""Auto Session Cleanup — TTL index on sessions collection + cleanup_expired_sessions()."""
import os
import json
import asyncio
import logging
from datetime import datetime, timezone, timedelta

from safe_repo.core.mongo.mongo_client import get_mongo_db, is_mongo_available

logger = logging.getLogger(__name__)

STORAGE = os.path.join(os.path.dirname(__file__), "sessions.json")

SESSION_TTL_SECONDS = 86400  # 24 hours default TTL


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
    return db["sessions"]


def ensure_ttl_index(ttl_seconds=SESSION_TTL_SECONDS):
    """Create a TTL index on the sessions collection (idempotent)."""
    if not is_mongo_available():
        return False
    coll = _get_coll()
    if coll is None:
        return False
    try:
        coll.create_index("expire_at", expireAfterSeconds=ttl_seconds)
        return True
    except Exception:
        return False


async def cleanup_expired_sessions(ttl_seconds=SESSION_TTL_SECONDS):
    """Remove expired sessions. Primary: MongoDB TTL. Fallback: JSON file."""
    cutoff = datetime.now(timezone.utc) - timedelta(seconds=ttl_seconds)

    if is_mongo_available():
        coll = _get_coll()
        if coll is not None:
            result = await coll.delete_many({"expire_at": {"$lte": datetime.now(timezone.utc)}})
            return result.deleted_count

    data = await asyncio.to_thread(_read)
    removed = 0
    for key in list(data.keys()):
        entry = data.get(key, {})
        try:
            expire_at = datetime.fromisoformat(entry.get("expire_at", "")).replace(tzinfo=timezone.utc)
            if expire_at <= datetime.now(timezone.utc):
                data.pop(key, None)
                removed += 1
        except Exception:
            continue
    if removed:
        await asyncio.to_thread(_write, data)
    return removed


async def set_session_expiry(user_id, ttl_seconds=SESSION_TTL_SECONDS):
    """Set a session's expire_at timestamp for TTL purposes."""
    user_id = str(user_id)
    expire_at = datetime.now(timezone.utc) + timedelta(seconds=ttl_seconds)
    data = await asyncio.to_thread(_read)
    data.setdefault(user_id, {})
    data[user_id]["expire_at"] = expire_at.isoformat()
    await asyncio.to_thread(_write, data)
    if is_mongo_available():
        coll = _get_coll()
        if coll is not None:
            await coll.update_one(
                {"user_id": user_id},
                {"$set": {"user_id": user_id, "expire_at": expire_at}},
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


# (task name, interval seconds, coroutine factory)
_CLEANUP_SCHEDULE = (
    ("session_cleanup", 6 * 60 * 60, lambda: cleanup_expired_sessions()),
    ("health_metrics_cleanup", 7 * 24 * 60 * 60, lambda: _health_cleanup()),
    ("activity_cleanup", 30 * 24 * 60 * 60, lambda: _activity_cleanup()),
    ("rate_limit_reset", 24 * 60 * 60, lambda: _rate_limit_reset()),
)


async def _health_cleanup():
    from safe_repo.core.mongo import health_db
    return await health_db.cleanup_old_metrics(days=7)


async def _activity_cleanup():
    from safe_repo.core.mongo import activity_db
    return await activity_db.clear_old_activity(days=30)


async def _rate_limit_reset():
    from safe_repo.core.mongo import rate_limit_db
    return await rate_limit_db.reset_rate_limits()


async def _cleanup_loop(name, interval, factory):
    """Run one cleanup task forever, sleeping `interval` between runs."""
    await asyncio.sleep(interval)
    while True:
        try:
            result = await factory()
            logger.info("auto_cleanup[%s] removed/updated: %s", name, result)
        except asyncio.CancelledError:
            raise
        except Exception as error:
            logger.warning("auto_cleanup[%s] failed: %s", name, error)
        await asyncio.sleep(interval)


def register_auto_cleanup():
    """Schedule periodic cleanup tasks on the running event loop.

    Call once from an async context (e.g. bot startup). Each task runs its
    cleanup immediately after one full interval, so startup is never blocked.
    Individual failures are logged and retried on the next tick.
    """
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        logger.warning("register_auto_cleanup() requires a running event loop; not scheduled")
        return []

    tasks = []
    for name, interval, factory in _CLEANUP_SCHEDULE:
        tasks.append(loop.create_task(_cleanup_loop(name, interval, factory)))
    logger.info("Registered %d auto_cleanup tasks", len(tasks))
    return tasks