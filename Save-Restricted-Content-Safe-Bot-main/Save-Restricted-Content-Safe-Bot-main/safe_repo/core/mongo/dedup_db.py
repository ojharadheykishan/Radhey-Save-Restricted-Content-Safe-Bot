"""Smart Link Dedup — find existing media by content hash."""
import os
import json
import asyncio
from datetime import datetime, timezone

from safe_repo.core.mongo.mongo_client import get_mongo_db, is_mongo_available

STORAGE = os.path.join(os.path.dirname(__file__), "dedup.json")


def _read():
    if not os.path.exists(STORAGE):
        return {"entries": []}
    try:
        with open(STORAGE, "r") as f:
            return json.load(f)
    except Exception:
        return {"entries": []}


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
    return db["media_dedup"]


def _serialize(doc):
    if doc is None:
        return None
    doc = dict(doc)
    doc.pop("_id", None)
    return doc


async def find_by_content_hash(content_hash):
    """Find an existing media entry by content hash."""
    if is_mongo_available():
        coll = _get_coll()
        if coll is not None:
            doc = await coll.find_one({"content_hash": content_hash})
            if doc:
                return _serialize(doc)

    data = await asyncio.to_thread(_read)
    entries = data.get("entries", [])
    for entry in entries:
        if entry.get("content_hash") == content_hash:
            return entry
    return None


async def index_media_entry(entry):
    """Index a media entry by content hash."""
    content_hash = entry.get("content_hash")
    if not content_hash:
        return False

    indexed = dict(entry)
    indexed["content_hash"] = content_hash
    indexed["indexed_at"] = datetime.now(timezone.utc)

    # JSON
    data = await asyncio.to_thread(_read)
    entries = data.get("entries", [])
    # Replace existing entry with same hash
    entries = [e for e in entries if e.get("content_hash") != content_hash]
    entries.append(indexed)
    data["entries"] = entries
    await asyncio.to_thread(_write, data)

    # MongoDB
    if is_mongo_available():
        coll = _get_coll()
        if coll is not None:
            await coll.update_one(
                {"content_hash": content_hash},
                {"$set": indexed},
                upsert=True,
            )
    return True


async def get_duplicate_stats():
    """Return stats about duplicate detection."""
    if is_mongo_available():
        coll = _get_coll()
        if coll is not None:
            count = await coll.count_documents({})
            return {"total_indexed": count}

    data = await asyncio.to_thread(_read)
    entries = data.get("entries", [])
    return {"total_indexed": len(entries)}


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