import os
import logging
import json

logger = logging.getLogger(__name__)

_mongo_client_async = None
_mongo_client_sync = None
_mongo_available = None


def _sync_mongo_client():
    """Return the synchronous pymongo client (singleton)."""
    global _mongo_client_sync
    if _mongo_client_sync is not None:
        return _mongo_client_sync
    from config import MONGO_DB
    if not MONGO_DB:
        return None
    try:
        from pymongo import MongoClient
        _mongo_client_sync = MongoClient(
            MONGO_DB,
            serverSelectionTimeoutMS=3000,
            maxPoolSize=10,
            tls=True,
        )
        _mongo_client_sync.server_info()
        return _mongo_client_sync
    except Exception as e:
        logger.warning(f"Sync MongoDB init failed: {e}")
        return None


def _async_mongo_client():
    """Return the async motor client (singleton)."""
    global _mongo_client_async
    if _mongo_client_async is not None:
        return _mongo_client_async
    from config import MONGO_DB
    if not MONGO_DB:
        return None
    try:
        from motor.motor_asyncio import AsyncIOMotorClient
        _mongo_client_async = AsyncIOMotorClient(
            MONGO_DB,
            serverSelectionTimeoutMS=3000,
            maxPoolSize=10,
            tls=True,
        )
        return _mongo_client_async
    except Exception as e:
        logger.warning(f"Async MongoDB init failed: {e}")
        return None


def is_mongo_available():
    """Returns True if MongoDB is reachable."""
    global _mongo_available
    if _mongo_available is not None:
        return _mongo_available
    client = _sync_mongo_client()
    if client is None:
        _mongo_available = False
        return False
    _mongo_available = True
    return True


def _db_name():
    from config import MONGO_DB
    from urllib.parse import urlparse
    parsed = urlparse(MONGO_DB)
    name = parsed.path.lstrip("/") or "safe_repo"
    return name.split("?")[0]


def get_sync_db():
    """Return the sync MongoDB database; None if unavailable."""
    client = _sync_mongo_client()
    if client is None:
        return None
    return client[_db_name()]


def get_async_db():
    """Return the async MongoDB database; None if unavailable."""
    client = _async_mongo_client()
    if client is None:
        return None
    return client[_db_name()]
