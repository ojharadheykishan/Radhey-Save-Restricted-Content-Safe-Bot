import os
import logging
import asyncio
import concurrent.futures
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

_mongo_client_async = None
_mongo_client_sync = None
_mongo_available_cache = None


def _build_client(async_mode: bool):
    """Internal factory for pymongo / motor client."""
    from config import MONGO_DB
    if not MONGO_DB:
        return None
    try:
        if async_mode:
            from motor.motor_asyncio import AsyncIOMotorClient
            return AsyncIOMotorClient(
                MONGO_DB,
                serverSelectionTimeoutMS=5000,
                maxPoolSize=10,
                tls=True,
            )
        else:
            from pymongo import MongoClient
            return MongoClient(
                MONGO_DB,
                serverSelectionTimeoutMS=5000,
                maxPoolSize=10,
                tls=True,
            )
    except Exception as e:
        logger.warning(f"MongoDB client init failed: {e}")
        return None


def _async_mongo_client():
    global _mongo_client_async
    if _mongo_client_async is not None:
        return _mongo_client_async
    _mongo_client_async = _build_client(async_mode=True)
    return _mongo_client_async


def _sync_mongo_client():
    global _mongo_client_sync
    if _mongo_client_sync is not None:
        return _mongo_client_sync
    _mongo_client_sync = _build_client(async_mode=False)
    return _mongo_client_sync


def _db_name() -> str:
    from config import MONGO_DB
    parsed = urlparse(MONGO_DB)
    name = parsed.path.lstrip("/") or "safe_repo"
    return name.split("?")[0]


def is_mongo_available(force=False) -> bool:
    global _mongo_available_cache
    if not force and _mongo_available_cache is not None:
        return _mongo_available_cache
    client = _sync_mongo_client()
    if client is None:
        _mongo_available_cache = False
        return False
    try:
        client.server_info()
        _mongo_available_cache = True
        logger.info(f"MongoDB connected to {_db_name()}")
        return True
    except Exception as e:
        logger.warning(f"MongoDB not reachable, falling back to JSON: {e}")
        _mongo_available_cache = False
        return False


def get_mongo_db():
    """Return async Motor database (used by bot-side async modules)."""
    client = _async_mongo_client()
    if client is None:
        return None
    return client[_db_name()]


def get_async_db():
    """Alias for get_mongo_db — async Motor database."""
    return get_mongo_db()


def get_sync_db():
    """Return sync pymongo database (used by sync functions like media_links.py)."""
    client = _sync_mongo_client()
    if client is None:
        return None
    return client[_db_name()]


def _run_async(coro):
    """Run an awaitable from synchronous code without conflicting with Motor."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        # We are inside a running event loop (e.g. Pyrogram async context).
        # Run the coroutine in a separate thread with its own loop.
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(asyncio.run, coro)
            return future.result()
    else:
        # No running loop — safe to use asyncio.run directly
        return asyncio.run(coro)


def get_mongo_status():
    """Return a dict describing the live MongoDB connection status (sync)."""
    from config import MONGO_DB
    status = {
        "mongo_db_env_set": bool(MONGO_DB),
        "mongo_db_configured": bool(MONGO_DB) and "mongodb" in (MONGO_DB or ""),
        "connected": False,
        "database": _db_name() if MONGO_DB and "mongodb" in MONGO_DB else None,
        "server_version": None,
        "collections": [],
        "stream_catalog_count": 0,
        "stream_catalog_approved": 0,
        "stream_catalog_pending": 0,
        "recent_entries": [],
        "error": None,
    }
    if not status["mongo_db_configured"]:
        status["error"] = "MONGO_DB is not set or invalid"
        return status
    client = _sync_mongo_client()
    if client is None:
        status["error"] = "MongoClient could not be initialized"
        return status
    try:
        info = client.server_info()
        status["server_version"] = info.get("version")
        db = client[_db_name()]
        status["collections"] = sorted(db.list_collection_names())
        if "stream_catalog" in status["collections"]:
            coll = db["stream_catalog"]
            status["stream_catalog_count"] = coll.count_documents({})
            status["stream_catalog_approved"] = coll.count_documents({"approved": True})
            status["stream_catalog_pending"] = coll.count_documents({"approved": False})
            cursor = coll.find({}).sort("timestamp", -1).limit(20)
            for doc in cursor:
                status["recent_entries"].append({
                    "token": str(doc.get("token", "")),
                    "file_name": doc.get("file_name", ""),
                    "file_size": doc.get("file_size", 0),
                    "approved": doc.get("approved", True),
                    "folder": doc.get("folder", "General"),
                    "timestamp": doc.get("timestamp", ""),
                    "source": "mongo",
                })
        status["connected"] = True
    except Exception as e:
        status["connected"] = False
        status["error"] = str(e)
    return status
